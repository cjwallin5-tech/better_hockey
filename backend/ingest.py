"""Pull skater stats from the NHL APIs into Postgres. Safe to re-run (upserts)."""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import requests

import config

session = requests.Session()


def get_json(url, **params):
    for attempt in range(8):
        r = session.get(url, params=params, timeout=30)
        if r.status_code == 429:  # rate limited: honor Retry-After, else back off
            time.sleep(float(r.headers.get("Retry-After", min(5 * 2 ** attempt, 120))))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def fetch_report(report):
    data = get_json(
        f"{config.STATS_API}/skater/{report}",
        limit=-1,
        cayenneExp=f"seasonId={config.SEASON_ID} and gameTypeId={config.GAME_TYPE}",
    )
    return {row["playerId"]: row for row in data["data"]}


def toi_to_sec(toi):
    if not toi:
        return None
    m, s = toi.split(":")
    return int(m) * 60 + int(s)


def ingest_season(conn):
    summary = fetch_report("summary")
    realtime = fetch_report("realtime")
    rows = []
    for pid, s in summary.items():
        r = realtime.get(pid, {})
        rows.append((
            config.SEASON_ID, pid, s["skaterFullName"], s.get("teamAbbrevs"),
            s.get("positionCode"), s["gamesPlayed"], s["goals"], s["assists"],
            s["points"], s.get("plusMinus"), s.get("penaltyMinutes"), s.get("shots"),
            s.get("timeOnIcePerGame"), r.get("hits"), r.get("blockedShots"),
            r.get("takeaways"), r.get("giveaways"), r.get("hitsPer60"),
            r.get("blockedShotsPer60"), r.get("takeawaysPer60"), r.get("giveawaysPer60"),
        ))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO skater_season (
                season_id, player_id, name, team, position, games_played, goals,
                assists, points, plus_minus, pim, shots, toi_per_game_sec, hits,
                blocked_shots, takeaways, giveaways, hits_per60, blocks_per60,
                takeaways_per60, giveaways_per60)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (season_id, player_id) DO UPDATE SET
                name=EXCLUDED.name, team=EXCLUDED.team, position=EXCLUDED.position,
                games_played=EXCLUDED.games_played, goals=EXCLUDED.goals,
                assists=EXCLUDED.assists, points=EXCLUDED.points,
                plus_minus=EXCLUDED.plus_minus, pim=EXCLUDED.pim, shots=EXCLUDED.shots,
                toi_per_game_sec=EXCLUDED.toi_per_game_sec, hits=EXCLUDED.hits,
                blocked_shots=EXCLUDED.blocked_shots, takeaways=EXCLUDED.takeaways,
                giveaways=EXCLUDED.giveaways, hits_per60=EXCLUDED.hits_per60,
                blocks_per60=EXCLUDED.blocks_per60,
                takeaways_per60=EXCLUDED.takeaways_per60,
                giveaways_per60=EXCLUDED.giveaways_per60, updated_at=now()
            """,
            rows,
        )
    conn.commit()
    print(f"season stats: {len(rows)} skaters")


def fetch_game_log(pid):
    data = get_json(f"{config.WEB_API}/player/{pid}/game-log/{config.SEASON_ID}/{config.GAME_TYPE}")
    time.sleep(0.25)  # stay well under the API's rate limit
    return pid, data["gameLog"]


def ingest_game_logs(conn):
    # Only refetch players whose stored game count is behind the season totals.
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.player_id FROM skater_season s
            LEFT JOIN (SELECT player_id, count(*) n FROM skater_game
                       WHERE season_id = %(sid)s GROUP BY player_id) g USING (player_id)
            WHERE s.season_id = %(sid)s AND s.games_played > 0
              AND COALESCE(g.n, 0) < s.games_played
            """,
            {"sid": config.SEASON_ID},
        )
        todo = [r[0] for r in cur.fetchall()]
    print(f"game logs: fetching {len(todo)} players")

    with ThreadPoolExecutor(max_workers=2) as pool, conn.cursor() as cur:
        for i, (pid, log) in enumerate(pool.map(fetch_game_log, todo), 1):
            cur.executemany(
                """
                INSERT INTO skater_game (player_id, season_id, game_id, game_date, team,
                    opponent, is_home, goals, assists, points, shots, plus_minus, pim, toi_sec)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (player_id, game_id) DO NOTHING
                """,
                [(pid, config.SEASON_ID, g["gameId"], g["gameDate"], g.get("teamAbbrev"),
                  g.get("opponentAbbrev"), g.get("homeRoadFlag") == "H", g["goals"],
                  g["assists"], g["points"], g.get("shots"), g.get("plusMinus"),
                  g.get("pim"), toi_to_sec(g.get("toi"))) for g in log],
            )
            if i % 25 == 0:  # commit as we go so an interrupted run keeps its progress
                conn.commit()
                print(f"  {i}/{len(todo)}", flush=True)
    conn.commit()


def main():
    with psycopg.connect(config.DATABASE_URL) as conn:
        conn.execute((Path(__file__).parent / "schema.sql").read_text())
        conn.commit()
        ingest_season(conn)
        if "--skip-logs" not in sys.argv:
            ingest_game_logs(conn)


if __name__ == "__main__":
    main()
