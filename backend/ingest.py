"""Pull skater stats from the NHL APIs into Postgres. Safe to re-run (upserts)."""
import json
import sys
import time
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import requests

import config
import corsi
import era
import html_shifts
import shots as shotlib

FINAL_STATES = ('OFF', 'FINAL')

session = requests.Session()


def get_json(url, **params):
    for attempt in range(8):
        try:
            r = session.get(url, params=params, timeout=60)
        except (requests.Timeout, requests.ConnectionError):
            # The NHL APIs time out now and then (this is what killed a nightly run); back off and retry.
            if attempt == 7:
                raise
            time.sleep(min(5 * 2 ** attempt, 60))
            continue
        if r.status_code == 429 or r.status_code >= 500:  # rate limited or flaky: honor Retry-After, else back off
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


# Extra season-level stats, one NHL stats-API report each: (column, report, field, SQL type).
# Columns are created on demand, so adding a stat is a one-line change here.
EXTRA_STATS = [
    # summary
    ("fo_win_pct", "summary", "faceoffWinPct", "REAL"),
    ("shooting_pct", "summary", "shootingPct", "REAL"),
    ("game_winning_goals", "summary", "gameWinningGoals", "INTEGER"),
    ("ev_points", "summary", "evPoints", "INTEGER"),
    ("pp_goals", "summary", "ppGoals", "INTEGER"),
    ("pp_points", "summary", "ppPoints", "INTEGER"),
    ("sh_points", "summary", "shPoints", "INTEGER"),
    # bio (one request covers every skater)
    ("birth_date", "bios", "birthDate", "DATE"),
    ("birth_country", "bios", "nationalityCode", "TEXT"),
    ("height_in", "bios", "height", "INTEGER"),
    ("weight_lb", "bios", "weight", "INTEGER"),
    ("shoots", "bios", "shootsCatches", "TEXT"),
    ("draft_year", "bios", "draftYear", "INTEGER"),
    ("draft_overall", "bios", "draftOverall", "INTEGER"),
    ("first_nhl_season", "bios", "firstSeasonForGameType", "INTEGER"),
    # 5v5 shot attempts: SAT = Corsi, USAT = Fenwick
    ("sat_for", "summaryshooting", "satFor", "INTEGER"),
    ("sat_against", "summaryshooting", "satAgainst", "INTEGER"),
    ("sat_rel", "summaryshooting", "satRelative", "REAL"),
    ("usat_for", "summaryshooting", "usatFor", "INTEGER"),
    ("usat_against", "summaryshooting", "usatAgainst", "INTEGER"),
    ("usat_rel", "summaryshooting", "usatRelative", "REAL"),
    ("toi_5v5_per_game", "summaryshooting", "timeOnIcePerGame5v5", "REAL"),
    ("sat_pct", "percentages", "satPercentage", "REAL"),
    ("usat_pct", "percentages", "usatPercentage", "REAL"),
    ("zone_start_pct_5v5", "percentages", "zoneStartPct5v5", "REAL"),
    ("pdo_5v5", "percentages", "skaterShootingPlusSavePct5v5", "REAL"),
    # even-strength goals while on the ice
    ("ev_goals_for", "goalsForAgainst", "evenStrengthGoalsFor", "INTEGER"),
    ("ev_goals_against", "goalsForAgainst", "evenStrengthGoalsAgainst", "INTEGER"),
    ("ev_goals_for_pct", "goalsForAgainst", "evenStrengthGoalsForPct", "REAL"),
    # ice time by situation
    ("ev_toi_per_game", "timeonice", "evTimeOnIcePerGame", "REAL"),
    ("pp_toi_per_game", "timeonice", "ppTimeOnIcePerGame", "REAL"),
    ("sh_toi_per_game", "timeonice", "shTimeOnIcePerGame", "REAL"),
    ("shifts_per_game", "timeonice", "shiftsPerGame", "REAL"),
    ("toi_per_shift", "timeonice", "timeOnIcePerShift", "REAL"),
    # special teams
    ("pp_points_per60", "powerplay", "ppPointsPer60", "REAL"),
    ("pp_toi_pct", "powerplay", "ppTimeOnIcePctPerGame", "REAL"),
    ("sh_toi_pct", "penaltykill", "shTimeOnIcePctPerGame", "REAL"),
    ("pk_goals_against_per60", "penaltykill", "ppGoalsAgainstPer60", "REAL"),
]


# Goalie season stats: (column, report, field, SQL type). The first report ("summary") defines
# which goalies exist; the rest are layered on by player id.
GOALIE_STATS = [
    ("team", "summary", "teamAbbrevs", "TEXT"),
    ("catches", "summary", "shootsCatches", "TEXT"),
    ("games_played", "summary", "gamesPlayed", "INTEGER"),
    ("games_started", "summary", "gamesStarted", "INTEGER"),
    ("wins", "summary", "wins", "INTEGER"),
    ("losses", "summary", "losses", "INTEGER"),
    ("ot_losses", "summary", "otLosses", "INTEGER"),
    ("saves", "summary", "saves", "INTEGER"),
    ("shots_against", "summary", "shotsAgainst", "INTEGER"),
    ("goals_against", "summary", "goalsAgainst", "INTEGER"),
    ("save_pct", "summary", "savePct", "REAL"),
    ("gaa", "summary", "goalsAgainstAverage", "REAL"),
    ("shutouts", "summary", "shutouts", "INTEGER"),
    ("toi_sec", "summary", "timeOnIce", "INTEGER"),
    ("quality_starts", "advanced", "qualityStart", "INTEGER"),
    ("quality_start_pct", "advanced", "qualityStartsPct", "REAL"),
    ("complete_games", "advanced", "completeGames", "INTEGER"),
    ("shots_against_per60", "advanced", "shotsAgainstPer60", "REAL"),
    ("goal_support_avg", "advanced", "goalsForAverage", "REAL"),
    ("ev_saves", "savesByStrength", "evSaves", "INTEGER"),
    ("ev_shots_against", "savesByStrength", "evShotsAgainst", "INTEGER"),
    ("ev_save_pct", "savesByStrength", "evSavePct", "REAL"),
    ("pp_saves", "savesByStrength", "ppSaves", "INTEGER"),
    ("pp_shots_against", "savesByStrength", "ppShotsAgainst", "INTEGER"),
    ("pp_save_pct", "savesByStrength", "ppSavePct", "REAL"),
    ("sh_saves", "savesByStrength", "shSaves", "INTEGER"),
    ("sh_shots_against", "savesByStrength", "shShotsAgainst", "INTEGER"),
    ("sh_save_pct", "savesByStrength", "shSavePct", "REAL"),
    ("games_relieved", "startedVsRelieved", "gamesRelieved", "INTEGER"),
]


def fetch_goalie_report(report):
    data = get_json(
        f"{config.STATS_API}/goalie/{report}",
        limit=-1,
        cayenneExp=f"seasonId={config.SEASON_ID} and gameTypeId={config.GAME_TYPE}",
    )
    return {row["playerId"]: row for row in data["data"]}


def ingest_goalie_season(conn):
    for col, _, _, sql_type in GOALIE_STATS:
        conn.execute(f"ALTER TABLE goalie_season ADD COLUMN IF NOT EXISTS {col} {sql_type}")

    reports = {}
    for report in dict.fromkeys(r for _, r, _, _ in GOALIE_STATS):  # keeps order, "summary" first
        if reports:
            time.sleep(1)
        reports[report] = fetch_goalie_report(report)

    cols = [c for c, _, _, _ in GOALIE_STATS]
    rows = [
        [config.SEASON_ID, pid, s["goalieFullName"]]
        + [reports[report].get(pid, {}).get(field) for _, report, field, _ in GOALIE_STATS]
        for pid, s in reports["summary"].items()
    ]
    updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in ["name"] + cols)
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO goalie_season (season_id, player_id, name, {', '.join(cols)}) "
            f"VALUES ({', '.join(['%s'] * (3 + len(cols)))}) "
            f"ON CONFLICT (season_id, player_id) DO UPDATE SET {updates}, updated_at = now()",
            rows,
        )
    conn.commit()
    print(f"goalie season stats: {len(rows)} goalies")


# --- All-time career totals ------------------------------------------------------------------
# (column, report, field, SQL type); "summary" defines which players exist. Columns are created
# on demand. Early eras lack some stats (shots start in 1967-68, +/- in 1959-60), so many are NULL.
ALLTIME_SKATER = [
    ("position", "summary", "positionCode", "TEXT"),
    ("shoots", "summary", "shootsCatches", "TEXT"),
    ("games_played", "summary", "gamesPlayed", "INTEGER"),
    ("goals", "summary", "goals", "INTEGER"),
    ("assists", "summary", "assists", "INTEGER"),
    ("points", "summary", "points", "INTEGER"),
    ("points_per_game", "summary", "pointsPerGame", "REAL"),
    ("plus_minus", "summary", "plusMinus", "INTEGER"),
    ("pim", "summary", "penaltyMinutes", "INTEGER"),
    ("ev_goals", "summary", "evGoals", "INTEGER"),
    ("pp_goals", "summary", "ppGoals", "INTEGER"),
    ("pp_points", "summary", "ppPoints", "INTEGER"),
    ("sh_goals", "summary", "shGoals", "INTEGER"),
    ("sh_points", "summary", "shPoints", "INTEGER"),
    ("game_winning_goals", "summary", "gameWinningGoals", "INTEGER"),
    ("ot_goals", "summary", "otGoals", "INTEGER"),
    ("shots", "summary", "shots", "INTEGER"),
    ("shooting_pct", "summary", "shootingPct", "REAL"),
    ("fo_win_pct", "summary", "faceoffWinPct", "REAL"),
    # The NHL only began tracking these in 2005-06; earlier seasons are blanked out below.
    ("hits", "realtime", "hits", "INTEGER"),
    ("blocked_shots", "realtime", "blockedShots", "INTEGER"),
    ("takeaways", "realtime", "takeaways", "INTEGER"),
    ("giveaways", "realtime", "giveaways", "INTEGER"),
    ("missed_shots", "realtime", "missedShots", "INTEGER"),
    ("shot_attempts", "realtime", "totalShotAttempts", "INTEGER"),
    ("empty_net_goals", "realtime", "emptyNetGoals", "INTEGER"),
    ("first_goals", "realtime", "firstGoals", "INTEGER"),
    ("birth_date", "bios", "birthDate", "DATE"),
    ("birth_country", "bios", "nationalityCode", "TEXT"),
    ("first_season", "bios", "firstSeasonForGameType", "INTEGER"),
    ("draft_year", "bios", "draftYear", "INTEGER"),
    ("hall_of_fame", "bios", "isInHallOfFameYn", "TEXT"),
]
ALLTIME_GOALIE = [
    ("catches", "summary", "shootsCatches", "TEXT"),
    ("games_played", "summary", "gamesPlayed", "INTEGER"),
    ("games_started", "summary", "gamesStarted", "INTEGER"),
    ("wins", "summary", "wins", "INTEGER"),
    ("losses", "summary", "losses", "INTEGER"),
    ("ot_losses", "summary", "otLosses", "INTEGER"),
    ("ties", "summary", "ties", "INTEGER"),
    ("saves", "summary", "saves", "INTEGER"),
    ("shots_against", "summary", "shotsAgainst", "INTEGER"),
    ("goals_against", "summary", "goalsAgainst", "INTEGER"),
    ("save_pct", "summary", "savePct", "REAL"),
    ("gaa", "summary", "goalsAgainstAverage", "REAL"),
    ("shutouts", "summary", "shutouts", "INTEGER"),
    ("toi_sec", "summary", "timeOnIce", "INTEGER"),
    ("goals", "summary", "goals", "INTEGER"),
    ("assists", "summary", "assists", "INTEGER"),
    ("pim", "summary", "penaltyMinutes", "INTEGER"),
    ("birth_date", "bios", "birthDate", "DATE"),
    ("birth_country", "bios", "nationalityCode", "TEXT"),
    ("first_season", "bios", "firstSeasonForGameType", "INTEGER"),
    ("draft_year", "bios", "draftYear", "INTEGER"),
    ("hall_of_fame", "bios", "isInHallOfFameYn", "TEXT"),
]
ALLTIME_MAX_AGE_HOURS = 12  # career totals only need a refresh about once a day


def _aggregate_report(kind, report, game_type, **extra):
    """Career-aggregate rows for every player, keyed by player id."""
    data = get_json(
        f"{config.STATS_API}/{kind}/{report}",
        isAggregate="true", limit=-1, cayenneExp=f"gameTypeId={game_type}", **extra,
    )
    return {row["playerId"]: row for row in data["data"]}


def _season_player_ids(kind, season_id):
    data = get_json(
        f"{config.STATS_API}/{kind}/summary",
        limit=-1, cayenneExp=f"seasonId={season_id} and gameTypeId={config.GAME_TYPE}",
    )
    return {row["playerId"] for row in data["data"]}


def ingest_alltime(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT max(updated_at) > now() - make_interval(hours => %s) FROM career_skater",
                    (ALLTIME_MAX_AGE_HOURS,))
        if cur.fetchone()[0]:
            print("all-time: fresh, skipping")
            return

    prev = config.SEASON_ID - 10001  # 20262027 -> 20252026
    for kind, table, stats, name_field in (
        ("skater", "career_skater", ALLTIME_SKATER, "skaterFullName"),
        ("goalie", "career_goalie", ALLTIME_GOALIE, "goalieFullName"),
    ):
        for col, _, _, sql_type in stats:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {sql_type}")
        conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS active_season INTEGER")

        # "Active" = has games this season or last (so early-season injuries still count).
        current, previous = _season_player_ids(kind, config.SEASON_ID), _season_player_ids(kind, prev)
        time.sleep(1)
        cols = [c for c, _, _, _ in stats]
        for game_type in (2, 3):
            reports = {}
            for report in dict.fromkeys(r for _, r, _, _ in stats):
                reports[report] = _aggregate_report(kind, report, game_type)
                time.sleep(1)
            rows = []
            for pid, base in reports["summary"].items():
                active = config.SEASON_ID if pid in current else prev if pid in previous else None
                rows.append([pid, game_type, base[name_field], active]
                            + [reports[r].get(pid, {}).get(f) for _, r, f, _ in stats])
            updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in ["name", "active_season"] + cols)
            with conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO {table} (player_id, game_type, name, active_season, {', '.join(cols)}) "
                    f"VALUES ({', '.join(['%s'] * (4 + len(cols)))}) "
                    f"ON CONFLICT (player_id, game_type) DO UPDATE SET {updates}, updated_at = now()",
                    rows,
                )
            if kind == "skater":
                # The feed reports 0 (not null) for careers before tracking began; show those as unknown.
                conn.execute(
                    """UPDATE career_skater SET hits = NULL, blocked_shots = NULL, takeaways = NULL,
                              giveaways = NULL, missed_shots = NULL, shot_attempts = NULL
                       WHERE game_type = %s AND COALESCE(hits, 0) = 0 AND COALESCE(blocked_shots, 0) = 0
                         AND COALESCE(takeaways, 0) = 0 AND COALESCE(giveaways, 0) = 0""",
                    (game_type,),
                )
            conn.commit()
            print(f"all-time {kind} (game type {game_type}): {len(rows)} players")


HISTORY_SEASONS = 4  # how many past seasons feed the pace-history charts
HISTORY_GAMES_PER_SEASON = 1312  # 32 teams x 82 games / 2 (past seasons were 82 games)


def ingest_history(conn):
    """Past seasons' per-game results (immutable, so each season is fetched once) and season records."""
    for back in range(1, HISTORY_SEASONS + 1):
        season = config.SEASON_ID - 10001 * back
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM team_game_hist WHERE season_id = %s", (season,))
            have_team = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM skater_game_hist WHERE season_id = %s", (season,))
            have_skater = cur.fetchone()[0]
        first_game = season // 10000 * 1000000 + 20000  # e.g. 2025020000
        if not have_team:
            data = get_json(f"{config.STATS_API}/team/summary", isGame="true", limit=-1,
                            cayenneExp=f"seasonId={season} and gameTypeId={config.GAME_TYPE}")["data"]
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO team_game_hist (team_name, season_id, game_id, game_date, points, wins, goals_for, goals_against)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    [(r["teamFullName"], season, r["gameId"], r["gameDate"], r["points"], r["wins"], r["goalsFor"], r["goalsAgainst"])
                     for r in data],
                )
            conn.commit()
            print(f"history {season}: {len(data)} team games")
            time.sleep(1)
        if not have_skater:
            total = 0
            for lo in range(1, HISTORY_GAMES_PER_SEASON + 1, 220):  # ~38 skaters/game keeps each window under 10,000 rows
                hi = lo + 220
                data = get_json(
                    f"{config.STATS_API}/skater/summary", isGame="true", limit=-1,
                    cayenneExp=f"seasonId={season} and gameTypeId={config.GAME_TYPE} and gameId>={first_game + lo} and gameId<{first_game + hi}",
                )["data"]
                with conn.cursor() as cur:
                    cur.executemany(
                        """INSERT INTO skater_game_hist (player_id, season_id, game_id, game_date, goals, assists, points)
                           VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                        [(r["playerId"], season, r["gameId"], r["gameDate"], r["goals"], r["assists"], r["points"]) for r in data],
                    )
                conn.commit()
                total += len(data)
                time.sleep(1)
            print(f"history {season}: {total} skater games")

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM season_record")
        have_records = cur.fetchone()[0]
    if not have_records:
        for stat in ("goals", "assists", "points"):
            sort = json.dumps([{"property": stat, "direction": "DESC"}])
            top = get_json(f"{config.STATS_API}/skater/summary", limit=5, sort=sort, cayenneExp="gameTypeId=2")["data"]
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO season_record (stat, rank, player_id, name, season_id, games, value) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    [(stat, i, r["playerId"], r["skaterFullName"], r["seasonId"], r["gamesPlayed"], r[stat]) for i, r in enumerate(top, 1)],
                )
            conn.commit()
            time.sleep(1)
        print("season records stored")


def toi_to_sec(toi):
    if not toi:
        return None
    m, s = toi.split(":")
    return int(m) * 60 + int(s)


def ingest_extra_stats(conn, summary):
    """Layer the EXTRA_STATS columns onto skater_season (creating any that are missing)."""
    for col, _, _, sql_type in EXTRA_STATS:
        conn.execute(f"ALTER TABLE skater_season ADD COLUMN IF NOT EXISTS {col} {sql_type}")

    reports = {"summary": summary}
    for report in {r for _, r, _, _ in EXTRA_STATS} - set(reports):
        time.sleep(1)  # one request per report; be gentle with the API
        reports[report] = fetch_report(report)

    assignments = ", ".join(f"{col} = %s" for col, _, _, _ in EXTRA_STATS)
    rows = [
        [reports[report].get(pid, {}).get(field) for _, report, field, _ in EXTRA_STATS]
        + [config.SEASON_ID, pid]
        for pid in summary
    ]
    with conn.cursor() as cur:
        cur.executemany(
            f"UPDATE skater_season SET {assignments} WHERE season_id = %s AND player_id = %s", rows
        )
    conn.commit()
    print(f"extra stats: {len(EXTRA_STATS)} columns from {len(reports)} reports")


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
    ingest_extra_stats(conn, summary)


def ingest_teams(conn):
    """Standings (records, ranks, logos) joined with team-level stats from the stats API."""
    standings = get_json(f"{config.WEB_API}/standings/{date.today()}")["standings"]
    time.sleep(1)
    stats = get_json(
        f"{config.STATS_API}/team/summary",
        limit=-1,
        cayenneExp=f"seasonId={config.SEASON_ID} and gameTypeId={config.GAME_TYPE}",
    )["data"]
    by_name = {t["teamFullName"]: t for t in stats}

    rows = []
    for t in standings:
        if t["seasonId"] != config.SEASON_ID:
            continue
        name = t["teamName"]["default"]
        s = by_name.get(name, {})
        if not s:
            print(f"  warning: no team stats matched for {name!r}")
        rows.append((
            config.SEASON_ID, t["teamAbbrev"]["default"], s.get("teamId"), name,
            t["teamCommonName"]["default"], t["teamLogo"], t["teamLogoDark"],
            t["conferenceName"], t["divisionName"], t["leagueSequence"],
            t["conferenceSequence"], t["divisionSequence"], t["wildcardSequence"],
            t["gamesPlayed"], t["wins"], t["losses"], t["otLosses"], t["points"],
            t["pointPctg"], t["regulationWins"], t["regulationPlusOtWins"],
            t["goalFor"], t["goalAgainst"], t["goalDifferential"], t["l10Wins"],
            t["l10Losses"], t["l10OtLosses"], t["l10Points"], t["streakCode"],
            t["streakCount"],
            f"{t['homeWins']}-{t['homeLosses']}-{t['homeOtLosses']}",
            f"{t['roadWins']}-{t['roadLosses']}-{t['roadOtLosses']}",
            s.get("powerPlayPct"), s.get("penaltyKillPct"), s.get("shotsForPerGame"),
            s.get("shotsAgainstPerGame"), s.get("faceoffWinPct"), s.get("teamShutouts"),
        ))
    cols = ("season_id abbrev team_id name common_name logo_url logo_dark_url conference "
            "division league_rank conference_rank division_rank wildcard_rank games_played "
            "wins losses ot_losses points point_pct reg_wins reg_ot_wins goals_for "
            "goals_against goal_diff l10_wins l10_losses l10_ot_losses l10_points "
            "streak_code streak_count home_record road_record pp_pct pk_pct shots_for_pg "
            "shots_against_pg fo_win_pct shutouts").split()
    updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols[2:])
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO team_season ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
            f"ON CONFLICT (season_id, abbrev) DO UPDATE SET {updates}, updated_at = now()",
            rows,
        )
    conn.commit()
    print(f"teams: {len(rows)} teams")


SCHEDULE_LOOKAHEAD_DAYS = 200  # the whole regular season: playoff odds and the schedule grid need every remaining game
SCHEDULE_REWIND_DAYS = 21  # re-read recent weeks: postponements and score corrections


def ingest_schedule(conn):
    """Store every regular-season game (scores when finished, start times when upcoming)."""
    today = date.today()
    with conn.cursor() as cur:
        cur.execute("SELECT max(game_date) FROM game WHERE season_id = %s", (config.SEASON_ID,))
        last = cur.fetchone()[0]
    if last:
        cursor = today - timedelta(days=SCHEDULE_REWIND_DAYS)
    else:
        cursor = date.fromisoformat(get_json(f"{config.WEB_API}/schedule/{today}")["regularSeasonStartDate"])
    horizon = today + timedelta(days=SCHEDULE_LOOKAHEAD_DAYS)

    rows = {}
    while cursor <= horizon:
        week = get_json(f"{config.WEB_API}/schedule/{cursor}")
        for day in week["gameWeek"]:
            for g in day["games"]:
                if g["gameType"] != config.GAME_TYPE or g.get("season") != config.SEASON_ID:
                    continue
                rows[g["id"]] = (
                    g["id"], config.SEASON_ID, day["date"], g.get("startTimeUTC"),
                    (g.get("venue") or {}).get("default"), g["gameState"],
                    g["homeTeam"]["abbrev"], g["awayTeam"]["abbrev"],
                    g["homeTeam"].get("score"), g["awayTeam"].get("score"),
                    (g.get("gameOutcome") or {}).get("lastPeriodType"),
                )
        nxt = week.get("nextStartDate")
        if not nxt:
            break
        cursor = date.fromisoformat(nxt)
        time.sleep(0.3)
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO game (game_id, season_id, game_date, start_time, venue, state, home, away,
                                 home_score, away_score, last_period)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (game_id) DO UPDATE SET game_date=EXCLUDED.game_date,
                   start_time=EXCLUDED.start_time, venue=EXCLUDED.venue, state=EXCLUDED.state,
                   home_score=EXCLUDED.home_score, away_score=EXCLUDED.away_score,
                   last_period=EXCLUDED.last_period, updated_at=now()""",
            list(rows.values()),
        )
    conn.commit()
    print(f"schedule: {len(rows)} games")


def schedule_final_game_ids(conn):
    """IDs of finished regular-season games we haven't stored yet, found via the weekly schedule."""
    with conn.cursor() as cur:
        # A game counts as stored only when both its skater and goalie lines are present.
        cur.execute(
            """SELECT game_id FROM skater_game WHERE season_id = %(s)s
               INTERSECT SELECT game_id FROM goalie_game WHERE season_id = %(s)s""",
            {"s": config.SEASON_ID},
        )
        known = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT max(game_date) FROM skater_game WHERE season_id = %s", (config.SEASON_ID,))
        last = cur.fetchone()[0]
        # Stored games missing goalie lines (from before goalies were tracked) need a backfill.
        cur.execute(
            """SELECT min(game_date) FROM skater_game
               WHERE season_id = %s AND game_id NOT IN (SELECT game_id FROM goalie_game)""",
            (config.SEASON_ID,),
        )
        unfilled = cur.fetchone()[0]

    today = date.today()
    if last:
        # Rewind a couple of weeks so games that weren't final last time get picked up.
        start = min(last - timedelta(days=14), unfilled or last)
    else:
        start = date.fromisoformat(get_json(f"{config.WEB_API}/schedule/{today}")["regularSeasonStartDate"])

    todo, cursor = [], start
    while cursor <= today:
        week = get_json(f"{config.WEB_API}/schedule/{cursor}")
        for day in week["gameWeek"]:
            for g in day["games"]:
                if (g["gameType"] == config.GAME_TYPE and g["gameState"] in FINAL_STATES
                        and g["id"] not in known):
                    todo.append(g["id"])
        nxt = week.get("nextStartDate")
        if not nxt:
            break
        cursor = date.fromisoformat(nxt)
    return sorted(set(todo))


def fetch_boxscore(game_id):
    box = get_json(f"{config.WEB_API}/gamecenter/{game_id}/boxscore")
    time.sleep(0.25)  # stay well under the API's rate limit
    return game_id, box


def box_rows(game_id, box):
    """One skater_game row per skater who appeared in the game."""
    rows = []
    for side, other in (("homeTeam", "awayTeam"), ("awayTeam", "homeTeam")):
        team, opp = box[side]["abbrev"], box[other]["abbrev"]
        stats = box["playerByGameStats"][side]
        for p in stats["forwards"] + stats["defense"]:
            rows.append((
                p["playerId"], config.SEASON_ID, game_id, box["gameDate"], team, opp,
                side == "homeTeam", p["goals"], p["assists"], p["points"], p.get("sog"),
                p.get("plusMinus"), p.get("pim"), toi_to_sec(p.get("toi")), p.get("hits"),
                p.get("blockedShots"), p.get("takeaways"), p.get("giveaways"),
            ))
    return rows


LINES_VERSION = 2  # bump when the on-ice computation gains new outputs
MIN_SHIFT_COVERAGE = 0.95  # below this, a game's shift data is treated as unusable


def fetch_html_shifts(game_id, pbp):
    """Shift rows rebuilt from the NHL's HTML time-on-ice reports (home and visitor)."""
    pages = []
    for kind in ("TH", "TV"):
        r = session.get(html_shifts.report_url(game_id, kind), headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        pages.append(r.text)
        time.sleep(0.3)
    return html_shifts.shift_rows(
        pages[0], pages[1], pbp["rosterSpots"], pbp["homeTeam"]["id"], pbp["awayTeam"]["id"]
    )


def fetch_onice_inputs(game_id):
    """(game_id, play-by-play, shift rows, source, coverage), preferring the stats API and
    falling back to the HTML reports when the API's shift chart is missing or incomplete."""
    pbp = get_json(f"{config.WEB_API}/gamecenter/{game_id}/play-by-play")
    time.sleep(0.3)
    rows = get_json(f"{config.STATS_API}/shiftcharts", limit=-1, cayenneExp=f"gameId={game_id}")["data"]
    time.sleep(0.3)
    cov = corsi.coverage(pbp["plays"], rows)
    if cov >= MIN_SHIFT_COVERAGE:
        return game_id, pbp, rows, "api", cov
    try:
        html_rows = fetch_html_shifts(game_id, pbp)
        html_cov = corsi.coverage(pbp["plays"], html_rows)
        if html_cov > cov:
            return game_id, pbp, html_rows, "html", html_cov
    except requests.RequestException as e:
        print(f"  game {game_id}: HTML shift reports unavailable ({e})")
    return game_id, pbp, rows, "api", cov


def onice_xg(shots, shift_rows, skater_ids):
    """{player_id: [xG for, xG against]} at 5v5: each attempt's xG is credited to every skater on the ice."""
    spans, team_of = corsi.parse_shifts(shift_rows)
    onice = {pid: [0.0, 0.0] for pid in skater_ids}
    for r in shots:
        if r["xg"] is None or r["situation"] != corsi.FIVE_ON_FIVE:
            continue
        for pid, sp in spans.items():
            if pid in onice and corsi.on_ice(sp, r["time_sec"]):
                onice[pid][0 if team_of[pid] == r["team_id"] else 1] += r["xg"]
    return onice


def store_shots(cur, game_id, pbp, shift_rows, skater_ids):
    """Every shot attempt with its xG, plus each skater's 5v5 on-ice xG for/against."""
    abbrev = {pbp["homeTeam"]["id"]: pbp["homeTeam"]["abbrev"], pbp["awayTeam"]["id"]: pbp["awayTeam"]["abbrev"]}
    rows = shotlib.extract_shots(pbp)
    for r in rows:
        r["xg"] = shotlib.xg(r)
    cur.execute("DELETE FROM shot WHERE game_id = %s", (game_id,))
    cur.executemany(
        """INSERT INTO shot (game_id, event_id, season_id, period, time_sec, team, opponent, shooter_id, goalie_id,
                             kind, shot_type, x, y, distance, angle, strength, situation, empty_net, rebound, xg)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (game_id, event_id) DO NOTHING""",
        [(game_id, r["event_id"], config.SEASON_ID, r["period"], r["time_sec"], abbrev[r["team_id"]],
          abbrev[pbp["awayTeam"]["id"] if r["is_home"] else pbp["homeTeam"]["id"]], r["shooter_id"],
          r["goalie_id"], r["kind"], r["shot_type"], r["x"], r["y"], r["distance"], r["angle"],
          r["strength"], r["situation"], r["empty_net"], r["rebound"], r["xg"]) for r in rows if r["event_id"] is not None],
    )
    onice = onice_xg(rows, shift_rows, skater_ids)
    cur.executemany(
        "UPDATE skater_game_onice SET xgf = %s, xga = %s WHERE player_id = %s AND game_id = %s",
        [(v[0], v[1], pid, game_id) for pid, v in onice.items()],
    )


def store_lines(cur, game_id, pbp, shift_rows, skater_ids):
    """Per-player 5v5 time plus the pair and forward-line tables for one game."""
    result = corsi.game_lines(pbp["plays"], shift_rows, pbp["rosterSpots"])
    abbrev = {pbp["homeTeam"]["id"]: pbp["homeTeam"]["abbrev"], pbp["awayTeam"]["id"]: pbp["awayTeam"]["abbrev"]}
    cur.executemany(
        "UPDATE skater_game_onice SET toi_5v5_sec = %s WHERE player_id = %s AND game_id = %s",
        [(result["toi"].get(pid, 0), pid, game_id) for pid in skater_ids],
    )
    cur.execute("DELETE FROM line_game WHERE game_id = %s", (game_id,))
    cur.execute("DELETE FROM pair_game WHERE game_id = %s", (game_id,))
    cur.executemany(
        "INSERT INTO line_game (game_id, team, p1, p2, p3, toi_sec, cf, ca, gf, ga) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        [(game_id, abbrev[k[0]], *k[1:], *v) for k, v in result["trios"].items() if v[0] > 0],
    )
    cur.executemany(
        "INSERT INTO pair_game (game_id, team, p1, p2, toi_sec, cf, ca, gf, ga) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        [(game_id, abbrev[k[0]], *k[1:], *v) for k, v in result["pairs"].items() if v[0] > 0],
    )


def ingest_onice(conn):
    """Per-game 5v5 Corsi/Fenwick for every skater, where the NHL has published shift data."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT g.game_id FROM skater_game g
            LEFT JOIN game_shift_status s USING (game_id)
            WHERE g.season_id = %s AND (
                s.game_id IS NULL
                OR (s.has_shifts AND s.lines_version < %s)
                OR (NOT s.has_shifts AND s.checked_at < now() - interval '12 hours'
                    AND g.game_date > current_date - 30))
            ORDER BY g.game_id
            """,
            (config.SEASON_ID, LINES_VERSION),
        )
        todo = [r[0] for r in cur.fetchall()]
        skaters = {}
        cur.execute("SELECT game_id, player_id FROM skater_game WHERE season_id = %s", (config.SEASON_ID,))
        for game_id, pid in cur.fetchall():
            skaters.setdefault(game_id, []).append(pid)
    print(f"on-ice: processing {len(todo)} games")

    missing = 0
    with ThreadPoolExecutor(max_workers=2) as pool, conn.cursor() as cur:
        for i, (game_id, pbp, shift_rows, source, cov) in enumerate(pool.map(fetch_onice_inputs, todo), 1):
            usable = cov >= MIN_SHIFT_COVERAGE
            if usable:
                totals = corsi.game_corsi(pbp["plays"], shift_rows)
                zero = dict(cf=0, ca=0, ff=0, fa=0, gf=0, ga=0)
                cur.executemany(
                    """INSERT INTO skater_game_onice (player_id, game_id, season_id, cf, ca, ff, fa, gf, ga)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (player_id, game_id) DO UPDATE SET
                           cf=EXCLUDED.cf, ca=EXCLUDED.ca, ff=EXCLUDED.ff, fa=EXCLUDED.fa,
                           gf=EXCLUDED.gf, ga=EXCLUDED.ga""",
                    [(pid, game_id, config.SEASON_ID, *(totals.get(pid, zero)[k] for k in ("cf", "ca", "ff", "fa", "gf", "ga")))
                     for pid in skaters[game_id]],
                )
                store_lines(cur, game_id, pbp, shift_rows, skaters[game_id])
                store_shots(cur, game_id, pbp, shift_rows, skaters[game_id])
            else:
                missing += 1
            cur.execute(
                """INSERT INTO game_shift_status (game_id, has_shifts, coverage, source, lines_version)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (game_id) DO UPDATE SET has_shifts=EXCLUDED.has_shifts,
                       coverage=EXCLUDED.coverage, source=EXCLUDED.source,
                       lines_version=EXCLUDED.lines_version, checked_at=now()""",
                (game_id, usable, cov, source if usable else None, LINES_VERSION if usable else 0),
            )
            conn.commit()
            if i % 25 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    conn.execute("""UPDATE skater_game_onice o SET team = g.team FROM skater_game g
                    WHERE g.player_id = o.player_id AND g.game_id = o.game_id AND o.team IS NULL""")
    conn.commit()
    print(f"on-ice: {len(todo) - missing} games stored, {missing} without usable shift data")


def onice_rows(game_id, season_id, pbp, shift_rows, skater_ids):
    """One skater_game_onice row per skater for a game, computed without storing shots or lines:
    5v5 Corsi/Fenwick, goals, xG for/against, 5v5 time and the player's team."""
    totals = corsi.game_corsi(pbp["plays"], shift_rows)
    shots = shotlib.extract_shots(pbp)
    for r in shots:
        r["xg"] = shotlib.xg(r)
    xg = onice_xg(shots, shift_rows, skater_ids)
    toi = corsi.game_lines(pbp["plays"], shift_rows, pbp["rosterSpots"])["toi"]
    abbrev = {pbp["homeTeam"]["id"]: pbp["homeTeam"]["abbrev"], pbp["awayTeam"]["id"]: pbp["awayTeam"]["abbrev"]}
    team = {r["playerId"]: abbrev.get(r["teamId"]) for r in pbp["rosterSpots"]}
    zero = dict(cf=0, ca=0, ff=0, fa=0, gf=0, ga=0)
    return [(pid, game_id, season_id, *(totals.get(pid, zero)[k] for k in ("cf", "ca", "ff", "fa", "gf", "ga")),
             toi.get(pid, 0), xg[pid][0], xg[pid][1], team.get(pid)) for pid in skater_ids]


def backfill_onice(conn, seasons, limit=None):
    """On-ice stats for past seasons' games (from skater_game_hist), so defensive impact can be compared
    across seasons. Resumable: games already checked (game_shift_status) are skipped. Slow by design,
    about two requests per game at the NHL's rate limits; run it by hand, not in the nightly job."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT h.game_id, h.season_id, array_agg(h.player_id) FROM skater_game_hist h
               LEFT JOIN game_shift_status s USING (game_id)
               WHERE h.season_id = ANY(%s) AND s.game_id IS NULL
               GROUP BY h.game_id, h.season_id ORDER BY h.season_id, h.game_id""", (seasons,))
        todo = cur.fetchall()
    if limit:
        todo = todo[:limit]
    print(f"on-ice backfill: {len(todo)} games to process", flush=True)
    info = {game_id: (season_id, ids) for game_id, season_id, ids in todo}
    stored = unusable = 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=2) as pool, conn.cursor() as cur:
        for i, (game_id, pbp, shift_rows, source, cov) in enumerate(pool.map(fetch_onice_inputs, [t[0] for t in todo]), 1):
            season_id, ids = info[game_id]
            usable = cov >= MIN_SHIFT_COVERAGE
            if usable:
                cur.executemany(
                    """INSERT INTO skater_game_onice (player_id, game_id, season_id, cf, ca, ff, fa, gf, ga,
                                                      toi_5v5_sec, xgf, xga, team)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (player_id, game_id) DO UPDATE SET cf=EXCLUDED.cf, ca=EXCLUDED.ca, ff=EXCLUDED.ff,
                           fa=EXCLUDED.fa, gf=EXCLUDED.gf, ga=EXCLUDED.ga, toi_5v5_sec=EXCLUDED.toi_5v5_sec,
                           xgf=EXCLUDED.xgf, xga=EXCLUDED.xga, team=EXCLUDED.team""",
                    onice_rows(game_id, season_id, pbp, shift_rows, ids))
                stored += 1
            else:
                unusable += 1
            cur.execute(
                """INSERT INTO game_shift_status (game_id, has_shifts, coverage, source, lines_version)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (game_id) DO UPDATE SET has_shifts=EXCLUDED.has_shifts, coverage=EXCLUDED.coverage,
                       source=EXCLUDED.source, lines_version=EXCLUDED.lines_version, checked_at=now()""",
                (game_id, usable, cov, source if usable else None, 0))  # lines_version 0: no line tables for these games
            conn.commit()
            if i % 25 == 0:
                rate = i / (time.time() - started)
                print(f"  {i}/{len(todo)} ({stored} stored, {unusable} unusable, {(len(todo) - i) / rate / 60:.0f} min left)", flush=True)
    print(f"on-ice backfill: {stored} games stored, {unusable} without usable shift data")


def goalie_rows(game_id, box):
    """One goalie_game row per goalie who actually played (backups who sat have 0 ice time)."""
    rows = []
    for side, other in (("homeTeam", "awayTeam"), ("awayTeam", "homeTeam")):
        team, opp = box[side]["abbrev"], box[other]["abbrev"]
        for p in box["playerByGameStats"][side].get("goalies", []):
            toi = toi_to_sec(p.get("toi"))
            if not toi:
                continue
            rows.append((
                p["playerId"], config.SEASON_ID, game_id, box["gameDate"], team, opp,
                side == "homeTeam", p.get("starter"), p.get("decision"), p.get("shotsAgainst"),
                p.get("saves"), p.get("goalsAgainst"), toi, p.get("evenStrengthGoalsAgainst"),
                p.get("powerPlayGoalsAgainst"), p.get("shorthandedGoalsAgainst"),
            ))
    return rows


def ingest_games(conn):
    """Store every skater's line for each finished game: one boxscore request per game."""
    todo = schedule_final_game_ids(conn)
    print(f"games: fetching {len(todo)} boxscores")

    with ThreadPoolExecutor(max_workers=2) as pool, conn.cursor() as cur:
        for i, (game_id, box) in enumerate(pool.map(fetch_boxscore, todo), 1):
            cur.executemany(
                """
                INSERT INTO skater_game (player_id, season_id, game_id, game_date, team,
                    opponent, is_home, goals, assists, points, shots, plus_minus, pim,
                    toi_sec, hits, blocked_shots, takeaways, giveaways)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (player_id, game_id) DO UPDATE SET
                    goals=EXCLUDED.goals, assists=EXCLUDED.assists, points=EXCLUDED.points,
                    shots=EXCLUDED.shots, plus_minus=EXCLUDED.plus_minus, pim=EXCLUDED.pim,
                    toi_sec=EXCLUDED.toi_sec, hits=EXCLUDED.hits,
                    blocked_shots=EXCLUDED.blocked_shots, takeaways=EXCLUDED.takeaways,
                    giveaways=EXCLUDED.giveaways
                """,
                box_rows(game_id, box),
            )
            cur.executemany(
                """
                INSERT INTO goalie_game (player_id, season_id, game_id, game_date, team, opponent,
                    is_home, started, decision, shots_against, saves, goals_against, toi_sec,
                    ev_goals_against, pp_goals_against, sh_goals_against)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (player_id, game_id) DO UPDATE SET
                    started=EXCLUDED.started, decision=EXCLUDED.decision,
                    shots_against=EXCLUDED.shots_against, saves=EXCLUDED.saves,
                    goals_against=EXCLUDED.goals_against, toi_sec=EXCLUDED.toi_sec,
                    ev_goals_against=EXCLUDED.ev_goals_against,
                    pp_goals_against=EXCLUDED.pp_goals_against,
                    sh_goals_against=EXCLUDED.sh_goals_against
                """,
                goalie_rows(game_id, box),
            )
            conn.commit()  # a game is stored all-or-nothing, so re-runs never see half a game
            if i % 25 == 0:
                print(f"  {i}/{len(todo)}", flush=True)


FIRST_NHL_SEASON = 1917
NO_SEASON = {20042005}  # the lockout year: nothing to fetch
SEASON_HISTORY_REFRESH = 2  # finished seasons never change; only the latest few are fetched again


def ingest_career_seasons(conn):
    """Every skater's regular-season line for every NHL season: one request per season."""
    have = {r[0] for r in conn.execute("SELECT DISTINCT season_id FROM career_season")}
    recent = {config.SEASON_ID - 10001 * i for i in range(SEASON_HISTORY_REFRESH)}
    todo = [s for s in (y * 10000 + y + 1 for y in range(FIRST_NHL_SEASON, config.SEASON_ID // 10000 + 1))
            if s not in NO_SEASON and (s not in have or s in recent)]
    for season in todo:
        data = get_json(f"{config.STATS_API}/skater/summary", limit=-1,
                        cayenneExp=f"seasonId={season} and gameTypeId={config.GAME_TYPE}")
        rows = [(r["playerId"], season, r.get("teamAbbrevs"), r["gamesPlayed"] or 0,
                 r["goals"] or 0, r["assists"] or 0, r["points"] or 0) for r in data["data"]]
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO career_season (player_id, season_id, team, games_played, goals, assists, points)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (player_id, season_id) DO UPDATE SET team=EXCLUDED.team,
                       games_played=EXCLUDED.games_played, goals=EXCLUDED.goals,
                       assists=EXCLUDED.assists, points=EXCLUDED.points""",
                rows)
        conn.commit()
        time.sleep(0.5)
    print(f"career seasons: fetched {len(todo)} season(s)")


FIRST_TRACKED_SEASON = 2005  # hits, blocks, takeaways and giveaways were not counted before 2005-06


def ingest_defense_seasons(conn):
    """Hits, blocks, takeaways and giveaways for every skater-season since tracking began."""
    have = {r[0] for r in conn.execute("SELECT DISTINCT season_id FROM defense_season")}
    recent = {config.SEASON_ID - 10001 * i for i in range(SEASON_HISTORY_REFRESH)}
    todo = [s for s in (y * 10000 + y + 1 for y in range(FIRST_TRACKED_SEASON, config.SEASON_ID // 10000 + 1))
            if s not in have or s in recent]
    for season in todo:
        data = get_json(f"{config.STATS_API}/skater/realtime", limit=-1,
                        cayenneExp=f"seasonId={season} and gameTypeId={config.GAME_TYPE}")
        rows = [(r["playerId"], season, r.get("teamAbbrevs"), r.get("positionCode"), r["gamesPlayed"] or 0,
                 r.get("timeOnIcePerGame"), r["hits"] or 0, r["blockedShots"] or 0,
                 r["takeaways"] or 0, r["giveaways"] or 0) for r in data["data"]]
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO defense_season (player_id, season_id, team, position, games_played,
                       toi_per_game_sec, hits, blocked_shots, takeaways, giveaways)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (player_id, season_id) DO UPDATE SET team=EXCLUDED.team,
                       position=EXCLUDED.position, games_played=EXCLUDED.games_played,
                       toi_per_game_sec=EXCLUDED.toi_per_game_sec, hits=EXCLUDED.hits,
                       blocked_shots=EXCLUDED.blocked_shots, takeaways=EXCLUDED.takeaways,
                       giveaways=EXCLUDED.giveaways""",
                rows)
        conn.commit()
        time.sleep(0.5)
    print(f"defense seasons: fetched {len(todo)} season(s)")


def ingest_era_adjusted(conn):
    """Era-adjusted career goals, assists and points for every skater (regular season), from career_season."""
    rows = era.load_rows(conn)
    rates = era.league_rates(rows)
    fac = era.factors(rates, era.reference_rates(rates, config.SEASON_ID - 10001))
    adj = era.adjust_careers(rows, fac)
    with conn.cursor() as cur:
        cur.executemany(
            """UPDATE career_skater SET adj_goals = %s, adj_assists = %s, adj_points = %s, adj_points_per_game = %s
               WHERE player_id = %s AND game_type = 2""",
            [(a["adj_goals"], a["adj_assists"], a["adj_points"], a["adj_points_per_game"], pid) for pid, a in adj.items()])
    conn.commit()
    print(f"era-adjusted: {len(adj)} skaters")


def main():
    with psycopg.connect(config.DATABASE_URL) as conn:
        conn.execute((Path(__file__).parent / "schema.sql").read_text())
        conn.commit()
        ingest_season(conn)
        ingest_teams(conn)
        ingest_schedule(conn)
        ingest_goalie_season(conn)
        ingest_games(conn)
        ingest_onice(conn)
        ingest_alltime(conn)
        ingest_career_seasons(conn)
        ingest_defense_seasons(conn)
        ingest_era_adjusted(conn)
        ingest_history(conn)


if __name__ == "__main__":
    if sys.argv[1:2] == ["backfill-onice"]:
        # python ingest.py backfill-onice [20222023,20232024,...] [--limit N]
        args = sys.argv[2:]
        limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
        wanted = [a for a in args if a.isdigit() or "," in a]
        seasons = [int(x) for x in wanted[0].split(",")] if wanted else [config.SEASON_ID - 10001 * i for i in range(1, 5)]
        with psycopg.connect(config.DATABASE_URL) as conn:
            conn.execute((Path(__file__).parent / "schema.sql").read_text())
            conn.commit()
            backfill_onice(conn, seasons, limit)
    else:
        main()
