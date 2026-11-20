"""Helpers and queries shared by more than one route module."""
from datetime import datetime, timedelta, timezone
import functools
import time

from fastapi import HTTPException
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import requests

import bestseasons
import config
import fatigue
import goaliemap
import luck_db
import matchups_db
import probable_goalies
import streaming

_TTL_MAX_ENTRIES = 64


def ttl_cached(seconds):
    """Reuses an endpoint's answer for `seconds`, per set of arguments. For the heavy read-only pages whose data only changes when the
    ingest runs (nightly) or a game ends: a user who has just seen the answer shouldn't make everyone after them wait for it again. Errors
    are not kept. The table is bounded because the arguments come from the URL."""
    def wrap(fn):
        store = {}

        @functools.wraps(fn)
        def inner(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            hit = store.get(key)
            if hit and now - hit[0] < seconds:
                return hit[1]
            value = fn(*args, **kwargs)
            if len(store) >= _TTL_MAX_ENTRIES:
                store.clear()
            store[key] = (now, value)
            return value
        return inner
    return wrap


SKATERS_SQL = """
WITH ranked AS (
    SELECT player_id, points, hits, blocked_shots, takeaways, giveaways, toi_sec,
           row_number() OVER (PARTITION BY player_id ORDER BY game_date DESC) AS rn
    FROM skater_game WHERE season_id = %(season)s
),
onice_ranked AS (
    SELECT o.player_id, o.cf, o.ca, o.ff, o.fa, o.gf, o.ga,
           row_number() OVER (PARTITION BY o.player_id ORDER BY g.game_date DESC, g.game_id DESC) AS rn
    FROM skater_game_onice o JOIN skater_game g USING (player_id, game_id)
    WHERE o.season_id = %(season)s
),
onice_recent AS (
    SELECT player_id, count(*) AS games, sum(cf) AS cf, sum(ca) AS ca, sum(ff) AS ff,
           sum(fa) AS fa, sum(gf) AS gf, sum(ga) AS ga
    FROM onice_ranked WHERE rn <= %(window)s GROUP BY player_id
),
ixg AS (
    SELECT shooter_id AS player_id, sum(xg) AS ixg,
           count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals
    FROM shot WHERE season_id = %(season)s AND shooter_id IS NOT NULL GROUP BY shooter_id
),
assist_split AS (
    -- primary (first) and secondary (second) assists, from who assisted each goal (see ingest_play_by_play)
    SELECT player_id, count(*) FILTER (WHERE rank = 1) AS primary_assists, count(*) FILTER (WHERE rank = 2) AS secondary_assists
    FROM (SELECT assist1_id AS player_id, 1 AS rank FROM goal_assist WHERE season_id = %(season)s
          UNION ALL SELECT assist2_id, 2 FROM goal_assist WHERE season_id = %(season)s) a
    WHERE player_id IS NOT NULL GROUP BY player_id
),
special_skater AS (
    -- shootout attempts and penalty shots taken (see ingest_play_by_play)
    SELECT shooter_id AS player_id,
           count(*) FILTER (WHERE kind = 'shootout') AS so_attempts, count(*) FILTER (WHERE kind = 'shootout' AND scored) AS so_goals,
           count(*) FILTER (WHERE kind = 'penalty_shot') AS ps_attempts, count(*) FILTER (WHERE kind = 'penalty_shot' AND scored) AS ps_goals
    FROM special_shot WHERE season_id = %(season)s AND shooter_id IS NOT NULL GROUP BY shooter_id
),
onice_xg AS (
    SELECT player_id, sum(xgf) AS xgf, sum(xga) AS xga
    FROM skater_game_onice WHERE season_id = %(season)s GROUP BY player_id
),
last_game AS (
    SELECT DISTINCT ON (player_id) player_id, team, game_date, game_id
    FROM skater_game WHERE season_id = %(season)s
    ORDER BY player_id, game_date DESC, game_id DESC
),
lineup_gap AS (
    -- team games played since the player's most recent appearance
    SELECT lg.player_id, count(DISTINCT tg.game_id) AS games_out, lg.game_date AS last_game_date
    FROM last_game lg
    JOIN skater_game tg ON tg.team = lg.team AND tg.season_id = %(season)s
     AND (tg.game_date, tg.game_id) > (lg.game_date, lg.game_id)
    GROUP BY lg.player_id, lg.game_date
),
recent AS (
    SELECT player_id, count(*) AS games, sum(points) AS points,
           sum(hits) AS hits, sum(blocked_shots) AS blocks,
           sum(takeaways) AS takeaways, sum(giveaways) AS giveaways,
           -- only count ice time from games whose defensive stats have been ingested
           sum(toi_sec) FILTER (WHERE hits IS NOT NULL) AS def_toi_sec
    FROM ranked WHERE rn <= %(window)s GROUP BY player_id
)
SELECT s.*,
       -- age as of today for the current season, and as of April 1 of the season's end for a past one
       date_part('year', age(LEAST(current_date, make_date(s.season_id %% 10000, 4, 1)), s.birth_date))::int AS age,
       (s.first_nhl_season = s.season_id) AS rookie,
       COALESCE(lgap.games_out, 0) AS games_out,
       lgap.last_game_date,
       (position(',' in s.team) > 0) AS traded,
       round(s.points::numeric / s.games_played * %(games)s, 1)::float AS point_pace,
       r.games AS recent_games, r.points AS recent_points,
       round(r.points::numeric / r.games * %(games)s, 1)::float AS recent_pace,
       round(r.hits::numeric / NULLIF(r.def_toi_sec, 0) * 3600, 1)::float AS recent_hits_per60,
       round(r.blocks::numeric / NULLIF(r.def_toi_sec, 0) * 3600, 1)::float AS recent_blocks_per60,
       round(r.takeaways::numeric / NULLIF(r.def_toi_sec, 0) * 3600, 1)::float AS recent_takeaways_per60,
       round(r.giveaways::numeric / NULLIF(r.def_toi_sec, 0) * 3600, 1)::float AS recent_giveaways_per60,
       -- NULL, not 0, for a season whose goals were never read for assisters (every season but this one)
       CASE WHEN has_assists.n THEN COALESCE(asp.primary_assists, 0) END AS primary_assists,
       CASE WHEN has_assists.n THEN COALESCE(asp.secondary_assists, 0) END AS secondary_assists,
       CASE WHEN has_assists.n THEN s.goals + COALESCE(asp.primary_assists, 0) END AS primary_points,
       -- even-strength goals for and against per 60 minutes on the ice
       round((s.ev_goals_for * 3600.0 / NULLIF(s.ev_toi_per_game * s.games_played, 0))::numeric, 2)::float AS ev_gf_per60,
       round((s.ev_goals_against * 3600.0 / NULLIF(s.ev_toi_per_game * s.games_played, 0))::numeric, 2)::float AS ev_ga_per60,
       -- NULL, not 0, for a season whose play-by-play was never read for these (every season but this one)
       CASE WHEN has_special.n THEN COALESCE(sp.so_attempts, 0) END AS so_attempts, CASE WHEN has_special.n THEN COALESCE(sp.so_goals, 0) END AS so_goals,
       round(sp.so_goals::numeric / NULLIF(sp.so_attempts, 0), 3)::float AS so_pct,
       CASE WHEN has_special.n THEN COALESCE(sp.ps_attempts, 0) END AS ps_attempts, CASE WHEN has_special.n THEN COALESCE(sp.ps_goals, 0) END AS ps_goals,
       round(ix.ixg::numeric, 2)::float AS ixg,
       round((ix.model_goals - ix.ixg)::numeric, 2)::float AS goals_minus_ixg,
       round(ox.xgf::numeric, 2)::float AS xgf, round(ox.xga::numeric, 2)::float AS xga,
       round(ox.xgf::numeric / NULLIF((ox.xgf + ox.xga)::numeric, 0), 4)::float AS xgf_pct,
       oi.games AS recent_onice_games,
       oi.cf AS recent_cf, oi.ca AS recent_ca,
       round(oi.cf::numeric / NULLIF(oi.cf + oi.ca, 0), 4)::float AS recent_cf_pct,
       round(oi.ff::numeric / NULLIF(oi.ff + oi.fa, 0), 4)::float AS recent_ff_pct,
       round(oi.gf::numeric / NULLIF(oi.gf + oi.ga, 0), 4)::float AS recent_gf_pct,
       -- change from the season-long Corsi share (positive = trending up)
       round(oi.cf::numeric / NULLIF(oi.cf + oi.ca, 0) - s.sat_pct::numeric, 4)::float AS cf_pct_trend,
       -- NHL EDGE tracking (NULL for players the NHL hasn't tracked this season)
       ed.top_shot_mph, ed.avg_shot_mph, ed.top_speed_mph, ed.bursts_22_plus,
       coalesce(ed.shots_90_100, 0) + coalesce(ed.shots_100_plus, 0) AS hard_shots,
       round((ed.distance_miles / NULLIF(s.games_played, 0))::numeric, 2)::float AS distance_per_game,
       ed.distance_miles, ed.oz_pct AS edge_oz_pct, ed.dz_pct AS edge_dz_pct, ed.hd_sog
FROM skater_season s
LEFT JOIN recent r USING (player_id)
LEFT JOIN onice_recent oi USING (player_id)
LEFT JOIN lineup_gap lgap USING (player_id)
LEFT JOIN ixg ix USING (player_id)
LEFT JOIN assist_split asp USING (player_id)
LEFT JOIN special_skater sp USING (player_id)
CROSS JOIN (SELECT EXISTS (SELECT 1 FROM special_shot WHERE season_id = %(season)s) AS n) has_special
CROSS JOIN (SELECT EXISTS (SELECT 1 FROM goal_assist WHERE season_id = %(season)s) AS n) has_assists
LEFT JOIN onice_xg ox USING (player_id)
LEFT JOIN edge_skater_season ed ON ed.player_id = s.player_id AND ed.season_id = s.season_id AND ed.has_data
WHERE s.season_id = %(season)s AND s.games_played > 0
ORDER BY s.points DESC, s.games_played ASC
"""


def _stored_season(conn, table, season):
    """The season to show: the current one when none is asked for, else a past season that has stats stored (404 if not)."""
    if season is None or season == config.SEASON_ID:
        return config.SEASON_ID
    if conn.execute(f"SELECT 1 FROM {table} WHERE season_id = %s LIMIT 1", (season,)).fetchone() is None:
        raise HTTPException(404, "No stats stored for that season")
    return season


TEAMS_SQL = """
SELECT t.*,
       round(t.points::numeric / NULLIF(t.games_played, 0) * %(games)s, 1)::float AS points_pace,
       round(t.wins::numeric / NULLIF(t.games_played, 0) * %(games)s, 1)::float AS wins_pace,
       round(t.goals_for::numeric / NULLIF(t.games_played, 0), 2)::float AS goals_for_pg,
       round(t.goals_against::numeric / NULLIF(t.games_played, 0), 2)::float AS goals_against_pg
FROM team_season t
WHERE t.season_id = %(season)s
ORDER BY t.league_rank
"""


GOALIES_SQL = """
WITH league AS (
    SELECT sum(saves)::float / NULLIF(sum(shots_against), 0) AS sv_pct
    FROM goalie_season WHERE season_id = %(season)s
),
ranked AS (
    SELECT player_id, shots_against, saves, goals_against, toi_sec,
           row_number() OVER (PARTITION BY player_id ORDER BY game_date DESC, game_id DESC) AS rn
    FROM goalie_game WHERE season_id = %(season)s
),
recent AS (
    SELECT player_id, count(*) AS games, sum(saves) AS saves, sum(shots_against) AS shots,
           sum(goals_against) AS goals, sum(toi_sec) AS toi
    FROM ranked WHERE rn <= %(window)s GROUP BY player_id
),
special_goalie AS (
    -- shootout and penalty-shot shots faced (a miss wide is not faced) and saved
    SELECT goalie_id AS player_id,
           count(*) FILTER (WHERE kind = 'shootout' AND on_goal) AS so_faced, count(*) FILTER (WHERE kind = 'shootout' AND on_goal AND NOT scored) AS so_saves,
           count(*) FILTER (WHERE kind = 'penalty_shot' AND on_goal) AS ps_faced, count(*) FILTER (WHERE kind = 'penalty_shot' AND on_goal AND NOT scored) AS ps_saves
    FROM special_shot WHERE season_id = %(season)s AND goalie_id IS NOT NULL GROUP BY goalie_id
),
bad_starts AS (
    -- a start with a save percentage under .850 (the NHL publishes quality starts but not these)
    SELECT player_id, count(*) AS n FROM goalie_game
    WHERE season_id = %(season)s AND started AND shots_against > 0 AND saves::float / shots_against < 0.85 GROUP BY player_id
)
SELECT s.*,
       -- NULL, not 0, for a season without game-by-game rows (every season but this one)
       CASE WHEN has_games.n THEN COALESCE(b.n, 0) END AS really_bad_starts,
       CASE WHEN has_special.n THEN COALESCE(sg.so_faced, 0) END AS so_faced, CASE WHEN has_special.n THEN COALESCE(sg.so_saves, 0) END AS so_saves,
       round(sg.so_saves::numeric / NULLIF(sg.so_faced, 0), 3)::float AS so_sv_pct,
       CASE WHEN has_special.n THEN COALESCE(sg.ps_faced, 0) END AS ps_faced, CASE WHEN has_special.n THEN COALESCE(sg.ps_saves, 0) END AS ps_saves,
       -- goals saved above average: goals a league-average goalie would have allowed minus actual
       round((s.shots_against * (1 - l.sv_pct) - s.goals_against)::numeric, 2)::float AS gsaa,
       round(((s.shots_against * (1 - l.sv_pct) - s.goals_against) / NULLIF(s.toi_sec, 0) * 3600)::numeric, 2)::float AS gsaa_per60,
       r.games AS recent_games,
       round((r.saves::numeric / NULLIF(r.shots, 0)), 3)::float AS recent_save_pct,
       round((r.goals * 3600.0 / NULLIF(r.toi, 0))::numeric, 2)::float AS recent_gaa,
       round((r.shots * (1 - l.sv_pct) - r.goals)::numeric, 2)::float AS recent_gsaa,
       round(l.sv_pct::numeric, 4)::float AS league_sv_pct
FROM goalie_season s
CROSS JOIN league l
CROSS JOIN (SELECT EXISTS (SELECT 1 FROM goalie_game WHERE season_id = %(season)s) AS n) has_games
LEFT JOIN recent r USING (player_id)
LEFT JOIN bad_starts b USING (player_id)
LEFT JOIN special_goalie sg USING (player_id)
CROSS JOIN (SELECT EXISTS (SELECT 1 FROM special_shot WHERE season_id = %(season)s) AS n) has_special
WHERE s.season_id = %(season)s AND s.games_played > 0
ORDER BY s.wins DESC, s.games_played ASC
"""


def _goalie_params():
    return {"season": config.SEASON_ID, "window": config.RECENT_GOALIE_GAMES}


CAREER_TTL = timedelta(hours=24)


def career_cache_stale(fetched_at, now, season_updated_at=None, ttl=CAREER_TTL):
    """Whether a cached NHL career payload should be fetched again: it is older than the TTL, or the player's current-season
    stats were updated (by the nightly ingest, after a game) since it was fetched. Without the second rule the season row of
    the career table lagged the rest of the page by up to a day after every game."""
    if now - fetched_at >= ttl:
        return True
    return season_updated_at is not None and season_updated_at > fetched_at


def _fetch_landing(player_id):
    r = requests.get(f"{config.WEB_API}/player/{player_id}/landing", timeout=15)
    if r.status_code == 404:
        raise HTTPException(404, "Player not found")
    r.raise_for_status()
    return r.json()


def _career_payload(conn, player_id, *, allow_fetch=True):
    """Raw NHL landing payload from the Postgres cache, refreshed when stale. None if unavailable."""
    cached = conn.execute(
        "SELECT payload, fetched_at FROM player_career WHERE player_id = %s", (player_id,)
    ).fetchone()
    if cached:
        newest = conn.execute(
            """SELECT max(updated_at) AS t FROM (
                   SELECT updated_at FROM skater_season WHERE season_id = %(s)s AND player_id = %(p)s
                   UNION ALL SELECT updated_at FROM goalie_season WHERE season_id = %(s)s AND player_id = %(p)s) x""",
            {"s": config.SEASON_ID, "p": player_id}).fetchone()
        if not career_cache_stale(cached["fetched_at"], datetime.now(timezone.utc), newest and newest["t"]):
            return cached["payload"]
    if not allow_fetch:
        return cached["payload"] if cached else None
    try:
        raw = _fetch_landing(player_id)
    except requests.RequestException:
        return cached["payload"] if cached else None  # stale beats nothing
    conn.execute(
        """INSERT INTO player_career (player_id, payload, fetched_at) VALUES (%s, %s, now())
           ON CONFLICT (player_id) DO UPDATE SET payload = EXCLUDED.payload, fetched_at = now()""",
        (player_id, Jsonb(raw)),
    )
    return raw


def _goalie_plans(teams, days):
    """Start-probability plans for the given teams' games over the next `days` days (today first, Eastern).

    Returns (today, end, plans, teams_with_history): plans maps a team to its upcoming games, each with the distribution of
    who might start. Games already played or under way anchor the chain (their starter is known); later games are chained
    from them, so a back-to-back after an uncertain starter is a mix of both cases (see probable_goalies.py). The NHL
    boxscore is checked for confirmed starters close to game time, outside the database connection."""
    teams = list(teams)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        end = today + timedelta(days=days - 1)
        starts = conn.execute(
            """SELECT g.team, g.player_id, g.game_date, s.name FROM goalie_game g
               LEFT JOIN goalie_season s ON s.season_id = g.season_id AND s.player_id = g.player_id
               WHERE g.season_id = %s AND g.started AND g.team = ANY(%s) ORDER BY g.game_date DESC, g.game_id DESC""",
            (config.SEASON_ID, teams)).fetchall()
        games = conn.execute(
            """SELECT game_id, game_date, start_time, state, home, away FROM game
               WHERE season_id = %s AND game_date <= %s AND (home = ANY(%s) OR away = ANY(%s)) ORDER BY game_date, game_id""",
            (config.SEASON_ID, end, teams, teams)).fetchall()
    by_team = {}
    for r in starts:
        by_team.setdefault(r["team"], []).append(r)
    b2b = repeats = 0  # league-wide repeat rate, as in the daily endpoint
    for rows in by_team.values():
        for newer, older in zip(rows, rows[1:]):
            if (newer["game_date"] - older["game_date"]).days == 1:
                b2b += 1
                repeats += newer["player_id"] == older["player_id"]
    p_repeat = probable_goalies.repeat_rate(b2b, repeats)

    plans = {}
    for team in teams:
        rows = by_team.get(team, [])
        recent = [(r["player_id"], r["name"] or "Unknown") for r in rows]
        prev_date = rows[0]["game_date"] if rows else None
        dist, prepend, plan = ({recent[0][0]: 1.0} if recent else {}), False, []
        for g in (g for g in games if team in (g["home"], g["away"]) and (prev_date is None or g["game_date"] > prev_date)):
            tired = prev_date is not None and (g["game_date"] - prev_date).days == 1
            known = _confirmed_starters(g).get(team)
            if known:
                dist, confirmed = {known[0]: 1.0}, True
            elif recent:
                dist, confirmed = probable_goalies.next_distribution(recent, dist, tired, p_repeat, prepend), False
            else:
                dist, confirmed = {}, False
            prepend, prev_date = True, g["game_date"]
            if g["game_date"] >= today and g["state"] not in ("OFF", "FINAL"):
                plan.append({"game_id": g["game_id"], "date": g["game_date"], "opponent": g["away"] if g["home"] == team else g["home"],
                             "home_game": g["home"] == team, "back_to_back": tired, "confirmed": confirmed, "dist": dict(dist)})
        plans[team] = plan
    return today, end, plans, set(by_team)


def _streaming_plan(days):
    """streaming_goalies' answer for a window of `days` days (also used for the rest of the season, see projections)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        teams, league = matchups_db.team_table(conn, config.SEASON_ID)
        goalies = conn.execute(
            "SELECT player_id, name, team FROM goalie_season WHERE season_id = %s", (config.SEASON_ID,)).fetchall()
        _, estimate = matchups_db.goalie_effects(conn, config.SEASON_ID, league.get("shots_pg"), league.get("goals_pg")) if league else (None, {})
        standings = conn.execute(
            "SELECT coalesce(sum(losses), 0) AS losses, coalesce(sum(ot_losses), 0) AS otl FROM team_season WHERE season_id = %s",
            (config.SEASON_ID,)).fetchone()
    if not teams:
        return {"from": None, "to": None, "league": {}, "goalies": []}
    otl_share = standings["otl"] / (standings["losses"] + standings["otl"]) if standings["losses"] + standings["otl"] else 0.23
    ratings = {t["team"]: t for t in teams}
    today, end, plans, _ = _goalie_plans(ratings, days)

    out = []
    for g in goalies:
        team = (g["team"] or "").split(",")[-1]
        own = ratings.get(team)
        games = []
        for p in plans.get(team, []):
            prob = p["dist"].get(g["player_id"], 0.0)
            opp = ratings.get(p["opponent"])
            if prob <= 0 or own is None or opp is None:
                continue
            line = streaming.goalie_game(own, opp, estimate.get(g["player_id"], 0.0), league, otl_share)
            games.append({"game_id": p["game_id"], "date": p["date"], "opponent": p["opponent"], "home_game": p["home_game"],
                          "back_to_back": p["back_to_back"], "confirmed": p["confirmed"], "probability": round(prob, 3),
                          "goalie_ratio": opp["goalie_ratio"], "goalie_label": opp["goalie_label"], "line": line})
        if games:
            out.append({"player_id": g["player_id"], "name": g["name"], "team": team, "games": games,
                        "expected_starts": round(sum(x["probability"] for x in games), 2)})
    return {"from": today, "to": end, "days": days, "league": league, "otl_share": otl_share, "goalies": out}


def _stints(rows):
    """Consecutive runs of games with one team. rows are ordered oldest first."""
    stints = []
    for r in rows:
        if not stints or stints[-1]["team"] != r["team"]:
            stints.append({"team": r["team"], "first_date": r["game_date"], "last_date": r["game_date"],
                           "gp": 0, "goals": 0, "assists": 0, "points": 0, "first_game": r["game_id"],
                           "last_game": r["game_id"]})
        s = stints[-1]
        s["last_date"], s["last_game"] = r["game_date"], r["game_id"]
        s["gp"] += 1
        for k in ("goals", "assists", "points"):
            s[k] += r.get(k) or 0
    return stints


def _offseason_from(conn, player_id, first_team_abbrev):
    """Full name of the team the player's last completed NHL season was with, if it differs."""
    raw = _career_payload(conn, player_id)
    if raw is None:
        return None
    prior = [s for s in raw.get("seasonTotals", [])
             if s.get("leagueAbbrev") == "NHL" and s.get("gameTypeId") == 2 and s["season"] < config.SEASON_ID]
    if not prior:
        return None
    last = max(s["season"] for s in prior)
    last_teams = {(s.get("teamName") or {}).get("default") for s in prior if s["season"] == last}
    row = conn.execute(
        "SELECT name FROM team_season WHERE season_id = %s AND abbrev = %s",
        (config.SEASON_ID, first_team_abbrev),
    ).fetchone()
    if not row or row["name"] in last_teams:
        return None
    return sorted(t for t in last_teams if t)[0] if last_teams else None


def _context(player_id, goalie):
    table = "goalie_game" if goalie else "skater_game"
    extra = "" if goalie else ", goals, assists, points"
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        games = conn.execute(
            f"SELECT game_id, game_date, team, opponent{extra} FROM {table} "
            "WHERE player_id = %s AND season_id = %s ORDER BY game_date, game_id",
            (player_id, config.SEASON_ID),
        ).fetchall()
        if not games:
            raise HTTPException(404, "No games for this player")
        stints = _stints(games)
        names = {r["abbrev"]: r["name"] for r in conn.execute(
            "SELECT abbrev, name FROM team_season WHERE season_id = %s", (config.SEASON_ID,)).fetchall()}
        moved_from = _offseason_from(conn, player_id, stints[0]["team"])
        rookie = None
        if not goalie:
            r = conn.execute(
                "SELECT (first_nhl_season = season_id) AS rookie FROM skater_season WHERE season_id = %s AND player_id = %s",
                (config.SEASON_ID, player_id)).fetchone()
            rookie = bool(r and r["rookie"])

        availability = None
        if not goalie:
            # Every game each of the player's teams played (any skater row for that team).
            team_games = conn.execute(
                """SELECT DISTINCT team, game_id, game_date, opponent FROM skater_game
                   WHERE season_id = %s AND team = ANY(%s) ORDER BY game_date, game_id""",
                (config.SEASON_ID, [s["team"] for s in stints]),
            ).fetchall()
            played = {g["game_id"] for g in games}
            missed = []
            for i, st in enumerate(stints):
                last = i == len(stints) - 1
                for tg in team_games:
                    if tg["team"] != st["team"] or tg["game_id"] in played:
                        continue
                    # Within a stint, count gaps after the debut; for the current team also the
                    # games since the player's last appearance.
                    after_debut = (tg["game_date"], tg["game_id"]) > (st["first_date"], st["first_game"])
                    before_end = last or (tg["game_date"], tg["game_id"]) < (st["last_date"], st["last_game"])
                    if after_debut and before_end:
                        missed.append({"game_date": tg["game_date"], "opponent": tg["opponent"], "team": tg["team"]})
            current = stints[-1]
            out_streak = sum(
                1 for tg in team_games
                if tg["team"] == current["team"] and tg["game_id"] not in played
                and (tg["game_date"], tg["game_id"]) > (current["last_date"], current["last_game"])
            )
            first = stints[0]
            debut_after = sum(1 for tg in team_games if tg["team"] == first["team"]
                              and (tg["game_date"], tg["game_id"]) < (first["first_date"], first["first_game"]))
            availability = {
                "missed_games": len(missed),
                "missed": missed[-12:],
                "out_streak": out_streak,
                "debut_after_team_games": debut_after,
            }
    return {
        "traded": len(stints) > 1,
        "stints": [{**s, "team_name": names.get(s["team"])} for s in stints],
        "moved_from": moved_from,
        "rookie": rookie,
        "availability": availability,
    }


# --- Rest and back-to-backs ---------------------------------------------------------------------
_UTA = "CASE WHEN {c} = 'ARI' THEN 'UTA' ELSE {c} END"


def _team_games(conn, with_past=True):
    """Every stored team-game as one row per team: the previous seasons' from team_game_hist and this season's from game.
    Returns (past, current, games): `past` rows are results, `current` rows also cover games still to play (`done` marks
    the finished ones, which carry the result), `games` is this season's schedule as stored. with_past=False skips
    the previous seasons (`past` is then empty)."""
    past = [] if not with_past else conn.execute(
        f"""SELECT {_UTA.format(c='team')} AS team, {_UTA.format(c='opponent')} AS opponent, season_id, game_id, game_date,
                   points, wins, goals_for, goals_against, is_home
            FROM team_game_hist WHERE team IS NOT NULL AND opponent IS NOT NULL""").fetchall()
    games = conn.execute(
        """SELECT game_id, season_id, game_date, home, away, home_score, away_score, last_period, state
           FROM game WHERE season_id = %s""", (config.SEASON_ID,)).fetchall()
    current = []
    for g in games:
        for team, opp, home in ((g["home"], g["away"], True), (g["away"], g["home"], False)):
            row = {"team": team, "opponent": opp, "season_id": g["season_id"], "game_id": g["game_id"],
                   "game_date": g["game_date"], "is_home": home}
            if g["state"] in ("OFF", "FINAL") and g["home_score"] is not None:
                gf, ga = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
                row.update(goals_for=gf, goals_against=ga, wins=int(gf > ga),
                           points=2 if gf > ga else (1 if g["last_period"] != "REG" else 0), done=True)
            current.append(row)
    return past, current, games


_rest_gaps_cache = {"key": None, "gaps": None, "win": None}


def _rest_context(conn):
    """(gaps, kinds): {kind: goals-for gap} for the tired and edge situations (see fatigue.effects), recomputed only when
    another game has finished since the last call, and each current-season team-game's rest situation
    {(team, game_id): kind}."""
    _, current, _ = _team_games(conn, with_past=False)
    rest = fatigue.rest_days(current)
    kinds = {(r["team"], r["game_id"]): fatigue.kind(rest[r["team"], r["game_id"]], rest.get((r["opponent"], r["game_id"]), fatigue.FIRST_GAME_REST))
             for r in current}
    key = sum(1 for r in current if r.get("done"))
    if _rest_gaps_cache["key"] != key:
        past, current, _ = _team_games(conn)
        all_rest = fatigue.rest_days(past + current)
        eff = fatigue.effects(list(fatigue.classify(past + [r for r in current if r.get("done")], all_rest)))
        _rest_gaps_cache.update(key=key, gaps={k: eff[k]["goals_for"]["gap"] for k in ("tired", "edge")},
                                win={k: eff[k]["win_rate"]["gap"] for k in ("tired", "edge")})
    return _rest_gaps_cache["gaps"], kinds


# --- Probable goalies ---------------------------------------------------------------------------
# Starters the NHL has confirmed, read from the boxscore only near or after puck drop and cached briefly.
CONFIRM_LEAD = timedelta(hours=2)   # start looking this long before puck drop


CONFIRM_TTL = 60                    # seconds; finished games never change, so they are kept an hour


_confirm_cache = {}


def _confirmed_starters(game):
    now = datetime.now(timezone.utc)
    if game["state"] == "FUT" and (game["start_time"] is None or game["start_time"] - now > CONFIRM_LEAD):
        return {}
    hit = _confirm_cache.get(game["game_id"])
    final = game["state"] in ("FINAL", "OFF")
    if hit and time.time() - hit[0] < (3600 if final else CONFIRM_TTL):
        return hit[1]
    try:
        box = requests.get(f"{config.WEB_API}/gamecenter/{game['game_id']}/boxscore", timeout=10).json()
        found = probable_goalies.confirmed_starters(box)
    except (requests.RequestException, ValueError, KeyError):
        return hit[1] if hit else {}  # NHL API hiccup: keep the last answer, or fall back to the guess
    _confirm_cache[game["game_id"]] = (time.time(), found)
    return found


_fit_cache = {}


RECORDS_API = "https://records.nhl.com/site/api"


RECORDS_TTL = 24 * 3600


_records_cache = {}   # (url, params) -> (fetched at, rows)


def _records_rows(url, **params):
    """Rows from the NHL records site or the stats API's team list, kept for a day (winners change once a year)."""
    cache_key = (url, tuple(sorted(params.items())))
    hit = _records_cache.get(cache_key)
    if hit and time.time() - hit[0] < RECORDS_TTL:
        return hit[1]
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        rows = r.json()["data"]
    except (requests.RequestException, ValueError, KeyError):
        if hit:
            return hit[1]  # the NHL site hiccuped: keep the last answer
        raise HTTPException(502, "The NHL records site isn't answering right now")
    _records_cache[cache_key] = (time.time(), rows)
    return rows


# --- All-time boards ---------------------------------------------------------------------------
# Sort keys are whitelisted because they're interpolated into SQL (everything else is bound).
ALLTIME_TABLES = {"skater": "career_skater", "goalie": "career_goalie"}


_season_board_cache = {"sig": None, "boards": {}}


def _season_board(conn, kind):
    """The built best-seasons board for 'skater' or 'goalie', kept until the stored seasons change (see bestseasons.py)."""
    sig = tuple(conn.execute(
        """SELECT (SELECT count(*) FROM career_season) a, (SELECT coalesce(sum(points), 0) FROM career_season) b,
                  (SELECT count(*) FROM defense_season) c, (SELECT count(*) FROM goalie_season) d,
                  (SELECT coalesce(sum(wins), 0) FROM goalie_season) e""").fetchone().values())
    if _season_board_cache["sig"] != sig:
        _season_board_cache.update(sig=sig, boards={})
    boards = _season_board_cache["boards"]
    if kind not in boards:
        if kind == "skater":
            seasons = conn.execute(
                """SELECT s.player_id, s.season_id, s.team, s.games_played, s.goals, s.assists, s.points,
                          k.name, k.position, k.birth_country, k.hall_of_fame, k.active_season
                   FROM career_season s JOIN career_skater k ON k.player_id = s.player_id AND k.game_type = 2""").fetchall()
            defense = {(r["player_id"], r["season_id"]): r for r in conn.execute(
                "SELECT player_id, season_id, hits, blocked_shots, takeaways, giveaways FROM defense_season")}
            boards[kind] = bestseasons.skater_board(seasons, defense, config.SEASON_ID)
        else:
            seasons = conn.execute(
                """SELECT g.*, c.birth_country, c.hall_of_fame, c.active_season FROM goalie_season g
                   LEFT JOIN career_goalie c ON c.player_id = g.player_id AND c.game_type = 2""").fetchall()
            boards[kind] = bestseasons.goalie_board(seasons, config.SEASON_ID)
    return boards[kind]


# --- Shots and expected goals -------------------------------------------------------------------
SHOT_COLUMNS = """s.game_id, s.event_id, g.game_date, s.team, s.opponent, s.period, s.time_sec, s.kind,
                  s.shot_type, s.x, s.y, s.distance, s.xg, s.strength, s.rebound, s.shooter_id, s.goalie_id"""


def _shots(conn, where, params, limit=1500):
    return conn.execute(
        f"SELECT {SHOT_COLUMNS} FROM shot s JOIN game g USING (game_id) "
        f"WHERE s.season_id = %(season)s AND s.x IS NOT NULL AND {where} "
        f"ORDER BY g.game_date DESC, s.game_id DESC, s.time_sec DESC LIMIT %(limit)s",
        {"season": config.SEASON_ID, "limit": limit, **params},
    ).fetchall()


_zone_calibration = {"sig": None, "cal": None}


ZONE_SHOT_SQL = """
    SELECT season_id, goalie_id, kind, xg, distance, angle, y, shot_type, rebound, strength, empty_net
    FROM shot_hist WHERE x IS NOT NULL AND kind IN ('shot', 'goal')
    UNION ALL
    SELECT season_id, goalie_id, kind, xg, distance, angle, y, shot_type, rebound, strength, empty_net
    FROM shot WHERE x IS NOT NULL AND kind IN ('shot', 'goal') AND season_id NOT IN (SELECT season_id FROM shot_hist_game)
"""


_zone_summary_cache = {}  # (player_id, span) -> (sig, goalie row, summary)


def _zone_sig(conn, span):
    """What the zone numbers are built from: it changes when shots are added (each ingested game), and only then."""
    return (span, conn.execute("SELECT count(*) AS n FROM shot_hist_game WHERE located").fetchone()["n"],
            conn.execute("SELECT count(*) AS n FROM shot WHERE season_id = %s", (config.SEASON_ID,)).fetchone()["n"])


def _goalie_zone_summary(conn, player_id, span="all", sig=None):
    """(goalie row, goaliemap.summarize output) for one goalie, or (None, None) if he is not in the data. The league calibration
    behind it is cached (see goaliemap.league_calibration), and so is each goalie's summary until the shot data changes (callers that
    ask for many goalies pass `sig` from _zone_sig so it is worked out once)."""
    sig = sig or _zone_sig(conn, span)
    hit = _zone_summary_cache.get((player_id, span))
    if hit and hit[0] == sig:
        return hit[1], hit[2]
    goalie = conn.execute("SELECT name, catches FROM goalie_season WHERE player_id = %s ORDER BY season_id DESC LIMIT 1",
                          (player_id,)).fetchone()
    if goalie is None:
        return None, None
    factors = {r["season_id"]: r["f"] for r in conn.execute(
        f"WITH {luck_db.GOALIE_CALIBRATION_CTE} SELECT season_id, f FROM gcal").fetchall()}
    only = "WHERE season_id = %(cur)s" if span == "current" else ""
    mine = conn.execute(f"SELECT * FROM ({ZONE_SHOT_SQL}) t {only} {'AND' if only else 'WHERE'} goalie_id = %(p)s",
                        {"p": player_id, "cur": config.SEASON_ID}).fetchall()
    if _zone_calibration["sig"] != sig:
        catches = {r["player_id"]: r["catches"] for r in conn.execute(
            "SELECT DISTINCT ON (player_id) player_id, catches FROM goalie_season ORDER BY player_id, season_id DESC").fetchall()}
        league = conn.execute(f"SELECT * FROM ({ZONE_SHOT_SQL}) t {only}", {"cur": config.SEASON_ID}).fetchall()
        for r in league:
            r["catches"] = catches.get(r["goalie_id"])
            r["f"] = factors.get(r["season_id"], 1.0)
        _zone_calibration.update(sig=sig, cal=goaliemap.league_calibration(league, 1.0))
    for r in mine:
        r["f"] = factors.get(r["season_id"], 1.0)
    summary = goaliemap.summarize(mine, 1.0, goalie["catches"], _zone_calibration["cal"])
    _zone_summary_cache[(player_id, span)] = (sig, goalie, summary)
    return goalie, summary


def _timed_seasons(conn):
    """Seasons with score state available: the current one plus past seasons whose shot times are backfilled."""
    rows = conn.execute("SELECT season_id FROM shot_hist_game WHERE timed GROUP BY season_id ORDER BY season_id").fetchall()
    return sorted({r["season_id"] for r in rows} | {config.SEASON_ID})


# --- Pace history -------------------------------------------------------------------------------
def _cumulative(rows):
    """[(value per game, ...)] -> running totals by game number (1-based)."""
    total, out = 0, []
    for v in rows:
        total += v
        out.append(total)
    return out
