"""Analytics endpoints: luck, score effects, tracking leaders and head-to-head."""

from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row
import requests

import config
import headtohead
import luck
import luck_db
import oldgames_db
import scorestate
import scorestate_db
from routes.common import _timed_seasons, ttl_cached

router = APIRouter()


# --- NHL EDGE tracking stats ------------------------------------------------------------------------
# stat id -> (SQL expression over edge_skater_season e / career_season s, label, unit, column holding the NHL
# percentile or None, column holding the date of the event or None, game-id column or None).
TRACKING_STATS = {
    "top_shot": ("e.top_shot_mph", "Hardest shot", "mph", "top_shot_pctile", "top_shot_date", "top_shot_game_id"),
    "avg_shot": ("e.avg_shot_mph", "Average shot speed", "mph", "avg_shot_pctile", None, None),
    "hard_shots": ("coalesce(e.shots_90_100, 0) + coalesce(e.shots_100_plus, 0)", "Shot attempts at 90+ mph", "attempts", None, None, None),
    "top_speed": ("e.top_speed_mph", "Fastest skating speed", "mph", "top_speed_pctile", "top_speed_date", "top_speed_game_id"),
    "bursts_22": ("e.bursts_22_plus", "Bursts over 22 mph", "bursts", "bursts_22_pctile", None, None),
    "bursts_20": ("coalesce(e.bursts_22_plus, 0) + coalesce(e.bursts_20_22, 0)", "Bursts over 20 mph", "bursts", None, None, None),
    "distance_per_game": ("e.distance_miles / nullif(s.games_played, 0)", "Distance skated per game", "mi", None, None, None),
    "distance": ("e.distance_miles", "Distance skated", "mi", "distance_pctile", None, None),
    "distance_max_game": ("e.distance_max_game_miles", "Most distance in a game", "mi", None, None, None),
    "oz_time": ("e.oz_pct", "Offensive-zone time", "share", "oz_pctile", None, None),
    "dz_time": ("e.dz_pct", "Defensive-zone time", "share", "dz_pctile", None, None),
    "hd_sog": ("e.hd_sog", "High-danger shots on goal", "shots", None, None, None),
}


EDGE_SEASONS_SQL = "SELECT DISTINCT season_id FROM edge_skater_season WHERE has_data ORDER BY season_id DESC"


@router.get("/api/tracking/leaders")
def tracking_leaders(stat: str = "top_shot", season: str = "", position: str = "", min_gp: int = 10,
                     dir: str = "desc", limit: int = 50):
    """Skater leaderboard for one EDGE stat in one season, or across every stored season (season=all)."""
    if stat not in TRACKING_STATS:
        raise HTTPException(400, f"Unknown stat; choose one of {', '.join(TRACKING_STATS)}")
    expr, label, unit, pct_col, date_col, game_col = TRACKING_STATS[stat]
    direction = "ASC" if dir.lower() == "asc" else "DESC"
    limit = max(1, min(limit, 200))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        seasons = [r["season_id"] for r in conn.execute(EDGE_SEASONS_SQL)]
        if not seasons:
            return {"stat": stat, "label": label, "unit": unit, "seasons": [], "season": None, "rows": []}
        where, params = ["e.has_data", f"({expr}) IS NOT NULL", "s.games_played >= %(min_gp)s"], {"min_gp": max(0, min_gp)}
        if season == "all":
            chosen = "all"
        else:
            chosen = int(season) if season.isdigit() else seasons[0]
            where.append("e.season_id = %(season)s")
            params["season"] = chosen
        if position == "F":
            where.append("c.position <> 'D'")
        elif position in ("C", "L", "R", "D"):
            where.append("c.position = %(position)s")
            params["position"] = position
        rows = conn.execute(
            f"""SELECT e.player_id, e.season_id, c.name, c.position, s.team, s.games_played, ({expr}) AS value,
                       {('e.' + pct_col) if pct_col else 'NULL::real'} AS percentile,
                       {('e.' + date_col) if date_col else 'NULL::date'} AS event_date,
                       {('e.' + game_col) if game_col else 'NULL::bigint'} AS game_id,
                       (e.season_id = %(current)s) AS current_season
                FROM edge_skater_season e
                JOIN career_season s ON s.player_id = e.player_id AND s.season_id = e.season_id
                JOIN career_skater c ON c.player_id = e.player_id AND c.game_type = 2
                WHERE {' AND '.join(where)} ORDER BY value {direction}, c.name LIMIT %(limit)s""",
            {**params, "limit": limit, "current": config.SEASON_ID}).fetchall()
    return {"stat": stat, "label": label, "unit": unit, "seasons": seasons, "season": chosen, "rows": rows,
            "stats": [{"id": k, "label": v[1], "unit": v[2]} for k, v in TRACKING_STATS.items()]}


GOALIE_TRACKING = {
    # stat -> (column, label, shots-faced columns used for the minimum)
    "sv_high": ("sv_high", "High-danger save %", ("saves_high", "ga_high"), 60),
    "sv_mid": ("sv_mid", "Mid-range save %", ("saves_mid", "ga_mid"), 120),
    "sv_long": ("sv_long", "Long-range save %", ("saves_long", "ga_long"), 120),
    "sv_all": ("sv_all", "Overall save %", ("saves_high", "ga_high"), 60),
    "games_above_900": ("games_above_900", "Share of games above .900", ("saves_high", "ga_high"), 60),
}


@router.get("/api/tracking/goalies")
def tracking_goalies(stat: str = "sv_high", season: str = "", limit: int = 50):
    """Goalie leaderboard for an EDGE save stat; goalies need a minimum number of shots faced from that range."""
    if stat not in GOALIE_TRACKING:
        raise HTTPException(400, f"Unknown stat; choose one of {', '.join(GOALIE_TRACKING)}")
    col, label, shot_cols, minimum = GOALIE_TRACKING[stat]
    limit = max(1, min(limit, 200))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        seasons = [r["season_id"] for r in conn.execute(
            "SELECT DISTINCT season_id FROM edge_goalie_season WHERE has_data ORDER BY season_id DESC")]
        if not seasons:
            return {"stat": stat, "label": label, "seasons": [], "season": None, "rows": []}
        chosen = int(season) if season.isdigit() else seasons[0]
        rows = conn.execute(
            f"""SELECT e.player_id, e.season_id, c.name, g.team, e.{col} AS value, e.sv_all, e.sv_high, e.sv_mid, e.sv_long,
                       e.{shot_cols[0]} + e.{shot_cols[1]} AS shots_faced
                FROM edge_goalie_season e
                JOIN career_goalie c ON c.player_id = e.player_id AND c.game_type = 2
                LEFT JOIN goalie_season g ON g.player_id = e.player_id AND g.season_id = e.season_id
                WHERE e.has_data AND e.season_id = %s AND e.{col} IS NOT NULL
                  AND e.{shot_cols[0]} + e.{shot_cols[1]} >= %s
                ORDER BY value DESC, c.name LIMIT %s""", (chosen, minimum, limit)).fetchall()
    return {"stat": stat, "label": label, "seasons": seasons, "season": chosen, "minimum_shots": minimum, "rows": rows,
            "stats": [{"id": k, "label": v[1]} for k, v in GOALIE_TRACKING.items()]}


# --- Head-to-head -----------------------------------------------------------------------------------
H2H_TEAM_SQL = """
SELECT t.season_id, t.game_id, t.game_date, t.goals_for AS gf, t.goals_against AS ga,
       CASE WHEN t.wins = 1 THEN CASE WHEN o.points = 1 THEN 'OTW' ELSE 'W' END
            WHEN t.points = 1 THEN 'OTL' ELSE 'L' END AS result
FROM team_game_hist t JOIN team_game_hist o ON o.game_id = t.game_id AND o.team = t.opponent
WHERE t.team = %(a)s AND t.opponent = %(b)s
UNION ALL
SELECT g.season_id, g.game_id, g.game_date,
       CASE WHEN g.home = %(a)s THEN g.home_score ELSE g.away_score END,
       CASE WHEN g.home = %(a)s THEN g.away_score ELSE g.home_score END,
       CASE WHEN (g.home = %(a)s) = (g.home_score > g.away_score)
            THEN CASE WHEN g.last_period = 'REG' THEN 'W' ELSE 'OTW' END
            ELSE CASE WHEN g.last_period = 'REG' THEN 'L' ELSE 'OTL' END END
FROM game g
WHERE g.state IN ('OFF', 'FINAL') AND g.home_score IS NOT NULL AND g.season_id = %(season)s
  AND ((g.home = %(a)s AND g.away = %(b)s) OR (g.home = %(b)s AND g.away = %(a)s))
UNION ALL
SELECT g.season_id, g.game_id, g.game_date,
       CASE WHEN g.home = %(a)s THEN g.home_score ELSE g.away_score END,
       CASE WHEN g.home = %(a)s THEN g.away_score ELSE g.home_score END,
       CASE WHEN (g.home = %(a)s) = (g.home_score > g.away_score)
            THEN CASE WHEN g.last_period = 'REG' THEN 'W' ELSE 'OTW' END
            ELSE CASE WHEN g.last_period = 'REG' THEN 'L' ELSE 'OTL' END END
FROM game_hist g
WHERE (g.home = %(a)s AND g.away = %(b)s) OR (g.home = %(b)s AND g.away = %(a)s)
"""


H2H_PLAYER_SQL = """
SELECT season_id, game_id, game_date, opponent, goals, assists FROM skater_game WHERE player_id = %(p)s
UNION ALL
SELECT h.season_id, h.game_id, h.game_date, t.opponent, h.goals, h.assists
FROM skater_game_hist h
JOIN skater_game_onice o ON o.player_id = h.player_id AND o.game_id = h.game_id
JOIN team_game_hist t ON t.game_id = h.game_id AND t.team = CASE WHEN o.team = 'ARI' THEN 'UTA' ELSE o.team END
WHERE h.player_id = %(p)s
UNION ALL
SELECT season_id, game_id, game_date, opponent, goals, assists FROM player_game_old WHERE player_id = %(p)s
"""


# A goalie's past games come from the stored shots they faced: the opponent is the team of the shooters, and the
# date comes from that team's game row. A few games with no usable shooter are missing, and so are
# shootout-only appearances. This season uses goalie_game, which has the opponent directly.
H2H_GOALIE_SQL = """
SELECT season_id, game_id, game_date, opponent, shots_against, goals_against FROM goalie_game
WHERE player_id = %(p)s AND toi_sec > 0
UNION ALL
SELECT season_id, game_id, game_date, opponent, shots_against, goals_against FROM player_game_old WHERE player_id = %(p)s
UNION ALL
SELECT s.season_id, s.game_id, t.game_date, CASE WHEN o.team = 'ARI' THEN 'UTA' ELSE o.team END,
       count(*) FILTER (WHERE s.kind IN ('shot', 'goal')), count(*) FILTER (WHERE s.kind = 'goal')
FROM shot_hist s
JOIN (SELECT DISTINCT player_id, game_id, team FROM skater_game_onice) o ON o.player_id = s.shooter_id AND o.game_id = s.game_id
JOIN team_game_hist t ON t.game_id = s.game_id AND t.team = o.team
WHERE s.goalie_id = %(p)s
GROUP BY s.season_id, s.game_id, t.game_date, o.team
"""


def _ensure_old_games(conn, player_id, goalie):
    """Pulls the player's games from before the stored seasons the first time (see oldgames.py); a NHL outage is a 502."""
    try:
        oldgames_db.ensure_player(conn, player_id, goalie)
    except requests.RequestException:
        raise HTTPException(502, "The NHL's older game logs are not available right now. Try again in a minute.")


@router.get("/api/head-to-head/teams")
def head_to_head_teams(a: str, b: str):
    """Results between two teams since 2005-06: this season and the previous four from the stored game results, earlier
    ones from the club schedules in game_hist (see oldgames.py)."""
    a, b = a.upper(), b.upper()
    if a == b:
        raise HTTPException(400, "Pick two different teams")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        names = {r["abbrev"]: r["name"] for r in conn.execute(
            "SELECT abbrev, name FROM team_season WHERE season_id = %s", (config.SEASON_ID,))}
        if a not in names or b not in names:
            raise HTTPException(404, "Team not found")
        games = conn.execute(H2H_TEAM_SQL, {"a": a, "b": b, "season": config.SEASON_ID}).fetchall()
        current = {r["game_id"] for r in conn.execute(
            "SELECT game_id FROM game WHERE season_id = %s", (config.SEASON_ID,))}
    summary = headtohead.team_summary(games)
    recent = sorted(games, key=lambda g: (g["game_date"], g["game_id"]), reverse=True)[:20]
    return {"a": {"abbrev": a, "name": names[a]}, "b": {"abbrev": b, "name": names[b]},
            "first_season": min((g["season_id"] for g in games), default=None),
            "summary": summary,
            "recent": [{**g, "link": g["game_id"] in current} for g in recent]}


@router.get("/api/head-to-head/player")
def head_to_head_player(player_id: int, team: str):
    """A skater's scoring against one team over the stored seasons, next to his scoring against everyone else."""
    team = team.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        who = conn.execute("SELECT name, position FROM career_skater WHERE player_id = %s AND game_type = 2",
                           (player_id,)).fetchone()
        if not who:
            raise HTTPException(404, "No skater with that id")
        tname = conn.execute("SELECT name FROM team_season WHERE season_id = %s AND abbrev = %s",
                             (config.SEASON_ID, team)).fetchone()
        if not tname:
            raise HTTPException(404, "Team not found")
        _ensure_old_games(conn, player_id, goalie=False)
        rows = conn.execute(H2H_PLAYER_SQL, {"p": player_id}).fetchall()
    out = headtohead.player_summary(rows, team)
    games = sorted((r for r in rows if r["opponent"] == team), key=lambda r: (r["game_date"], r["game_id"]), reverse=True)
    return {"player": {"player_id": player_id, "name": who["name"], "position": who["position"]},
            "team": {"abbrev": team, "name": tname["name"]},
            "stored_games": len(rows), **out,
            "recent": [{k: r[k] for k in ("season_id", "game_id", "game_date", "goals", "assists")} for r in games[:20]]}


@router.get("/api/head-to-head/goalie")
def head_to_head_goalie(player_id: int, team: str):
    """A goalie's save percentage against one team over the stored seasons, next to their numbers against everyone else."""
    team = team.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        who = conn.execute("SELECT name FROM career_goalie WHERE player_id = %s AND game_type = 2", (player_id,)).fetchone()
        if not who:
            raise HTTPException(404, "No goalie with that id")
        tname = conn.execute("SELECT name FROM team_season WHERE season_id = %s AND abbrev = %s",
                             (config.SEASON_ID, team)).fetchone()
        if not tname:
            raise HTTPException(404, "Team not found")
        _ensure_old_games(conn, player_id, goalie=True)
        rows = conn.execute(H2H_GOALIE_SQL, {"p": player_id}).fetchall()
    out = headtohead.goalie_summary(rows, team)
    games = sorted((r for r in rows if r["opponent"] == team), key=lambda r: (r["game_date"], r["game_id"]), reverse=True)
    return {"player": {"player_id": player_id, "name": who["name"]},
            "team": {"abbrev": team, "name": tname["name"]},
            "stored_games": len(rows), **out,
            "recent": [{k: r[k] for k in ("season_id", "game_id", "game_date", "shots_against", "goals_against")} for r in games[:20]]}


_score_cache = {}


def _score_tallies(conn, seasons):
    sig = (tuple(seasons), conn.execute("SELECT count(*) AS n FROM shot_hist_game WHERE timed").fetchone()["n"],
           conn.execute("SELECT count(*) AS n FROM shot WHERE season_id = %s", (config.SEASON_ID,)).fetchone()["n"])
    hit = _score_cache.get(tuple(seasons))
    if hit is None or hit[0] != sig:
        hit = (sig, scorestate_db.team_tallies(conn, seasons))
        _score_cache[tuple(seasons)] = hit
    return hit[1]


@router.get("/api/score-effects")
def score_effects(season: str = "current"):
    """How play changes with the score, league-wide and by team, with score-adjusted team shares (see scorestate.py).
    season is a season id, `current`, or `all` (every season with shot times). The score effect behind the adjustment
    is always measured on every available season."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        available = _timed_seasons(conn)
        if season == "all":
            chosen = available
        else:
            chosen = [config.SEASON_ID if season == "current" else int(season)] if (season == "current" or season.isdigit()) else []
        if not chosen or any(c not in available for c in chosen):
            raise HTTPException(400, "season must be current, all, or a season with shot times")
        league = _score_tallies(conn, available)
        mine = league if chosen == available else _score_tallies(conn, chosen)
    rows, p = scorestate.team_rows(mine, league)
    rows.sort(key=lambda r: -(r["xg_pct_adj"] or 0))
    return {"seasons": chosen, "available": available, "effects": scorestate.league_effects(mine),
            "effects_all": scorestate.league_effects(league), "teams": rows, "league_share": p}


# --- Luck and regression --------------------------------------------------------------------------
@router.get("/api/luck/skaters")
@ttl_cached(60)
def luck_skaters(position: str = "", min_attempts: int = luck.MIN_ATTEMPTS, dir: str = "desc", rank: str = "points",
                 vs: str = "own", limit: int = 50):
    """Skaters' goals and points against what their shots (and their teammates' shots while on the ice) predict,
    with a z-score for how unusual each gap is (see luck.py). rank=points or goals picks which z orders the list;
    vs=own compares each player with what their own past seasons say they should score, vs=average with an average
    shooter; dir=desc lists the hottest first, dir=asc the coldest."""
    if rank not in ("points", "goals"):
        raise HTTPException(400, "rank must be points or goals")
    if vs not in ("own", "average"):
        raise HTTPException(400, "vs must be own or average")
    limit = max(1, min(limit, 1000))
    key = ("points_z" if rank == "points" else "z") + ("_adj" if vs == "own" else "")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = luck_db.skater_rows(conn, config.SEASON_ID, config.GAMES_PER_SEASON, position, min_attempts)
    out = [r for r in rows if r[key] is not None]
    out.sort(key=lambda x: (x[key], x["name"]), reverse=dir.lower() != "asc")
    return {"season": config.SEASON_ID, "games": config.GAMES_PER_SEASON, "min_attempts": min_attempts,
            "rank": rank, "vs": vs, "z_flag": luck.Z_FLAG, "rows": out[:limit]}


@router.get("/api/luck/goalies")
def luck_goalies(min_faced: int = luck.MIN_FACED, dir: str = "desc", limit: int = 50):
    """Goalies' goals saved above expected (xG faced minus goals allowed), with a z-score for the gap."""
    limit = max(1, min(limit, 200))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = luck_db.goalie_rows(conn, config.SEASON_ID, min_faced)
    out = [r for r in rows if r["z"] is not None]
    out.sort(key=lambda x: (x["z"], x["name"]), reverse=dir.lower() != "asc")
    return {"season": config.SEASON_ID, "min_faced": min_faced, "z_flag": luck.Z_FLAG, "rows": out[:limit]}


@router.get("/api/luck/history/{player_id}")
def luck_history(player_id: int):
    """A player's finishing (skater) or goals saved above expected (goalie) season by season, past seasons included."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        history = luck_db.skater_history(conn, player_id)
        kind = "skater"
        if not history["seasons"]:
            history, kind = luck_db.goalie_history(conn, player_id), "goalie"
    return {"kind": kind if history["seasons"] else None, **history}


@router.get("/api/luck/persistence")
def luck_persistence():
    """How well one season's luck figure predicts the next (see luck_db.persistence)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        result = luck_db.persistence(conn)
    return {"min_attempts": luck.MIN_PERSIST_ATTEMPTS, "min_faced": luck.MIN_PERSIST_FACED, **result}


@router.get("/api/luck/players")
def luck_players(ids: str = ""):
    """Luck figures for specific players (comma-separated ids, skaters and goalies mixed), keyed by player id.
    Players with no shots yet are left out; `enough` says whether the sample is big enough to trust the flag."""
    try:
        wanted = [int(x) for x in ids.split(",") if x.strip()][:100]
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    if not wanted:
        return {"season": config.SEASON_ID, "z_flag": luck.Z_FLAG, "skaters": {}, "goalies": {}}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        skaters = luck_db.skater_rows(conn, config.SEASON_ID, config.GAMES_PER_SEASON, ids=wanted)
        goalies = luck_db.goalie_rows(conn, config.SEASON_ID, ids=wanted)
    return {"season": config.SEASON_ID, "games": config.GAMES_PER_SEASON, "z_flag": luck.Z_FLAG,
            "skaters": {r["player_id"]: r for r in skaters}, "goalies": {r["player_id"]: r for r in goalies}}
