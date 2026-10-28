"""Read-only JSON API over the ingested stats. Run: uvicorn api:app --reload"""
from datetime import date, datetime, timedelta, timezone

import math
from collections import defaultdict
import statistics
import time

import psycopg
import requests
from fastapi import FastAPI, HTTPException, Request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import absences_db
import accuracy
import awards
import winprob
import winprob_db
import predictions
import auth
import chemistry
import config
import defense
import era
import explain_db
import fatigue
import headtohead
import leagues
import oldgames_db
import luck
import luck_db
import matchups
import matchups_db
import playoff_odds
import probable_goalies
import roles
import roles_db
import specialteams
import specialteams_db
import streaming
import teamlog
import tonight
import projections
import prospects as prospectlib
import trajectory
import trophies as trophy_lib

app = FastAPI(title="Hockey Stats")
app.include_router(auth.router)
app.include_router(leagues.router)


@app.on_event("startup")
def _init_accounts():
    auth.init_db()
    leagues.init_db()   # after auth: its tables refer to app_user
    predictions.init_db()

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
    SELECT lg.player_id, count(DISTINCT tg.game_id) AS games_out
    FROM last_game lg
    JOIN skater_game tg ON tg.team = lg.team AND tg.season_id = %(season)s
     AND (tg.game_date, tg.game_id) > (lg.game_date, lg.game_id)
    GROUP BY lg.player_id
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
       (position(',' in s.team) > 0) AS traded,
       round(s.points::numeric / s.games_played * %(games)s, 1)::float AS point_pace,
       r.games AS recent_games, r.points AS recent_points,
       round(r.points::numeric / r.games * %(games)s, 1)::float AS recent_pace,
       round(r.hits::numeric / NULLIF(r.def_toi_sec, 0) * 3600, 1)::float AS recent_hits_per60,
       round(r.blocks::numeric / NULLIF(r.def_toi_sec, 0) * 3600, 1)::float AS recent_blocks_per60,
       round(r.takeaways::numeric / NULLIF(r.def_toi_sec, 0) * 3600, 1)::float AS recent_takeaways_per60,
       round(r.giveaways::numeric / NULLIF(r.def_toi_sec, 0) * 3600, 1)::float AS recent_giveaways_per60,
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
       round(oi.cf::numeric / NULLIF(oi.cf + oi.ca, 0) - s.sat_pct::numeric, 4)::float AS cf_pct_trend
FROM skater_season s
LEFT JOIN recent r USING (player_id)
LEFT JOIN onice_recent oi USING (player_id)
LEFT JOIN lineup_gap lgap USING (player_id)
LEFT JOIN ixg ix USING (player_id)
LEFT JOIN onice_xg ox USING (player_id)
WHERE s.season_id = %(season)s AND s.games_played > 0
ORDER BY s.points DESC, s.games_played ASC
"""


@app.get("/api/meta")
def meta():
    with psycopg.connect(config.DATABASE_URL) as conn:
        updated = conn.execute("SELECT max(updated_at) FROM skater_season WHERE season_id = %s", (config.SEASON_ID,)).fetchone()[0]
    return {
        "updated_at": updated,
        "season_id": config.SEASON_ID,
        "games_per_season": config.GAMES_PER_SEASON,
        "recent_window": config.RECENT_WINDOW,
    }


def _stored_season(conn, table, season):
    """The season to show: the current one when none is asked for, else a past season that has stats stored (404 if not)."""
    if season is None or season == config.SEASON_ID:
        return config.SEASON_ID
    if conn.execute(f"SELECT 1 FROM {table} WHERE season_id = %s LIMIT 1", (season,)).fetchone() is None:
        raise HTTPException(404, "No stats stored for that season")
    return season


@app.get("/api/seasons")
def seasons():
    """Seasons the Skaters and Goalies leaderboards can show, newest first (the current season is the default)."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        def ids(table):
            return [r[0] for r in conn.execute(f"SELECT DISTINCT season_id FROM {table} ORDER BY season_id DESC")]
        return {"current": config.SEASON_ID, "skaters": ids("skater_season"), "goalies": ids("goalie_season")}


@app.get("/api/skaters")
def skaters(season: int | None = None):
    """Every skater's season line. Past seasons have no per-game data, so their recent-form and expected-goals columns are
    empty; the season totals and the NHL's own rates are all there."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        params = {
            "season": _stored_season(conn, "skater_season", season),
            "window": config.RECENT_WINDOW,
            "games": config.GAMES_PER_SEASON,
        }
        return conn.execute(SKATERS_SQL, params).fetchall()


# Stats the player page ranks against same-role peers, with whether bigger is better.
DEFENSIVE_STATS = {
    "hits_per60": True,
    "blocks_per60": True,
    "takeaways_per60": True,
    "giveaways_per60": False,  # fewer giveaways is better
    "hits": True,
    "blocked_shots": True,
    "takeaways": True,
    "giveaways": False,
    # Possession / usage (5v5), all "higher is better"
    "sat_pct": True,
    "usat_pct": True,
    "sat_rel": True,
    "zone_start_pct_5v5": True,
    "ev_goals_for_pct": True,
    "pp_points_per60": True,
}


def _percentile(value, peers, higher_is_better):
    """Share of peers this player is at least as good as, 0-100."""
    peers = [p for p in peers if p is not None]
    if value is None or not peers:
        return None
    beaten = sum(1 for p in peers if (p <= value if higher_is_better else p >= value))
    return round(100 * beaten / len(peers))


@app.get("/api/skaters/{player_id}")
def skater(player_id: int):
    params = {
        "season": config.SEASON_ID,
        "window": config.RECENT_WINDOW,
        "games": config.GAMES_PER_SEASON,
    }
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        everyone = conn.execute(SKATERS_SQL, params).fetchall()
        player = next((r for r in everyone if r["player_id"] == player_id), None)
        if player is None:
            raise HTTPException(404, "Player not found")
        games = conn.execute(
            """SELECT game_id, game_date, team, opponent, is_home, goals, assists,
                      points, shots, plus_minus, pim, toi_sec,
                      hits, blocked_shots, takeaways, giveaways
               FROM skater_game WHERE player_id = %s AND season_id = %s
               ORDER BY game_date DESC""",
            (player_id, config.SEASON_ID),
        ).fetchall()
        onice = {
            r["game_id"]: r
            for r in conn.execute(
                "SELECT game_id, cf, ca, ff, fa, gf, ga FROM skater_game_onice WHERE player_id = %s AND season_id = %s",
                (player_id, config.SEASON_ID),
            ).fetchall()
        }
    for g in games:  # attach 5v5 on-ice counts; None where the NHL has no shift data for that game
        g["onice"] = onice.get(g["game_id"])

    # Compare against same-role (forward vs defense) players with a meaningful sample.
    group = lambda r: "D" if r["position"] == "D" else "F"
    min_gp = max(1, -(-max(r["games_played"] for r in everyone) // 2))
    peers = [r for r in everyone if group(r) == group(player) and r["games_played"] >= min_gp]
    percentiles = {
        stat: _percentile(player[stat], [p[stat] for p in peers], better)
        for stat, better in DEFENSIVE_STATS.items()
    }
    return {
        "player": player,
        "games": games,
        "percentiles": percentiles,
        "games_per_season": config.GAMES_PER_SEASON,
        "peer_group": "defensemen" if group(player) == "D" else "forwards",
        "peer_count": len(peers),
        "peer_min_gp": min_gp,
    }


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


@app.get("/api/teams")
def teams():
    params = {"season": config.SEASON_ID, "games": config.GAMES_PER_SEASON}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(TEAMS_SQL, params).fetchall()


@app.get("/api/teams/{abbrev}")
def team(abbrev: str):
    params = {"season": config.SEASON_ID, "games": config.GAMES_PER_SEASON}
    abbrev = abbrev.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        everyone = conn.execute(TEAMS_SQL, params).fetchall()
        found = next((t for t in everyone if t["abbrev"] == abbrev), None)
        if found is None:
            raise HTTPException(404, "Team not found")
        # Players traded mid-season have a comma-separated team list ("NYI,TOR");
        # they appear on both rosters with their combined season totals.
        roster = conn.execute(
            """SELECT player_id, name, team, position, games_played, goals, assists, points,
                      plus_minus, toi_per_game_sec, hits, blocked_shots, sat_pct,
                      round(points::numeric / games_played * %(games)s, 1)::float AS point_pace
               FROM skater_season
               WHERE season_id = %(season)s AND games_played > 0
                 AND %(abbrev)s = ANY(string_to_array(team, ','))
               ORDER BY points DESC, games_played ASC""",
            {**params, "abbrev": abbrev},
        ).fetchall()
        # Goalies reuse the leaderboard query so GSAA and recent form match the goalie pages.
        goalie_rows = conn.execute(GOALIES_SQL, _goalie_params()).fetchall()
    goalies = [g for g in goalie_rows if abbrev in (g["team"] or "").split(",")]
    goalies.sort(key=lambda g: (-g["games_started"], -g["games_played"]))
    return {"team": found, "roster": roster, "goalies": goalies, "league_size": len(everyone)}


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
)
SELECT s.*,
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
LEFT JOIN recent r USING (player_id)
WHERE s.season_id = %(season)s AND s.games_played > 0
ORDER BY s.wins DESC, s.games_played ASC
"""


def _goalie_params():
    return {"season": config.SEASON_ID, "window": config.RECENT_GOALIE_GAMES}


@app.get("/api/goalies")
def goalies(season: int | None = None):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        chosen = _stored_season(conn, "goalie_season", season)
        return {
            "season_id": chosen,
            "recent_window": config.RECENT_GOALIE_GAMES,
            "goalies": conn.execute(GOALIES_SQL, {**_goalie_params(), "season": chosen}).fetchall(),
        }


@app.get("/api/goalies/{player_id}")
def goalie(player_id: int):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        everyone = conn.execute(GOALIES_SQL, _goalie_params()).fetchall()
        player = next((g for g in everyone if g["player_id"] == player_id), None)
        if player is None:
            raise HTTPException(404, "Goalie not found")
        games = conn.execute(
            """SELECT game_id, game_date, team, opponent, is_home, started, decision,
                      shots_against, saves, goals_against, toi_sec,
                      ev_goals_against, pp_goals_against, sh_goals_against
               FROM goalie_game WHERE player_id = %s AND season_id = %s
               ORDER BY game_date DESC, game_id DESC""",
            (player_id, config.SEASON_ID),
        ).fetchall()
    return {
        "goalie": player,
        "games": games,
        "league_sv_pct": player["league_sv_pct"],
        "recent_window": config.RECENT_GOALIE_GAMES,
    }


CAREER_TTL = timedelta(hours=24)


def _fetch_landing(player_id):
    r = requests.get(f"{config.WEB_API}/player/{player_id}/landing", timeout=15)
    if r.status_code == 404:
        raise HTTPException(404, "Player not found")
    r.raise_for_status()
    return r.json()


def _career_view(raw):
    """Trim the NHL payload down to what the player page shows."""
    def name(v):
        return v.get("default") if isinstance(v, dict) else v

    seasons = []
    for s in raw.get("seasonTotals", []):
        row = {k: v for k, v in s.items() if not isinstance(v, dict)}
        row["team"] = name(s.get("teamName"))
        seasons.append(row)

    draft = raw.get("draftDetails")
    return {
        "bio": {
            "player_id": raw["playerId"],
            "name": f"{name(raw['firstName'])} {name(raw['lastName'])}",
            "position": raw.get("position"),
            "is_goalie": raw.get("position") == "G",
            "is_active": raw.get("isActive"),
            "sweater": raw.get("sweaterNumber"),
            "shoots_catches": raw.get("shootsCatches"),
            "birth_date": raw.get("birthDate"),
            "birth_city": name(raw.get("birthCity")),
            "birth_state": name(raw.get("birthStateProvince")),
            "birth_country": raw.get("birthCountry"),
            "height_in": raw.get("heightInInches"),
            "weight_lb": raw.get("weightInPounds"),
            "headshot": raw.get("headshot"),
            "in_hhof": raw.get("inHHOF"),
            "draft": draft and {
                "year": draft.get("year"), "team": draft.get("teamAbbrev"),
                "round": draft.get("round"), "overall": draft.get("overallPick"),
            },
            "awards": [
                {"name": name(a["trophy"]), "seasons": [str(x["seasonId"]) for x in a.get("seasons", [])]}
                for a in raw.get("awards", [])
            ],
        },
        "career": raw.get("careerTotals", {}),
        "seasons": seasons,
    }


def _career_payload(conn, player_id, *, allow_fetch=True):
    """Raw NHL landing payload from the Postgres cache, refreshed when stale. None if unavailable."""
    cached = conn.execute(
        "SELECT payload, fetched_at FROM player_career WHERE player_id = %s", (player_id,)
    ).fetchone()
    if cached and datetime.now(timezone.utc) - cached["fetched_at"] < CAREER_TTL:
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


@app.get("/api/players/{player_id}/career")
def career(player_id: int):
    """Career totals and season-by-season history, cached in Postgres for CAREER_TTL."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        raw = _career_payload(conn, player_id)
    if raw is None:
        raise HTTPException(503, "The NHL API is busy right now; try again in a minute.")
    return _career_view(raw)


# --- "Players like this": style similarity from this season's rates ---------------------------
# Each feature is (label, function of a skater row). Rates are per game or per 60 so playing
# time doesn't dominate; every feature gets equal weight after standardizing.
def _per_game(key):
    return lambda r: r[key] / r["games_played"] if r.get(key) is not None and r["games_played"] else None


SIMILARITY_FEATURES = {
    "goals / game": _per_game("goals"),
    "assists / game": _per_game("assists"),
    "shots / game": _per_game("shots"),
    "ice time": lambda r: r.get("toi_per_game_sec"),
    "power-play time": lambda r: r.get("pp_toi_per_game"),
    "penalty-kill time": lambda r: r.get("sh_toi_per_game"),
    "hits / 60": lambda r: r.get("hits_per60"),
    "blocks / 60": lambda r: r.get("blocks_per60"),
    "takeaways / 60": lambda r: r.get("takeaways_per60"),
    "giveaways / 60": lambda r: r.get("giveaways_per60"),
}


def _similar_players(everyone, player, limit=8):
    group = lambda r: "D" if r["position"] == "D" else "F"
    min_gp = max(1, -(-max(r["games_played"] for r in everyone) // 2))
    peers = [r for r in everyone if group(r) == group(player) and r["games_played"] >= min_gp]
    if player["player_id"] not in {p["player_id"] for p in peers}:
        peers.append(player)  # always compare the page's own player, even with few games

    names = list(SIMILARITY_FEATURES)
    raw = {p["player_id"]: [SIMILARITY_FEATURES[n](p) for n in names] for p in peers}
    complete = {pid: v for pid, v in raw.items() if None not in v}
    if player["player_id"] not in complete or len(complete) < 10:
        return {"matches": [], "peer_count": len(complete), "min_gp": min_gp, "features": names}

    cols = list(zip(*complete.values()))
    means = [statistics.fmean(c) for c in cols]
    sds = [statistics.pstdev(c) or 1.0 for c in cols]
    z = {pid: [(x - m) / sd for x, m, sd in zip(v, means, sds)] for pid, v in complete.items()}

    me = z[player["player_id"]]
    by_id = {p["player_id"]: p for p in peers}
    scored = []
    for pid, vec in z.items():
        if pid == player["player_id"]:
            continue
        rms = math.sqrt(sum((a - b) ** 2 for a, b in zip(me, vec)) / len(names))
        # What the two share: features where both stand clearly above or below their peers.
        shared = [
            f"{'high' if a > 0 else 'low'} {n}"
            for n, a, b in zip(names, me, vec)
            if abs(a) >= 0.75 and abs(b) >= 0.75 and (a > 0) == (b > 0)
        ]
        scored.append((rms, pid, shared))
    scored.sort(key=lambda t: t[0])

    matches = []
    for rms, pid, shared in scored[:limit]:
        p = by_id[pid]
        matches.append({
            "player_id": pid, "name": p["name"], "team": p["team"], "position": p["position"],
            "games_played": p["games_played"], "points": p["points"], "goals": p["goals"],
            "assists": p["assists"], "toi_per_game_sec": p["toi_per_game_sec"],
            "hits_per60": p["hits_per60"], "blocks_per60": p["blocks_per60"],
            "similarity": round(100 / (1 + rms)), "shared": shared[:3],
        })
    return {"matches": matches, "peer_count": len(complete), "min_gp": min_gp, "features": names}


# --- Defensive profile (hits, blocks, takeaways, giveaways vs the league) -----------------------
_defense_cache = {"sig": None, "ctx": None, "rows": None}


_onice_cache = {"sig": None, "data": None}
ONICE_SQL = """
WITH tg AS (
    -- team totals per game: every shot is counted once per skater on the ice, five a side at 5v5
    SELECT game_id, team, sum(toi_5v5_sec) / 5.0 AS t_toi, sum(xgf) / 5.0 AS t_xgf, sum(xga) / 5.0 AS t_xga
    FROM skater_game_onice WHERE team IS NOT NULL AND xga IS NOT NULL GROUP BY game_id, team
)
SELECT o.player_id, o.season_id, c.position,
       sum(o.toi_5v5_sec)::float AS on_toi, sum(o.xgf)::float AS on_xgf, sum(o.xga)::float AS on_xga,
       sum(o.cf)::float AS on_cf, sum(o.ca)::float AS on_ca,
       sum(tg.t_toi)::float AS t_toi, sum(tg.t_xgf)::float AS t_xgf, sum(tg.t_xga)::float AS t_xga
FROM skater_game_onice o
JOIN tg ON tg.game_id = o.game_id AND tg.team = o.team
JOIN career_skater c ON c.player_id = o.player_id AND c.game_type = 2
WHERE o.xga IS NOT NULL AND o.toi_5v5_sec > 0
GROUP BY o.player_id, o.season_id, c.position
"""


def _onice_profiles():
    """On-ice defensive metrics for every skater-season we have shift data for, cached until it changes."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        sig = tuple(conn.execute("SELECT count(*) AS n, sum(cf) AS c FROM skater_game_onice").fetchone().values())
        if _onice_cache["sig"] != sig:
            rows = conn.execute(ONICE_SQL).fetchall()
            by_player = {}
            for r in rows:
                by_player.setdefault(r["player_id"], []).append(r)
            _onice_cache.update(sig=sig, data={"metrics": defense.build_onice(rows), "rows": by_player})
    return _onice_cache["data"]


@app.get("/api/players/{player_id}/defense")
def defense_profile(player_id: int):
    """Per-season and since-2005-06 defensive rates as an index against the league (see defense.py)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        sig = tuple(conn.execute("SELECT count(*) AS n, sum(hits) AS h FROM defense_season").fetchone().values())
        if _defense_cache["sig"] != sig:
            rows = conn.execute("SELECT * FROM defense_season").fetchall()
            by_player = {}
            for r in rows:
                by_player.setdefault(r["player_id"], []).append(r)
            _defense_cache.update(sig=sig, ctx=defense.build(rows), rows=by_player)
        who = conn.execute(
            "SELECT name, position, birth_date FROM career_skater WHERE player_id = %s AND game_type = 2",
            (player_id,)).fetchone()
    if not who:
        raise HTTPException(404, "No skater career data for this player")
    mine = sorted(_defense_cache["rows"].get(player_id, []), key=lambda r: r["season_id"])
    ctx = _defense_cache["ctx"]
    onice = _onice_profiles()
    seasons = []
    for r in mine:
        profile = defense.season_profile(r, ctx)
        if profile:
            seasons.append({
                "season_id": r["season_id"], "team": r["team"], "games_played": r["games_played"],
                "toi_per_game_sec": r["toi_per_game_sec"], "qualified": r["games_played"] >= defense.MIN_GP,
                "age": trajectory.age_in(r["season_id"], who["birth_date"]) if who["birth_date"] else None,
                "stats": profile, "onice": onice["metrics"].get((player_id, r["season_id"]))})
    return {"player": {"player_id": player_id, "name": who["name"], "position": who["position"]},
            "min_gp": defense.MIN_GP, "first_tracked": 20052006,
            "seasons": seasons, "career": defense.career_profile(mine, ctx),
            "onice_career": defense.onice_career(onice["rows"].get(player_id, []))}


GOALIE_PROJECTION_DAYS = 200   # longer than any season, so the window runs to the last game


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


@app.get("/api/probable-goalies/week")
def probable_goalies_week(ids: str = "", days: int = 7):
    """For rostered goalies: the chance of starting each of their team's games in the next `days` days.
    Games already played or under way anchor the chain (their starter is known); later games are chained
    from them, so a back-to-back after an uncertain starter is a mix of both cases (see probable_goalies.py)."""
    try:
        wanted = [int(i) for i in ids.split(",") if i.strip()][:20]
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    days = max(1, min(days, 14))
    if not wanted:
        return {"from": None, "to": None, "goalies": []}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        roster = conn.execute(
            "SELECT player_id, name, team FROM goalie_season WHERE season_id = %s AND player_id = ANY(%s)",
            (config.SEASON_ID, wanted)).fetchall()
    teams = {(r["team"] or "").split(",")[-1] for r in roster}
    today, end, plans, known = _goalie_plans(teams, days)

    out = []
    for r in roster:
        team = (r["team"] or "").split(",")[-1]
        has_history = team in known
        entries = [{"game_id": p["game_id"], "date": p["date"], "opponent": p["opponent"], "home_game": p["home_game"],
                    "back_to_back": p["back_to_back"], "confirmed": p["confirmed"],
                    "probability": round(p["dist"].get(r["player_id"], 0.0), 3) if has_history else None}
                   for p in plans.get(team, [])]
        out.append({"player_id": r["player_id"], "name": r["name"], "team": team, "games": entries,
                    "expected_starts": round(sum(e["probability"] or 0 for e in entries), 1) if has_history else None})
    return {"from": today, "to": end, "goalies": out}


@app.get("/api/streaming/goalies")
def streaming_goalies(days: int = 7):
    """Every goalie with a chance to start in the next `days` days: for each game his chance to start and what a start
    there is expected to be worth (win, loss and overtime-loss chances, saves, goals against, shutout chance), from the
    two teams' ratings. The Fantasy page turns these into points or category value under your league. See streaming.py."""
    return _streaming_plan(max(1, min(days, 14)))


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


@app.get("/api/tracking/leaders")
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


@app.get("/api/tracking/goalies")
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


@app.get("/api/players/{player_id}/tracking")
def player_tracking(player_id: int):
    """One player's EDGE stats season by season (a skater's speeds, distance and zone time, or a goalie's
    save percentage by shot range)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        skater = conn.execute("SELECT name, position FROM career_skater WHERE player_id = %s AND game_type = 2",
                              (player_id,)).fetchone()
        if skater:
            rows = conn.execute(
                """SELECT e.*, s.games_played, s.team FROM edge_skater_season e
                   LEFT JOIN career_season s ON s.player_id = e.player_id AND s.season_id = e.season_id
                   WHERE e.player_id = %s AND e.has_data ORDER BY e.season_id DESC""", (player_id,)).fetchall()
            return {"kind": "skater", "name": skater["name"], "position": skater["position"], "seasons": rows}
        goalie = conn.execute("SELECT name FROM career_goalie WHERE player_id = %s AND game_type = 2", (player_id,)).fetchone()
        if not goalie:
            raise HTTPException(404, "Player not found")
        rows = conn.execute(
            "SELECT * FROM edge_goalie_season WHERE player_id = %s AND has_data ORDER BY season_id DESC", (player_id,)).fetchall()
    return {"kind": "goalie", "name": goalie["name"], "position": "G", "seasons": rows}


# --- Career-trajectory comparables --------------------------------------------------------------
_traj_cache = {"sig": None, "data": None}


def _trajectory_data(conn):
    """Every skater's age curve, rebuilt only when the stored seasons change."""
    sig = tuple(conn.execute("SELECT count(*) AS n, sum(points) AS p FROM career_season").fetchone().values())
    if _traj_cache["sig"] != sig:
        people = {r["player_id"]: r for r in conn.execute(
            "SELECT player_id, name, position, birth_date, active_season, hall_of_fame FROM career_skater "
            "WHERE game_type = 2 AND birth_date IS NOT NULL")}
        seasons = {}
        for r in conn.execute("SELECT player_id, season_id, games_played, points FROM career_season ORDER BY season_id"):
            seasons.setdefault(r["player_id"], []).append((r["season_id"], r["games_played"], r["points"]))
        base = trajectory.baselines(
            (sid, trajectory.role(people[pid]["position"]), g, p)
            for pid, rows in seasons.items() if pid in people for sid, g, p in rows)
        curves = {pid: trajectory.curve(seasons.get(pid, []), p["birth_date"], trajectory.role(p["position"]), base)
                  for pid, p in people.items()}
        _traj_cache.update(sig=sig, data={"people": people, "seasons": seasons, "base": base, "curves": curves})
    return _traj_cache["data"]


@app.get("/api/players/{player_id}/comparables")
def comparables(player_id: int, limit: int = 8):
    """Retired skaters whose scoring-by-age curve best matches this player's (see trajectory.py)."""
    limit = max(1, min(limit, 20))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        d = _trajectory_data(conn)
    me = d["people"].get(player_id)
    if not me:
        raise HTTPException(404, "No skater career data for this player")
    role = trajectory.role(me["position"])
    mine = d["curves"][player_id]
    active = me["active_season"] is not None
    out = {"player": {"player_id": player_id, "name": me["name"], "position": me["position"], "active": active},
           "min_gp": trajectory.MIN_GP, "seasons": len(mine), "matches": [], "projection": None,
           "curve": [{"age": a, "value": round(v, 2)} for a, (_, v) in sorted(mine.items())]}
    if len(mine) < trajectory.MIN_SEASONS:
        return out

    scored = []
    for pid, p in d["people"].items():
        if pid == player_id or p["active_season"] is not None or trajectory.role(p["position"]) != role:
            continue
        hit = trajectory.distance(mine, d["curves"][pid])
        if hit:
            scored.append((hit[0], hit[1], pid))
    scored.sort()

    now = d["base"].get((config.SEASON_ID - 10001, role))  # last full season's scoring level
    last_age = max(mine)
    matches, afters = [], []
    for rms, compared, pid in scored[:limit]:
        p, rows, cv = d["people"][pid], d["seasons"][pid], d["curves"][pid]
        after = None
        if active and now:  # points after the target's current age, scaled to today's scoring level
            after = round(sum(pts * now / d["base"][sid, role] for sid, g, pts in rows
                              if trajectory.age_in(sid, p["birth_date"]) > last_age and (sid, role) in d["base"]))
            afters.append(after)
        peak = max(cv, key=lambda a: cv[a][1])
        matches.append({
            "player_id": pid, "name": p["name"], "position": p["position"], "hall_of_fame": p["hall_of_fame"],
            "similarity": trajectory.similarity(rms), "seasons_compared": compared,
            "first_season": rows[0][0], "last_season": rows[-1][0],
            "games_played": sum(g for _, g, _ in rows), "points": sum(pts for _, _, pts in rows),
            "peak_age": peak, "after_points": after,
            "curve": [{"age": a, "value": round(v, 2)} for a, (_, v) in sorted(cv.items())],
        })
    out["matches"] = matches
    out["projection"] = trajectory.projection(afters) if active else None
    return out


@app.get("/api/skaters/{player_id}/similar")
def similar(player_id: int):
    params = {"season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        everyone = conn.execute(SKATERS_SQL, params).fetchall()
    player = next((r for r in everyone if r["player_id"] == player_id), None)
    if player is None:
        raise HTTPException(404, "Player not found")
    return _similar_players(everyone, player)


# --- Trade / availability context --------------------------------------------------------------
# The NHL feeds don't publish injuries or transactions, so this is inferred from game rows: a team
# change between games is a trade (or waiver claim), and a team game the player skipped is simply
# "not in the lineup" - the feed doesn't say whether that was injury, scratch, or suspension.

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


@app.get("/api/skaters/{player_id}/context")
def skater_context(player_id: int):
    return _context(player_id, goalie=False)


@app.get("/api/goalies/{player_id}/context")
def goalie_context(player_id: int):
    return _context(player_id, goalie=True)


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


@app.get("/api/head-to-head/teams")
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


@app.get("/api/head-to-head/player")
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


@app.get("/api/head-to-head/goalie")
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


# --- Playoff odds -------------------------------------------------------------------------------
_odds_cache = {"sig": None, "data": None}


@app.get("/api/playoff-odds")
def playoff_odds_endpoint():
    """Chance each team makes the playoffs and goes on to win each round and the Cup, from simulating the rest of the season
    and then the playoffs (see playoff_odds.py)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        teams = conn.execute(
            """SELECT abbrev, name, conference, division, games_played, points, reg_wins, goal_diff
               FROM team_season WHERE season_id = %s""", (config.SEASON_ID,)).fetchall()
        remaining = conn.execute(
            "SELECT home, away FROM game WHERE season_id = %s AND state NOT IN ('OFF', 'FINAL')",
            (config.SEASON_ID,)).fetchall()
    if not teams:
        raise HTTPException(404, "No standings yet")
    sig = (sum(t["games_played"] for t in teams), sum(t["points"] or 0 for t in teams), len(remaining))
    if _odds_cache["sig"] != sig:  # results only change when a game finishes, so reuse the run until then
        odds = playoff_odds.simulate(teams, [(g["home"], g["away"]) for g in remaining], seed=sig[0])
        _odds_cache.update(sig=sig, data={
            "sims": playoff_odds.SIMS, "games_remaining": len(remaining),
            "teams": [{**t, **odds[t["abbrev"]]} for t in teams],
        })
    return _odds_cache["data"]


# --- Schedule grid ------------------------------------------------------------------------------
@app.get("/api/schedule-grid")
def schedule_grid():
    """Games per team for every Monday-Sunday week from this week to the end of the regular season."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        first = today - timedelta(days=today.weekday())
        games = conn.execute(
            "SELECT game_date, home, away FROM game WHERE season_id = %s AND game_date >= %s ORDER BY game_date",
            (config.SEASON_ID, first)).fetchall()
        teams = conn.execute(
            "SELECT abbrev, name, conference, division FROM team_season WHERE season_id = %s ORDER BY name",
            (config.SEASON_ID,)).fetchall()
    if not games:
        return {"weeks": [], "teams": []}
    n_weeks = (games[-1]["game_date"] - first).days // 7 + 1
    weeks = [{"start": first + timedelta(days=7 * i), "end": first + timedelta(days=7 * i + 6)} for i in range(n_weeks)]
    by_team = {t["abbrev"]: [[] for _ in weeks] for t in teams}
    for g in games:
        w = (g["game_date"] - first).days // 7
        for team, opp, home in ((g["home"], g["away"], True), (g["away"], g["home"], False)):
            if team in by_team:
                by_team[team][w].append({"date": g["game_date"], "opp": opp, "home": home})
    out = []
    for t in teams:
        cells = []
        prev_last = None  # date of the previous game, to catch back-to-backs across a week boundary
        for wk in by_team[t["abbrev"]]:
            b2b = 0
            for g in wk:
                if prev_last and (g["date"] - prev_last).days == 1:
                    b2b += 1
                prev_last = g["date"]
            cells.append({"games": len(wk), "back_to_backs": b2b, "days": wk})
        out.append({**t, "weeks": cells, "total": sum(c["games"] for c in cells)})
    return {"weeks": weeks, "teams": out}


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


_rest_gaps_cache = {"key": None, "gaps": None}


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
        _rest_gaps_cache.update(key=key, gaps={k: eff[k]["goals_for"]["gap"] for k in ("tired", "edge")})
    return _rest_gaps_cache["gaps"], kinds


@app.get("/api/rest")
def rest_endpoint(days: int = 7):
    """How teams do on the second night of a back-to-back, from every stored game (this season and the previous four),
    each team's record in those games, and the next `days` days' games with each side's rest and travel (see
    fatigue.py). Travel distance and time zones had no detectable effect once rest and home ice were accounted for
    (analysis/travel_effects.py), so they are shown for context only."""
    days = max(1, min(days, 21))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        past, current, games = _team_games(conn)
        names = {r["abbrev"]: r["name"] for r in conn.execute(
            "SELECT abbrev, name FROM team_season WHERE season_id = %s", (config.SEASON_ID,))}
    rest = fatigue.rest_days(past + current)
    trav = fatigue.travel(past + current)
    finished = past + [r for r in current if r.get("done")]
    classified = list(fatigue.classify(finished, rest))
    lines = fatigue.team_lines(classified)
    left = defaultdict(lambda: {"back_to_backs_left": 0, "tired_left": 0})
    for r in current:
        if r.get("done"):
            continue
        k = fatigue.kind(rest[r["team"], r["game_id"]], rest.get((r["opponent"], r["game_id"]), fatigue.FIRST_GAME_REST))
        if k in ("tired", "both"):
            left[r["team"]]["back_to_backs_left"] += 1
        if k == "tired":
            left[r["team"]]["tired_left"] += 1
    fixtures = [{"game_id": g["game_id"], "game_date": g["game_date"], "home": g["home"], "away": g["away"]}
                for g in games if g["state"] not in ("OFF", "FINAL") and today <= g["game_date"] < today + timedelta(days=days)]
    fixtures.sort(key=lambda f: (f["game_date"], f["game_id"]))
    ahead = fatigue.upcoming(fixtures, rest)
    for u in ahead:
        for side, team in (("home", u["home"]), ("away", u["away"])):
            t = trav.get((team, u["game_id"]))
            u[f"{side}_travel"] = t and {"km": round(t["km"]), "hours_east": t["hours_east"], "road_game": t["road_game"]}
    teams = [{"abbrev": t, "name": names[t], **lines.get(t, {}), **left[t]} for t in sorted(names, key=names.get)]
    return {"season": config.SEASON_ID, "games_counted": len(classified), "effects": fatigue.effects(classified),
            "teams": teams, "upcoming": ahead}


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


@app.get("/api/probable-goalies")
def probable_goalies_endpoint(date: str | None = None):
    """Inferred starters for one day's games (default: today, Eastern). See probable_goalies.py."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        if date is None:
            day = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        else:
            try:
                day = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        games = conn.execute(
            "SELECT game_id, start_time, state, home, away FROM game "
            "WHERE season_id = %s AND game_date = %s ORDER BY start_time, game_id",
            (config.SEASON_ID, day)).fetchall()
        starts = conn.execute(
            """SELECT g.team, g.player_id, g.game_date, s.name FROM goalie_game g
               LEFT JOIN goalie_season s ON s.season_id = g.season_id AND s.player_id = g.player_id
               WHERE g.season_id = %s AND g.started AND g.game_date < %s ORDER BY g.game_date DESC, g.game_id DESC""",
            (config.SEASON_ID, day)).fetchall()
    by_team = {}
    for r in starts:
        by_team.setdefault(r["team"], []).append(r)

    # How often a goalie starts both ends of a back-to-back, league-wide this season so far.
    b2b = repeats = 0
    for rows in by_team.values():
        for newer, older in zip(rows, rows[1:]):
            if (newer["game_date"] - older["game_date"]).days == 1:
                b2b += 1
                repeats += newer["player_id"] == older["player_id"]
    p_repeat = probable_goalies.repeat_rate(b2b, repeats)

    def side(abbrev, confirmed):
        rows = by_team.get(abbrev, [])
        tired = bool(rows) and (day - rows[0]["game_date"]).days == 1
        candidates = probable_goalies.predict(
            [(r["player_id"], r["name"] or "Unknown") for r in rows], tired, p_repeat)
        if abbrev in confirmed:
            candidates = probable_goalies.apply_confirmed(candidates, confirmed[abbrev])
        return {"team": abbrev, "back_to_back": tired, "confirmed": abbrev in confirmed, "candidates": candidates}

    out = []
    for g in games:
        confirmed = _confirmed_starters(g)
        out.append({**g, "away_goalies": side(g["away"], confirmed), "home_goalies": side(g["home"], confirmed)})
    return {"date": day, "repeat_rate": round(p_repeat, 3), "games": out}


@app.get("/api/tonight")
def tonight_endpoint(date: str | None = None, ids: str = "", teams: str = ""):
    """A day's games (default today, Eastern), each with why it might be worth watching: how even the teams are, expected
    goals, the playoff race, the best scorers, the likely goalies, rest, and how many of your players (ids) or followed
    teams (teams) are in it. `score` and `reasons` come from tonight.py; the page sorts by them."""
    try:
        wanted = [int(i) for i in ids.split(",") if i.strip()][:300]
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    followed = {t.strip().upper() for t in teams.split(",") if t.strip()}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        if date is None:
            day = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        else:
            try:
                day = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
        games = conn.execute(
            "SELECT game_id, start_time, state, home, away FROM game WHERE season_id = %s AND game_date = %s "
            "ORDER BY start_time, game_id", (config.SEASON_ID, day)).fetchall()
        ratings, league = matchups_db.team_table(conn, config.SEASON_ID)
        skaters = conn.execute(
            "SELECT player_id, name, team, games_played, points FROM skater_season WHERE season_id = %s AND games_played > 0",
            (config.SEASON_ID,)).fetchall()
        goalies = conn.execute(
            "SELECT player_id, name, team FROM goalie_season WHERE season_id = %s AND player_id = ANY(%s)",
            (config.SEASON_ID, wanted)).fetchall() if wanted else []
        _, kinds = _rest_context(conn)
    by_team = {t["team"]: t for t in ratings}
    try:
        odds = {t["abbrev"]: t["make_playoffs"] for t in playoff_odds_endpoint()["teams"]}
    except HTTPException:
        odds = {}
    try:
        starters = {g["game_id"]: g for g in probable_goalies_endpoint(str(day))["games"]}
    except HTTPException:
        starters = {}

    stars, yours_by_team = {}, {}
    for r in skaters:
        team = (r["team"] or "").split(",")[-1]
        if r["games_played"] >= 5:
            stars.setdefault(team, []).append({"player_id": r["player_id"], "name": r["name"], "points": r["points"],
                                               "games_played": r["games_played"], "ppg": r["points"] / r["games_played"]})
        if r["player_id"] in wanted:
            yours_by_team.setdefault(team, []).append({"player_id": r["player_id"], "name": r["name"], "kind": "skater"})
    for r in goalies:
        yours_by_team.setdefault((r["team"] or "").split(",")[-1], []).append({"player_id": r["player_id"], "name": r["name"], "kind": "goalie"})
    for team in stars:
        stars[team].sort(key=lambda s: (-s["ppg"], s["name"]))

    def goalie(side):
        top = (side["candidates"] or [None])[0]
        return {"team": side["team"], "confirmed": side["confirmed"], "back_to_back": side["back_to_back"],
                "name": top["name"] if top else None, "player_id": top["player_id"] if top else None,
                "probability": top["probability"] if top else None}

    out = []
    for g in games:
        h, a = by_team.get(g["home"]), by_team.get(g["away"])
        win, total = tonight.matchup(h, a, league)
        top = sorted((stars.get(g["home"], [])[:1] + stars.get(g["away"], [])[:1]), key=lambda s: -s["ppg"])
        yours = yours_by_team.get(g["home"], []) + yours_by_team.get(g["away"], [])
        starter = starters.get(g["game_id"])
        graded = tonight.score_game(win, total, 2 * league["goals_pg"] if league else None,
                                    [odds.get(g["home"]), odds.get(g["away"])], top[0] if top else None,
                                    [y["name"] for y in yours], sorted(followed & {g["home"], g["away"]}))
        out.append({
            "game_id": g["game_id"], "start_time": g["start_time"], "state": g["state"], "home": g["home"], "away": g["away"],
            "home_info": {k: h[k] for k in ("name", "logo_url", "logo_dark_url")} if h else None,
            "away_info": {k: a[k] for k in ("name", "logo_url", "logo_dark_url")} if a else None,
            "home_win": win, "expected_goals": total,
            "odds": {"home": odds.get(g["home"]), "away": odds.get(g["away"])},
            "stars": {"home": stars.get(g["home"], [])[:2], "away": stars.get(g["away"], [])[:2]},
            "goalies": {"home": goalie(starter["home_goalies"]), "away": goalie(starter["away_goalies"])} if starter else None,
            "rest": {"home": kinds.get((g["home"], g["game_id"])), "away": kinds.get((g["away"], g["game_id"]))},
            "yours": yours, "followed": sorted(followed & {g["home"], g["away"]}), **graded,
        })
    return {"date": day, "games": out}


# --- Live scores --------------------------------------------------------------------------------
# The nightly ingest only knows finished games, so in-progress games come straight from the NHL's
# scoreboard, cached briefly so many visitors don't each hit the NHL API.
LIVE_TTL = 20  # seconds
_live_cache = {"at": 0.0, "data": None}


def _live_elapsed(game):
    """Seconds of regulation played in a live game from its period and clock (3600 or more once it is in overtime or a shootout)."""
    period = game["period"] or 1
    if period > 3:
        return winprob.REGULATION
    try:
        minutes, seconds = (game["time_remaining"] or "20:00").split(":")
        left = int(minutes) * 60 + int(seconds)
    except ValueError:
        left = 1200
    return (period - 1) * 1200 + (1200 - left)


def _add_live_win_probability(games):
    """Adds home_win (the home team's chance, see winprob.py) to each live game; leaves it out if the ratings cannot be had."""
    if not games:
        return
    try:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
            for g in games:
                gap = winprob_db.gap_before(conn, config.SEASON_ID, today, g["home"]["abbrev"], g["away"]["abbrev"])
                g["home_win"] = round(winprob.win_prob(g["home"]["score"] - g["away"]["score"], _live_elapsed(g), gap), 4)
    except psycopg.Error:
        pass


@app.get("/api/live")
def live():
    now = time.time()
    if _live_cache["data"] is None or now - _live_cache["at"] > LIVE_TTL:
        try:
            raw = requests.get(f"{config.WEB_API}/score/now", timeout=10).json()
        except (requests.RequestException, ValueError):
            if _live_cache["data"] is None:
                return {"games": []}
            raw = None  # NHL API hiccup: keep serving the last good copy
        if raw is not None:
            games = []
            for g in raw.get("games", []):
                if g.get("gameState") not in ("LIVE", "CRIT"):
                    continue
                clock, period = g.get("clock") or {}, g.get("periodDescriptor") or {}
                side = lambda t: {"abbrev": t.get("abbrev"), "score": t.get("score", 0), "shots": t.get("sog")}
                games.append({
                    "game_id": g["id"], "away": side(g.get("awayTeam", {})), "home": side(g.get("homeTeam", {})),
                    "period": period.get("number"), "period_type": period.get("periodType"),
                    "time_remaining": clock.get("timeRemaining"), "intermission": bool(clock.get("inIntermission")),
                })
            _add_live_win_probability(games)
            _live_cache.update(at=now, data={"games": games})
    return _live_cache["data"]


# --- Fantasy roster support ---------------------------------------------------------------------
FANTASY_DAYS = 7


@app.get("/api/fantasy/week")
def fantasy_week(ids: str = "", days: int = FANTASY_DAYS):
    """For a roster: each player's team games over the next `days` days plus lineup status."""
    try:
        wanted = [int(i) for i in ids.split(",") if i.strip()][:60]
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    days = max(1, min(days, 14))
    if not wanted:
        return {"from": None, "to": None, "players": {}}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        sk = {r["player_id"]: r for r in conn.execute(SKATERS_SQL, {
            "season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}).fetchall()
            if r["player_id"] in wanted}
        gl = {r["player_id"]: r for r in conn.execute(GOALIES_SQL, _goalie_params()).fetchall() if r["player_id"] in wanted}
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        end = today + timedelta(days=days - 1)
        games = conn.execute(
            """SELECT game_id, game_date, start_time, home, away FROM game
               WHERE season_id = %s AND game_date BETWEEN %s AND %s AND state NOT IN ('OFF', 'FINAL')
               ORDER BY game_date, game_id""",
            (config.SEASON_ID, today, end),
        ).fetchall()
        gaps, kinds = _rest_context(conn)
        teams_table, league = matchups_db.team_table(conn, config.SEASON_ID)
    ratings = {t["team"]: t for t in teams_table}
    goals_pg = league.get("goals_pg") if league else None
    by_team = {}
    for g in games:
        for team, opp, home in ((g["home"], g["away"], True), (g["away"], g["home"], False)):
            # matchup ratios already include the rest adjustment: "tired" is the second night of a back-to-back against
            # a rested team, "edge" its mirror image (see fatigue.py and matchups.py)
            by_team.setdefault(team, []).append({**g, "opponent": opp, "home_game": home,
                                                 **_game_ratios(ratings.get(opp), kinds.get((team, g["game_id"])), gaps, goals_pg)})
    players = {}
    for pid in wanted:
        row, kind = (sk.get(pid), "skater") if pid in sk else (gl.get(pid), "goalie")
        if not row:
            continue
        team = (row["team"] or "").split(",")[-1]
        players[str(pid)] = {
            "kind": kind, "team": team, "games": by_team.get(team, []),
            "games_out": row.get("games_out"), "traded": bool(row.get("traded")),
        }
    return {"from": today, "to": end, "players": players}


# --- Trophy races ------------------------------------------------------------------------------
# "In contention" is a stats-only proxy: a player is listed when they sit in the top CONTENTION_SIZE
# (ties included) for the trophy's deciding stat. Voted awards (Hart, Selke, Lady Byng...) turn on
# narrative and defensive judgement the data can't capture, so only the stat-driven ones are here.
CONTENTION_SIZE = 5

TROPHIES = [
    # (name, kind, stat, "what decides it", pool filter)
    ("Art Ross Trophy", "skater", "points", "most points", lambda r, gp: True),
    ("Maurice Richard Trophy", "skater", "goals", "most goals", lambda r, gp: True),
    ("Norris Trophy", "skater", "points", "top-scoring defensemen (a stats-only proxy; voters also weigh defense)",
     lambda r, gp: r["position"] == "D"),
    ("Calder Trophy", "skater", "points", "top-scoring rookies",
     lambda r, gp: bool(r["rookie"]) and (r.get("age") or 99) <= 25),
    ("Vezina Trophy", "goalie", "gsaa", "most goals saved above average among goalies with at least half the busiest goalie's games",
     lambda r, gp: r["games_played"] >= gp),
]


def _contenders(skater_rows, goalie_rows):
    """{player_id: [{trophy, rank, of, stat, value, basis}]} for everyone in a trophy's top group."""
    out = {}
    max_goalie_gp = max((g["games_played"] for g in goalie_rows), default=0)
    goalie_floor = max(1, -(-max_goalie_gp // 2))
    for trophy, kind, stat, basis, keep in TROPHIES:
        rows = skater_rows if kind == "skater" else goalie_rows
        pool = [r for r in rows if r.get(stat) is not None and keep(r, goalie_floor)]
        for r in pool:
            better = sum(1 for o in pool if o[stat] > r[stat])
            if better < CONTENTION_SIZE:
                out.setdefault(r["player_id"], []).append({
                    "trophy": trophy, "rank": better + 1, "of": len(pool),
                    "stat": stat, "value": r[stat], "basis": basis,
                })
    for lst in out.values():
        lst.sort(key=lambda t: t["rank"])
    return out


_award_cache = {"sig": None, "data": None}
AWARD_NAMES = {"hart": "Hart Trophy", "norris": "Norris Trophy", "calder": "Calder Trophy", "selke": "Selke Trophy", "vezina": "Vezina Trophy"}
RATE_PRIOR_GAMES = 25   # early in the season a shot-attempt share, faceoff share or takeaway rate is pulled toward average, worth this many games (a guess)
AWARD_SHOWN = 8       # candidates listed per award
Z80 = 1.2816


@app.get("/api/award-odds")
def award_odds_endpoint():
    """Win chances for the Hart, Norris, Calder, Selke and Vezina from the stats voters have rewarded in past seasons, applied to many
    plausible finishes for the season (see awards.py)."""
    skaters = projections_endpoint(limit=1000)["rows"]
    goalies = projections_goalies(limit=300)["rows"]
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        sk_rows = {r["player_id"]: r for r in conn.execute(SKATERS_SQL, {
            "season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}).fetchall()}
        gl_rows = {r["player_id"]: r for r in conn.execute(GOALIES_SQL, _goalie_params()).fetchall()}
    sig = (sum(r["games_played"] for r in sk_rows.values()), sum(r["games_played"] or 0 for r in gl_rows.values()))
    if _award_cache["sig"] == sig:
        return _award_cache["data"]
    try:
        team_odds = playoff_odds_endpoint()["teams"]
    except HTTPException:
        team_odds = []
    teams = {t["abbrev"]: (t["exp_points"], max(1.0, (t["p90_points"] - t["p10_points"]) / (2 * Z80))) for t in team_odds}

    skater_cands = []
    league_tk = sum(r["takeaways"] or 0 for r in sk_rows.values()) / max(1, sum(r["games_played"] for r in sk_rows.values()))
    for p in skaters:
        r = sk_rows.get(p["player_id"])
        if not r:
            continue
        gp = p["games_played"]
        shrink = gp / (gp + RATE_PRIOR_GAMES)
        final_gp = gp + p["expected_games"]
        tk_rate = ((r["takeaways"] or 0) + RATE_PRIOR_GAMES * league_tk) / (gp + RATE_PRIOR_GAMES)
        skater_cands.append({
            "id": p["player_id"], "name": p["name"], "team": (p["team"] or "").split(",")[-1], "pos": p["position"], "points": p["points"],
            "goals": p["goals"], "toi_pg": r["toi_per_game_sec"], "rookie": bool(r["rookie"]) and (r.get("age") or 99) <= awards.ROOKIE_MAX_AGE,
            "age": r.get("age"), "games_played": gp, "final_gp": final_gp,
            "sat": 0.5 + ((r["sat_pct"] or 0.5) - 0.5) * shrink, "sat_now": r["sat_pct"], "sh": r["sh_toi_per_game"] or 0,
            "fo": 0.5 + ((r["fo_win_pct"] or 0.5) - 0.5) * shrink, "fo_n": 1000 if p["position"] == "C" and r["fo_win_pct"] is not None else 0,
            "takeaways": r["takeaways"] or 0, "final_takeaways": (r["takeaways"] or 0) + tk_rate * p["expected_games"],
            "final_points": p["final_points"], "sd_points": max(0.5, (p["high_points"] - p["low_points"]) / (2 * Z80))})
    goalie_cands = []
    for p in goalies:
        r = gl_rows.get(p["player_id"])
        if not r or not p["final_shots"]:
            continue
        league_sv = r["league_sv_pct"] or 0.9
        rest_shots = p["rest_shots"]
        goalie_cands.append({
            "id": p["player_id"], "name": p["name"], "team": (p["team"] or "").split(",")[-1], "wins": p["wins"],
            "gsaa": p["saves"] - league_sv * (p["final_shots"] - rest_shots), "final_gp": p["final_starts"], "final_wins": p["final_wins"], "sd_wins": math.sqrt(0.25 * p["rest_starts"]),
            "final_gsaa": p["final_saves"] - league_sv * p["final_shots"],
            "sd_gsaa": math.sqrt(0.09 * rest_shots + (0.007 * rest_shots) ** 2), "games_played": p["games_played"]})
    by_id = {c["id"]: c for c in skater_cands + goalie_cands}
    out = {}
    for award in awards.AWARDS:
        if award == "vezina":
            cands = sorted(goalie_cands, key=lambda c: -c["final_wins"])[:16]
        elif award == "norris":
            cands = sorted((c for c in skater_cands if c["pos"] == "D"), key=lambda c: -c["final_points"])[:20]
        elif award == "calder":
            cands = sorted((c for c in skater_cands if c["rookie"]), key=lambda c: -c["final_points"])[:20]
        elif award == "selke":
            fwd = [c for c in skater_cands if c["pos"] in ("C", "L", "R")]
            rank = {c["id"]: 0 for c in fwd}
            for stat in ("final_points", "sat", "sh"):
                for place, c in enumerate(sorted(fwd, key=lambda c: (-c[stat], c["id"]))):
                    rank[c["id"]] += place
            cands = sorted(fwd, key=lambda c: (rank[c["id"]], c["id"]))[:40]
        else:
            cands = sorted(skater_cands, key=lambda c: -c["final_points"])[:40]
        chances = awards.odds(award, cands, teams, games=config.GAMES_PER_SEASON, seed=sig[0])
        ranked = sorted(chances.items(), key=lambda kv: (-kv[1], by_id[kv[0]]["name"]))[:AWARD_SHOWN]
        rows = []
        for pid, p in ranked:
            c = by_id[pid]
            rows.append({"player_id": pid, "name": c["name"], "team": c["team"], "chance": p, "games_played": c["games_played"],
                         **({"wins": c["wins"], "final_wins": c["final_wins"], "final_gsaa": c["final_gsaa"]} if award == "vezina"
                            else {"points": c["points"], "final_points": c["final_points"], "sat": c["sat_now"]})})
        out[award] = {"trophy": AWARD_NAMES[award], "backtest": awards.BACKTEST[award], "candidates": rows}
    data = {"season": config.SEASON_ID, "draws": awards.DRAWS, "awards": out}
    _award_cache.update(sig=sig, data=data)
    return data


_absence_cache = {"sig": None, "data": None}


@app.get("/api/absences")
def absences_endpoint():
    """Regulars who have missed their team's latest games (inferred from the box scores, since the NHL publishes no injury list) and what their
    teammates in the same position group are getting: the average extra ice time for a teammate in that spot, from four seasons of games, and
    what each has actually played in the games missed so far. See absences.py and its backtest."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        sig = tuple(conn.execute("SELECT count(*) AS n, max(game_date) AS d FROM skater_game_toi WHERE season_id = %s", (config.SEASON_ID,)).fetchone().values())
        if _absence_cache["sig"] != sig:
            _absence_cache.update(sig=sig, data={"season": config.SEASON_ID, "absences": absences_db.current(conn, config.SEASON_ID)})
    return _absence_cache["data"]


@app.get("/api/trophy-races")
def trophy_races():
    """Each stat-driven trophy with its current contenders, best first."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        sk = conn.execute(SKATERS_SQL, {"season": config.SEASON_ID, "window": config.RECENT_WINDOW,
                                        "games": config.GAMES_PER_SEASON}).fetchall()
        gl = conn.execute(GOALIES_SQL, _goalie_params()).fetchall()
    by_id = {r["player_id"]: r for r in sk} | {r["player_id"]: r for r in gl}
    races = {t[0]: {"trophy": t[0], "stat": t[2], "basis": t[3], "contenders": []} for t in TROPHIES}
    for pid, entries in _contenders(sk, gl).items():
        r = by_id[pid]
        for e in entries:
            races[e["trophy"]]["contenders"].append({
                "player_id": pid, "name": r["name"], "team": r["team"], "rank": e["rank"],
                "value": e["value"], "games_played": r["games_played"],
            })
    for race in races.values():
        race["contenders"].sort(key=lambda c: (c["rank"], c["name"]))
    return {"size": CONTENTION_SIZE, "races": list(races.values())}


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


def _team_codes():
    """{team id: abbreviation} for every franchise past and present. Empty if the stats API won't answer, which only costs the
    team column (the winners themselves don't depend on it)."""
    try:
        return {t["id"]: t["triCode"] for t in _records_rows(f"{config.STATS_API}/team")}
    except HTTPException:
        return {}


@app.get("/api/trophy-index")
def trophy_index():
    """Every NHL trophy with the key that matches it to the award names on player pages."""
    rows = _records_rows(f"{RECORDS_API}/trophy")
    return {"trophies": [{"id": t["id"], "name": t["name"], "key": trophy_lib.key(t["name"])} for t in rows]}


@app.get("/api/trophy-summary")
def trophy_summary():
    """The trophy index: every trophy grouped by kind, with its newest winner and first season."""
    from concurrent.futures import ThreadPoolExecutor

    infos = _records_rows(f"{RECORDS_API}/trophy")
    teams = _team_codes()

    def one(info):
        rows = _records_rows(f"{RECORDS_API}/award-details", cayenneExp=f"trophyId={info['id']}")
        return trophy_lib.summary(info, trophy_lib.winners(rows, info["categoryId"], teams))

    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(one, infos))
    groups = []
    for title, ids in trophy_lib.CATEGORY_GROUPS:
        members = [r for r in rows if r["category_id"] in ids]
        if members:
            groups.append({"title": title, "trophies": sorted(members, key=lambda r: r["name"])})
    other = [r for r in rows if trophy_lib.group_of(r["category_id"]) == "Other"]
    if other:
        groups.append({"title": "Other", "trophies": sorted(other, key=lambda r: r["name"])})
    return {"groups": groups}


@app.get("/api/trophy/{trophy_id}")
def trophy(trophy_id: int):
    """One trophy's winners by season. The scoring awards (Art Ross, Richard) carry the winner's season totals."""
    info = next((t for t in _records_rows(f"{RECORDS_API}/trophy") if t["id"] == trophy_id), None)
    if info is None:
        raise HTTPException(404, "Trophy not found")
    teams = _team_codes()
    rows = _records_rows(f"{RECORDS_API}/award-details", cayenneExp=f"trophyId={trophy_id}")
    winner_rows = trophy_lib.winners(rows, info["categoryId"], teams)
    columns = trophy_lib.STAT_AWARDS.get(trophy_id)
    if columns:
        ids = [w["player_id"] for w in winner_rows if w["player_id"] is not None]
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            lines = conn.execute(
                "SELECT player_id, season_id, games_played, goals, assists, points FROM career_season WHERE player_id = ANY(%s)",
                (ids,)).fetchall()
        trophy_lib.add_stats(winner_rows, {(l["player_id"], l["season_id"]): l for l in lines}, columns)
    return {"id": trophy_id, "name": info["name"], "description": info.get("briefDescription"),
            "is_team": info["categoryId"] == trophy_lib.TEAM_CATEGORY, "stat_columns": columns, "winners": winner_rows}


@app.get("/api/trophies")
def trophies():
    """Who is in contention for each stat-driven trophy this season, keyed by player id."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        sk = conn.execute(SKATERS_SQL, {"season": config.SEASON_ID, "window": config.RECENT_WINDOW,
                                        "games": config.GAMES_PER_SEASON}).fetchall()
        gl = conn.execute(GOALIES_SQL, _goalie_params()).fetchall()
    return {"size": CONTENTION_SIZE, "players": {str(k): v for k, v in _contenders(sk, gl).items()}}


# --- All-time boards ---------------------------------------------------------------------------
# Sort keys are whitelisted because they're interpolated into SQL (everything else is bound).
ALLTIME_TABLES = {"skater": "career_skater", "goalie": "career_goalie"}
ALLTIME_SORTS = {
    "skater": {"name", "first_season", "games_played", "goals", "assists", "points", "points_per_game",
               "plus_minus", "pim", "ev_goals", "pp_goals", "pp_points", "sh_goals", "sh_points",
               "game_winning_goals", "ot_goals", "shots", "shooting_pct", "fo_win_pct", "hits", "blocked_shots",
               "takeaways", "giveaways", "missed_shots", "shot_attempts", "empty_net_goals", "first_goals",
               "adj_goals", "adj_assists", "adj_points", "adj_points_per_game"},
    "goalie": {"name", "first_season", "games_played", "games_started", "wins", "losses", "ot_losses",
               "ties", "saves", "shots_against", "goals_against", "save_pct", "gaa", "shutouts", "toi_sec"},
}


# --- Era adjustment ---------------------------------------------------------------------------
_era_cache = {"sig": None, "data": None}


@app.get("/api/era-factors")
def era_factors():
    """Per-season, per-role multipliers that turn goals and assists into today's scoring terms (see era.py)."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        sig = conn.execute("SELECT count(*), coalesce(sum(points), 0) FROM career_season").fetchone()
        if _era_cache["sig"] != sig:
            rows = era.load_rows(conn)
            rates = era.league_rates(rows)
            ref = era.reference_rates(rates, config.SEASON_ID - 10001)
            fac = era.factors(rates, ref)
            seasons = {}
            for (season, rl), f in fac.items():
                seasons.setdefault(str(season), {})[rl] = {k: round(v, 4) for k, v in f.items()}
            _era_cache.update(sig=sig, data={
                "reference_seasons": [config.SEASON_ID - 10001 * i for i in range(1, era.REFERENCE_SEASONS + 1)],
                "today": {rl: {k: round(v, 4) for k, v in r.items()} for rl, r in ref.items()}, "seasons": seasons})
    return _era_cache["data"]


@app.get("/api/alltime/{kind}")
def alltime(
    kind: str,
    game_type: int = 2,
    sort: str | None = None,
    dir: str = "desc",
    q: str = "",
    position: str = "",
    country: str = "",
    active: bool = False,
    hof: bool = False,
    min_gp: int = 0,
    debut_from: int | None = None,
    debut_to: int | None = None,
    limit: int = 50,
    offset: int = 0,
    export: bool = False,
):
    """Career totals for every player in NHL history, sorted/filtered/paged server-side."""
    if kind not in ALLTIME_TABLES:
        raise HTTPException(404, "Unknown board")
    if game_type not in (2, 3):
        raise HTTPException(400, "game_type must be 2 (regular season) or 3 (playoffs)")
    default_sort = "points" if kind == "skater" else "wins"
    sort = sort or default_sort
    if sort not in ALLTIME_SORTS[kind]:
        raise HTTPException(400, f"Can't sort by {sort}")
    direction = "ASC" if dir.lower() == "asc" else "DESC"
    limit, offset = max(1, min(limit, 10000 if export else 200)), max(0, offset)

    where, params = ["game_type = %(game_type)s"], {"game_type": game_type}
    if q.strip():
        where.append("name ILIKE %(q)s")
        params["q"] = f"%{q.strip()}%"
    if kind == "skater" and position:
        if position == "F":
            where.append("position <> 'D'")
        else:
            where.append("position = %(position)s")
            params["position"] = position
    if country:
        where.append("birth_country = %(country)s")
        params["country"] = country
    if active:
        where.append("active_season IS NOT NULL")
    if hof:
        where.append("hall_of_fame = 'Y'")
    if min_gp > 0:
        where.append("games_played >= %(min_gp)s")
        params["min_gp"] = min_gp
    if debut_from is not None:
        where.append("first_season >= %(debut_from)s")
        params["debut_from"] = debut_from * 10000 + debut_from + 1
    if debut_to is not None:
        where.append("first_season <= %(debut_to)s")
        params["debut_to"] = debut_to * 10000 + debut_to + 1

    table, clause = ALLTIME_TABLES[kind], " AND ".join(where)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        total = conn.execute(f"SELECT count(*) AS n FROM {table} WHERE {clause}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE {clause} "
            f"ORDER BY {sort} {direction} NULLS LAST, name LIMIT %(limit)s OFFSET %(offset)s",
            {**params, "limit": limit, "offset": offset},
        ).fetchall()
    for r in rows:
        r.pop("updated_at", None)
    return {"total": total, "offset": offset, "limit": limit, "sort": sort, "dir": direction.lower(), "rows": rows}


@app.get("/api/alltime/{kind}/countries")
def alltime_countries(kind: str):
    if kind not in ALLTIME_TABLES:
        raise HTTPException(404, "Unknown board")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            f"SELECT birth_country AS c, count(*) AS n FROM {ALLTIME_TABLES[kind]} "
            "WHERE game_type = 2 AND birth_country IS NOT NULL GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()
    return [r["c"] for r in rows]


# --- Native pages for any player, including retired ones -----------------------------------------
# (stat, higher_is_better, min games to qualify for a rank). Rate stats need a floor so a one-game
# career can't rank first.
RANKED_STATS = {
    "skater": [
        ("games_played", True, 0), ("goals", True, 0), ("assists", True, 0), ("points", True, 0),
        ("points_per_game", True, 300), ("plus_minus", True, 0), ("pim", True, 0),
        ("pp_goals", True, 0), ("game_winning_goals", True, 0), ("shots", True, 0),
        ("hits", True, 0), ("blocked_shots", True, 0), ("takeaways", True, 0), ("giveaways", True, 0),
    ],
    "goalie": [
        ("games_played", True, 0), ("wins", True, 0), ("shutouts", True, 0), ("saves", True, 0),
        ("save_pct", True, 150), ("gaa", False, 150),
    ],
}


def _alltime_ranks(conn, kind, table, player_id):
    """Where a player's career ranks among everyone in NHL history, per game type and stat."""
    ranks = {}
    for game_type in (2, 3):
        row = conn.execute(
            f"SELECT * FROM {table} WHERE player_id = %s AND game_type = %s", (player_id, game_type)
        ).fetchone()
        if not row:
            continue
        group = {}
        for stat, higher, min_gp in RANKED_STATS[kind]:
            value = row[stat]
            if value is None or (min_gp and (row["games_played"] or 0) < min_gp):
                continue
            op = ">" if higher else "<"
            better = conn.execute(
                f"SELECT count(*) AS n FROM {table} WHERE game_type = %s AND {stat} IS NOT NULL "
                f"AND {stat} {op} %s" + (" AND games_played >= %s" if min_gp else ""),
                (game_type, value, min_gp) if min_gp else (game_type, value),
            ).fetchone()["n"]
            of = conn.execute(
                f"SELECT count(*) AS n FROM {table} WHERE game_type = %s AND {stat} IS NOT NULL"
                + (" AND games_played >= %s" if min_gp else ""),
                (game_type, min_gp) if min_gp else (game_type,),
            ).fetchone()["n"]
            group[stat] = {"value": value, "rank": better + 1, "of": of}
        ranks["regular" if game_type == 2 else "playoffs"] = group
    return ranks


# Current-season rank stats: (stat, higher_is_better, is_rate). Rate stats only rank players with at
# least half the games of the busiest player, so a three-game sample can't top the league.
SEASON_RANKED = {
    "skater": [
        ("games_played", True, False), ("goals", True, False), ("assists", True, False), ("points", True, False),
        ("point_pace", True, True), ("plus_minus", True, False), ("shots", True, False), ("pp_points", True, False),
        ("hits", True, False), ("blocked_shots", True, False), ("takeaways", True, False), ("pim", True, False),
    ],
    "goalie": [
        ("games_played", True, False), ("wins", True, False), ("shutouts", True, False), ("saves", True, False),
        ("save_pct", True, True), ("gaa", False, True), ("gsaa", True, False),
    ],
}


def _season_ranks(conn, kind, player_id):
    table = "skater_season" if kind == "skater" else "goalie_season"
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE season_id = %s AND games_played > 0", (config.SEASON_ID,)
    ).fetchall()
    me = next((r for r in rows if r["player_id"] == player_id), None)
    if not me:
        return {}, 0
    floor = max(1, -(-max(r["games_played"] for r in rows) // 2))
    out = {}
    for stat, higher, is_rate in SEASON_RANKED[kind]:
        if me.get(stat) is None or (is_rate and me["games_played"] < floor):
            continue
        pool = [r[stat] for r in rows if r.get(stat) is not None and (not is_rate or r["games_played"] >= floor)]
        better = sum(1 for v in pool if (v > me[stat] if higher else v < me[stat]))
        out[stat] = {"value": me[stat], "rank": better + 1, "of": len(pool)}
    return out, floor


@app.get("/api/players/{player_id}/rankings")
def player_rankings(player_id: int):
    """Rank this season among current players, and career rank among everyone in NHL history."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        for kind, table in ALLTIME_TABLES.items():
            if conn.execute(f"SELECT 1 FROM {table} WHERE player_id = %s", (player_id,)).fetchone():
                break
        else:
            raise HTTPException(404, "Player not found")
        season, floor = _season_ranks(conn, kind, player_id)
        return {
            "kind": kind, "season": season, "season_min_gp": floor,
            "alltime": _alltime_ranks(conn, kind, table, player_id),
        }


@app.get("/api/players/{player_id}/profile")
def player_profile(player_id: int):
    """Who a player is (skater/goalie, current or retired) plus where their career ranks all-time."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        for kind, table in ALLTIME_TABLES.items():
            me = conn.execute(
                f"SELECT * FROM {table} WHERE player_id = %s AND game_type = 2", (player_id,)
            ).fetchone()
            if me:
                break
        else:
            # Only played playoff games? Fall back to the playoff row to identify them.
            for kind, table in ALLTIME_TABLES.items():
                me = conn.execute(f"SELECT * FROM {table} WHERE player_id = %s AND game_type = 3", (player_id,)).fetchone()
                if me:
                    break
            else:
                raise HTTPException(404, "Player not found")

        ranks = _alltime_ranks(conn, kind, table, player_id)

        current = conn.execute(
            f"SELECT 1 FROM {'skater_season' if kind == 'skater' else 'goalie_season'} "
            "WHERE season_id = %s AND player_id = %s AND games_played > 0",
            (config.SEASON_ID, player_id),
        ).fetchone() is not None

    return {
        "kind": kind, "current": current, "name": me["name"], "position": me.get("position") or "G",
        "active_season": me["active_season"], "hall_of_fame": me["hall_of_fame"] == "Y",
        "ranks": ranks,
    }


# --- Home dashboard -----------------------------------------------------------------------------
STREAKS_SQL = """
WITH g AS (
    SELECT player_id, points, goals,
           row_number() OVER (PARTITION BY player_id ORDER BY game_date DESC, game_id DESC) AS rn
    FROM skater_game WHERE season_id = %(season)s
),
agg AS (
    SELECT player_id, count(*) AS games,
           min(rn) FILTER (WHERE points = 0) AS first_pointless,
           min(rn) FILTER (WHERE points > 0) AS first_point,
           min(rn) FILTER (WHERE goals = 0) AS first_goalless
    FROM g GROUP BY player_id
)
SELECT a.player_id,
       COALESCE(a.first_pointless, a.games + 1) - 1 AS point_streak,
       COALESCE(a.first_point, a.games + 1) - 1 AS pointless_streak,
       COALESCE(a.first_goalless, a.games + 1) - 1 AS goal_streak
FROM agg a
"""


@app.get("/api/home")
def home():
    today = datetime.now().date()
    params = {"season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        latest = conn.execute(
            "SELECT max(game_date) AS d FROM game WHERE season_id = %s AND state IN ('OFF', 'FINAL')",
            (config.SEASON_ID,),
        ).fetchone()["d"]
        games = conn.execute(
            """SELECT game_id, game_date, home, away, home_score, away_score, last_period, venue
               FROM game WHERE season_id = %s AND game_date = %s AND state IN ('OFF', 'FINAL')
               ORDER BY start_time, game_id""",
            (config.SEASON_ID, latest),
        ).fetchall() if latest else []

        performers = conn.execute(
            """SELECT g.player_id, s.name, g.team, g.opponent, g.is_home, s.position, g.goals, g.assists,
                      g.points, g.shots, g.plus_minus, g.game_id
               FROM skater_game g JOIN skater_season s ON s.player_id = g.player_id AND s.season_id = g.season_id
               WHERE g.season_id = %s AND g.game_date = %s
               ORDER BY g.points DESC, g.goals DESC, g.shots DESC NULLS LAST LIMIT 8""",
            (config.SEASON_ID, latest),
        ).fetchall() if latest else []
        goalie_nights = conn.execute(
            """SELECT g.player_id, s.name, g.team, g.opponent, g.shots_against, g.saves, g.goals_against,
                      g.decision, round(g.saves::numeric / NULLIF(g.shots_against, 0), 3)::float AS save_pct
               FROM goalie_game g JOIN goalie_season s ON s.player_id = g.player_id AND s.season_id = g.season_id
               WHERE g.season_id = %s AND g.game_date = %s AND g.shots_against >= 15
               ORDER BY g.saves::float / g.shots_against DESC, g.shots_against DESC LIMIT 3""",
            (config.SEASON_ID, latest),
        ).fetchall() if latest else []

        next_day = conn.execute(
            "SELECT min(game_date) AS d FROM game WHERE season_id = %s AND state IN ('FUT', 'PRE', 'LIVE', 'CRIT') AND game_date >= %s",
            (config.SEASON_ID, today),
        ).fetchone()["d"]
        upcoming = conn.execute(
            """SELECT game_id, game_date, start_time, home, away, venue, state, home_score, away_score
               FROM game WHERE season_id = %s AND game_date = %s ORDER BY start_time, game_id""",
            (config.SEASON_ID, next_day),
        ).fetchall() if next_day else []

        skaters = conn.execute(SKATERS_SQL, params).fetchall()
        streaks = {r["player_id"]: r for r in conn.execute(STREAKS_SQL, params).fetchall()}
        top_goalies = conn.execute(GOALIES_SQL, _goalie_params()).fetchall()
        top_teams = conn.execute(TEAMS_SQL, {"season": config.SEASON_ID, "games": config.GAMES_PER_SEASON}).fetchall()[:6]

    min_gp = max(1, -(-max(r["games_played"] for r in skaters) // 2))
    qualified = [r for r in skaters if r["games_played"] >= min_gp]

    def slim(r, **extra):
        return {"player_id": r["player_id"], "name": r["name"], "team": r["team"], "position": r["position"],
                "games_played": r["games_played"], "goals": r["goals"], "assists": r["assists"],
                "points": r["points"], "toi_per_game_sec": r["toi_per_game_sec"], **extra}

    hot = sorted((r for r in skaters if streaks.get(r["player_id"], {}).get("point_streak", 0) >= 3),
                 key=lambda r: (-streaks[r["player_id"]]["point_streak"], -r["points"]))[:8]
    cold = sorted(
        (r for r in skaters
         if r["position"] != "D" and (r["toi_per_game_sec"] or 0) >= 17 * 60
         and streaks.get(r["player_id"], {}).get("pointless_streak", 0) >= 3),
        key=lambda r: (-streaks[r["player_id"]]["pointless_streak"], -(r["toi_per_game_sec"] or 0)))[:8]
    goal_pace = sorted(qualified, key=lambda r: -(r["goals"] / r["games_played"]))[:5]

    return {
        "last_game_day": latest,
        "games": games,
        "performers": performers,
        "goalie_nights": goalie_nights,
        "upcoming_day": next_day,
        "upcoming": upcoming,
        "hot": [slim(r, streak=streaks[r["player_id"]]["point_streak"]) for r in hot],
        "cold": [slim(r, streak=streaks[r["player_id"]]["pointless_streak"]) for r in cold],
        "point_pace": [slim(r, pace=r["point_pace"]) for r in sorted(qualified, key=lambda r: -(r["point_pace"] or 0))[:5]],
        "goal_pace": [slim(r, pace=round(r["goals"] / r["games_played"] * config.GAMES_PER_SEASON, 1)) for r in goal_pace],
        "goalies": [
            {"player_id": g["player_id"], "name": g["name"], "team": g["team"], "games_played": g["games_played"],
             "save_pct": g["save_pct"], "gaa": g["gaa"], "gsaa": g["gsaa"], "wins": g["wins"]}
            for g in sorted((g for g in top_goalies if g["games_played"] >= max(1, min_gp // 2)), key=lambda g: -(g["gsaa"] or 0))[:5]
        ],
        "teams": [{k: t[k] for k in ("abbrev", "name", "logo_url", "logo_dark_url", "games_played", "wins", "losses", "ot_losses", "points", "points_pace", "goal_diff")} for t in top_teams],
        "min_gp": min_gp,
        "games_per_season": config.GAMES_PER_SEASON,
    }


# --- Milestone watch ----------------------------------------------------------------------------
MILESTONES = {
    "skater": {
        "goals": ("Goals", [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]),
        "assists": ("Assists", [100, 250, 500, 750, 1000, 1250, 1500]),
        "points": ("Points", [250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2500]),
        "games_played": ("Games played", [250, 500, 750, 1000, 1250, 1500]),
    },
    "goalie": {
        "wins": ("Wins", [50, 100, 150, 200, 250, 300, 350, 400, 500, 600]),
        "shutouts": ("Shutouts", [10, 25, 50, 75, 100]),
        "games_played": ("Games played", [100, 250, 500, 750, 1000]),
    },
}
# Smallest milestone worth headlining for each stat; the rest are shown only when asked for.
MAJOR_FROM = {
    "skater": {"goals": 300, "assists": 500, "points": 750, "games_played": 1000},
    "goalie": {"wins": 200, "shutouts": 25, "games_played": 500},
}
MILESTONE_MAX_GAMES = 90  # only show milestones within roughly a season's reach


def _milestone_rows(conn, kind):
    """Active players with their career totals (before this season) and this season's totals."""
    career_t = ALLTIME_TABLES[kind]
    season_t = "skater_season" if kind == "skater" else "goalie_season"
    stats = list(MILESTONES[kind])
    cols_c = ", ".join(f"c.{s} AS career_{s}" for s in stats)
    cols_s = ", ".join(f"s.{s} AS season_{s}" for s in stats if s != "games_played")
    return conn.execute(
        f"""SELECT s.player_id, s.name, s.team, s.games_played AS season_gp, {cols_c}, {cols_s},
                   t.games_played AS team_gp
            FROM {season_t} s
            JOIN {career_t} c ON c.player_id = s.player_id AND c.game_type = 2
            LEFT JOIN team_season t ON t.season_id = s.season_id AND t.abbrev = split_part(s.team, ',', 1)
            WHERE s.season_id = %s AND s.games_played > 0""",
        (config.SEASON_ID,),
    ).fetchall()


@app.get("/api/milestones")
def milestones():
    upcoming, reached = [], []
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        for kind in ("skater", "goalie"):
            for r in _milestone_rows(conn, kind):
                team_gp = r["team_gp"] or r["season_gp"]
                team_left = max(0, config.GAMES_PER_SEASON - team_gp)
                # Share of team games this player appears in (matters for goalies who split starts).
                appear = min(1.0, r["season_gp"] / team_gp) if team_gp else 1.0
                expected_left = team_left * appear
                for stat, (label, steps) in MILESTONES[kind].items():
                    now = r[f"career_{stat}"]
                    if now is None:
                        continue
                    season_total = r["season_gp"] if stat == "games_played" else (r[f"season_{stat}"] or 0)
                    before = now - season_total
                    base = {"player_id": r["player_id"], "name": r["name"], "team": r["team"], "kind": kind,
                            "stat": stat, "label": label}
                    major_from = MAJOR_FROM[kind][stat]
                    # Crossed during this season: find the game it happened in.
                    for m in (s for s in steps if before < s <= now):
                        reached.append({**base, "milestone": m, "now": now, "before": before, "major": m >= major_from})
                    nxt = next((s for s in steps if s > now), None)
                    if nxt is None:
                        continue
                    # Pace: this season's rate once it's a real sample, otherwise the career rate.
                    career_gp = r["career_games_played"] or 0
                    if stat == "games_played":
                        rate = 1.0  # one per appearance
                    elif r["season_gp"] >= 20:
                        rate = season_total / r["season_gp"]
                    else:
                        rate = (now / career_gp) if career_gp else 0
                    if rate <= 0:
                        continue
                    remaining = nxt - now
                    need = math.ceil(remaining / rate)
                    if need > MILESTONE_MAX_GAMES:
                        continue
                    upcoming.append({**base, "now": now, "milestone": nxt, "remaining": remaining,
                                     "rate": round(rate, 3), "games_needed": need,
                                     "major": nxt >= major_from, "this_season": need <= expected_left,
                                     "rate_source": "this season" if r["season_gp"] >= 20 and stat != "games_played" else "career"})

        # Dates for milestones reached this season, from the player's game log.
        for item in reached:
            table = "skater_game" if item["kind"] == "skater" else "goalie_game"
            stat = item["stat"]
            if stat == "games_played":
                rows = conn.execute(
                    f"SELECT game_date, opponent, 1 AS v FROM {table} WHERE player_id = %s AND season_id = %s ORDER BY game_date, game_id",
                    (item["player_id"], config.SEASON_ID)).fetchall()
            else:
                col = {"goals": "goals", "assists": "assists", "points": "points"}.get(stat)
                if item["kind"] == "goalie":
                    col = {"wins": "(decision = 'W')::int", "shutouts": "(goals_against = 0 AND toi_sec >= 3540)::int"}[stat]
                rows = conn.execute(
                    f"SELECT game_date, opponent, {col} AS v FROM {table} WHERE player_id = %s AND season_id = %s ORDER BY game_date, game_id",
                    (item["player_id"], config.SEASON_ID)).fetchall()
            running = item["before"]
            for g in rows:
                running += g["v"] or 0
                if running >= item["milestone"]:
                    item["date"], item["opponent"] = g["game_date"], g["opponent"]
                    break

    upcoming.sort(key=lambda m: (m["games_needed"], m["remaining"]))
    reached.sort(key=lambda m: str(m.get("date") or ""), reverse=True)
    return {"upcoming": upcoming, "reached": reached, "games_per_season": config.GAMES_PER_SEASON}


# --- Lines, pairings and linemates --------------------------------------------------------------
@app.get("/api/teams/{abbrev}/lines")
def team_lines(abbrev: str, limit: int = 12):
    """The team's most-used 5v5 forward lines and defense pairs this season."""
    abbrev = abbrev.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        names = {r["player_id"]: (r["name"], r["position"]) for r in conn.execute(
            "SELECT player_id, name, position FROM skater_season WHERE season_id = %s", (config.SEASON_ID,))}
        fwd = conn.execute(
            """SELECT p1, p2, p3, sum(toi_sec) AS toi, count(*) AS games, sum(cf) AS cf, sum(ca) AS ca,
                      sum(gf) AS gf, sum(ga) AS ga, sum(xgf)::float AS xgf, sum(xga)::float AS xga, count(xgf) = count(*) AS has_xg
               FROM line_game WHERE team = %s GROUP BY p1, p2, p3 ORDER BY sum(toi_sec) DESC LIMIT %s""",
            (abbrev, limit)).fetchall()
        pairs = conn.execute(
            """SELECT p1, p2, sum(toi_sec) AS toi, count(*) AS games, sum(cf) AS cf, sum(ca) AS ca,
                      sum(gf) AS gf, sum(ga) AS ga, sum(xgf)::float AS xgf, sum(xga)::float AS xga, count(xgf) = count(*) AS has_xg
               FROM pair_game WHERE team = %s GROUP BY p1, p2 ORDER BY sum(toi_sec) DESC""",
            (abbrev,)).fetchall()
    def player(pid):
        n = names.get(pid, (str(pid), None))
        return {"player_id": pid, "name": n[0], "position": n[1]}
    d_pairs = [p for p in pairs if names.get(p["p1"], (0, None))[1] == "D" and names.get(p["p2"], (0, None))[1] == "D"][:8]
    def shape(row, ids):
        total = row["cf"] + row["ca"]
        return {"players": [player(i) for i in ids], "toi_sec": row["toi"], "games": row["games"],
                "cf": row["cf"], "ca": row["ca"], "cf_pct": round(row["cf"] / total, 4) if total else None,
                "gf": row["gf"], "ga": row["ga"],
                "xgf": row["xgf"] if row["has_xg"] else None, "xga": row["xga"] if row["has_xg"] else None,
                "xg_pct": round(chemistry.share(row["xgf"], row["xga"]), 4) if row["has_xg"] and chemistry.share(row["xgf"], row["xga"]) is not None else None}
    return {
        "forwards": [shape(r, (r["p1"], r["p2"], r["p3"])) for r in fwd],
        "defense": [shape(r, (r["p1"], r["p2"])) for r in d_pairs],
    }


@app.get("/api/skaters/{player_id}/linemates")
def linemates(player_id: int, limit: int = 10):
    """Who this player spends 5v5 time with, and how each of them does together vs apart: shot-attempt share (Corsi) and, where
    stored, expected goals per 60 and share, with a chemistry verdict that accounts for how much data is behind it
    (chemistry.py). Rows are the most-used partners first. Only games with expected goals stored on the pair rows count, on both
    the together and the apart side, so the two compare like for like."""
    limit = max(1, min(limit, 30))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        names = {r["player_id"]: (r["name"], r["position"], r["team"]) for r in conn.execute(
            "SELECT player_id, name, position, team FROM skater_season WHERE season_id = %s", (config.SEASON_ID,))}
        totals = {r["player_id"]: r for r in conn.execute(
            """SELECT player_id, sum(cf) AS cf, sum(ca) AS ca, sum(toi_5v5_sec) AS toi, sum(xgf)::float AS xgf, sum(xga)::float AS xga
               FROM skater_game_onice WHERE season_id = %s
                 AND game_id IN (SELECT game_id FROM game_shift_status WHERE lines_version >= %s) GROUP BY player_id""",
            (config.SEASON_ID, chemistry.XG_LINES_VERSION))}
        rows = conn.execute(
            """SELECT CASE WHEN p1 = %(p)s THEN p2 ELSE p1 END AS partner,
                      sum(toi_sec) AS toi, count(*) AS games, sum(cf) AS cf, sum(ca) AS ca,
                      sum(gf) AS gf, sum(ga) AS ga, sum(xgf)::float AS xgf, sum(xga)::float AS xga,
                      count(xgf) = count(*) AS has_xg
               FROM pair_game WHERE (p1 = %(p)s OR p2 = %(p)s)
                 AND game_id IN (SELECT game_id FROM game_shift_status WHERE lines_version >= %(v)s)
               GROUP BY 1 ORDER BY sum(toi_sec) DESC LIMIT %(limit)s""",
            {"p": player_id, "limit": limit, "v": chemistry.XG_LINES_VERSION}).fetchall()
    me = totals.get(player_id)
    out = []
    for r in rows:
        together = {"toi": r["toi"], "cf": r["cf"], "ca": r["ca"],
                    "xgf": r["xgf"] if r["has_xg"] else None, "xga": r["xga"] if r["has_xg"] else None}
        view = chemistry.pair_view(together, me, totals.get(r["partner"]))
        n = names.get(r["partner"], (str(r["partner"]), None, None))
        out.append({
            "player_id": r["partner"], "name": n[0], "position": n[1], "team": n[2],
            "toi_sec": r["toi"], "games": r["games"], "gf": r["gf"], "ga": r["ga"],
            # the original Corsi columns, kept as they were
            "cf_pct_together": round(view["cf_share_together"], 4) if view["cf_share_together"] is not None else None,
            "cf_pct_player_apart": _apart_pct(me, r),
            "cf_pct_partner_apart": _apart_pct(totals.get(r["partner"]), r),
            **view,
        })
    best, worst = chemistry.best_and_worst(out)
    return {"toi_5v5_sec": me["toi"] if me else None, "linemates": out,
            "min_together_sec": chemistry.MIN_TOGETHER_SEC,
            "best": {"player_id": best["player_id"], "name": best["name"]} if best else None,
            "worst": {"player_id": worst["player_id"], "name": worst["name"]} if worst else None}


def _apart_pct(total, together):
    """Corsi share of a player's 5v5 time without this partner, or None when it can't be worked out."""
    if not total or total["cf"] is None or total["ca"] is None:
        return None
    cf, ca = total["cf"] - together["cf"], total["ca"] - together["ca"]
    return round(cf / (cf + ca), 4) if cf + ca > 0 else None


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


@app.get("/api/skaters/{player_id}/shots")
def skater_shots(player_id: int):
    """Every shot attempt by this skater this season (blocked shots included), and their xG summary."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = _shots(conn, "s.shooter_id = %(p)s", {"p": player_id})
        summary = conn.execute(
            """SELECT count(*) FILTER (WHERE kind <> 'block') AS unblocked,
                      count(*) FILTER (WHERE kind IN ('shot', 'goal')) AS on_goal,
                      count(*) FILTER (WHERE kind = 'goal') AS goals,
                      count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals,
                      coalesce(sum(xg), 0) AS ixg,
                      avg(distance) FILTER (WHERE kind <> 'block') AS avg_distance,
                      avg(xg) FILTER (WHERE xg IS NOT NULL) AS avg_xg
               FROM shot WHERE season_id = %s AND shooter_id = %s""",
            (config.SEASON_ID, player_id),
        ).fetchone()
        onice = conn.execute(
            "SELECT coalesce(sum(xgf), 0) AS xgf, coalesce(sum(xga), 0) AS xga FROM skater_game_onice WHERE season_id = %s AND player_id = %s",
            (config.SEASON_ID, player_id),
        ).fetchone()
    return {"shots": rows, "summary": summary, "onice": onice}


@app.get("/api/teams/{abbrev}/shots")
def team_shots(abbrev: str):
    """Shots the team took ('for') and allowed ('against'), with totals."""
    abbrev = abbrev.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        taken = _shots(conn, "s.team = %(t)s", {"t": abbrev}, limit=2500)
        allowed = _shots(conn, "s.opponent = %(t)s", {"t": abbrev}, limit=2500)
        totals = conn.execute(
            """SELECT sum(xg) FILTER (WHERE team = %(t)s) AS xgf, sum(xg) FILTER (WHERE opponent = %(t)s) AS xga,
                      count(*) FILTER (WHERE team = %(t)s AND kind = 'goal') AS gf,
                      count(*) FILTER (WHERE opponent = %(t)s AND kind = 'goal') AS ga
               FROM shot WHERE season_id = %(season)s AND (team = %(t)s OR opponent = %(t)s)""",
            {"t": abbrev, "season": config.SEASON_ID},
        ).fetchone()
    return {"for": taken, "against": allowed, "totals": totals}


@app.get("/api/goalies/{player_id}/shots")
def goalie_shots(player_id: int):
    """Shots this goalie faced, with goals saved above expected (xG faced minus goals allowed)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = _shots(conn, "s.goalie_id = %(p)s AND s.kind IN ('shot', 'goal')", {"p": player_id})
        summary = conn.execute(
            """SELECT count(*) AS faced, count(*) FILTER (WHERE kind = 'goal') AS goals,
                      count(*) FILTER (WHERE xg IS NOT NULL) AS modeled,
                      count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals,
                      coalesce(sum(xg), 0) AS xga
               FROM shot WHERE season_id = %s AND goalie_id = %s AND kind IN ('shot', 'goal')""",
            (config.SEASON_ID, player_id),
        ).fetchone()
        # An attempt's xG includes the chance of missing the net, so shots on goal alone need scaling up to the
        # league's goal total (see luck_db.GOALIE_CALIBRATION_CTE); each shot's own xG is left as the model made it.
        factor = luck_db.goalie_factor(conn, config.SEASON_ID)
        summary["xga"] = summary["xga"] * factor
    return {"shots": rows, "summary": summary, "xga_factor": factor}


# --- Luck and regression --------------------------------------------------------------------------
@app.get("/api/luck/skaters")
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
    limit = max(1, min(limit, 200))
    key = ("points_z" if rank == "points" else "z") + ("_adj" if vs == "own" else "")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = luck_db.skater_rows(conn, config.SEASON_ID, config.GAMES_PER_SEASON, position, min_attempts)
    out = [r for r in rows if r[key] is not None]
    out.sort(key=lambda x: (x[key], x["name"]), reverse=dir.lower() != "asc")
    return {"season": config.SEASON_ID, "games": config.GAMES_PER_SEASON, "min_attempts": min_attempts,
            "rank": rank, "vs": vs, "z_flag": luck.Z_FLAG, "rows": out[:limit]}


@app.get("/api/luck/goalies")
def luck_goalies(min_faced: int = luck.MIN_FACED, dir: str = "desc", limit: int = 50):
    """Goalies' goals saved above expected (xG faced minus goals allowed), with a z-score for the gap."""
    limit = max(1, min(limit, 200))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = luck_db.goalie_rows(conn, config.SEASON_ID, min_faced)
    out = [r for r in rows if r["z"] is not None]
    out.sort(key=lambda x: (x["z"], x["name"]), reverse=dir.lower() != "asc")
    return {"season": config.SEASON_ID, "min_faced": min_faced, "z_flag": luck.Z_FLAG, "rows": out[:limit]}


@app.get("/api/luck/history/{player_id}")
def luck_history(player_id: int):
    """A player's finishing (skater) or goals saved above expected (goalie) season by season, past seasons included."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        history = luck_db.skater_history(conn, player_id)
        kind = "skater"
        if not history["seasons"]:
            history, kind = luck_db.goalie_history(conn, player_id), "goalie"
    return {"kind": kind if history["seasons"] else None, **history}


@app.get("/api/luck/persistence")
def luck_persistence():
    """How well one season's luck figure predicts the next (see luck_db.persistence)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        result = luck_db.persistence(conn)
    return {"min_attempts": luck.MIN_PERSIST_ATTEMPTS, "min_faced": luck.MIN_PERSIST_FACED, **result}


@app.get("/api/luck/players")
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


PRIOR_MIN_GAMES = 20  # games in a past season before its rates count as a track record


# --- Fantasy value ----------------------------------------------------------------------------------
@app.get("/api/fantasy/games-left")
def fantasy_games_left():
    """Games each team has played and has left this season, from the stored schedule. The Fantasy page uses it to turn
    a player's per-game value into value over the rest of the season."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            """SELECT team, count(*) FILTER (WHERE state IN ('OFF', 'FINAL')) AS played,
                      count(*) FILTER (WHERE state NOT IN ('OFF', 'FINAL')) AS left
               FROM (SELECT home AS team, state FROM game WHERE season_id = %(s)s
                     UNION ALL SELECT away, state FROM game WHERE season_id = %(s)s) t
               GROUP BY team""", {"s": config.SEASON_ID}).fetchall()
    return {"season": config.SEASON_ID, "games_per_season": config.GAMES_PER_SEASON,
            "teams": {r["team"]: {"played": r["played"], "left": r["left"]} for r in rows}}


@app.get("/api/fantasy/priors")
def fantasy_priors():
    """Each skater's track record: goals and assists per game over the last two seasons, the more recent one counting
    double. The Fantasy page pulls a short early-season sample toward this (a backtest on four past seasons found
    that predicts the rest of the season far better than pulling toward the position average). A season counts
    only with PRIOR_MIN_GAMES games; players without one are left out."""
    seasons = [config.SEASON_ID - 10001, config.SEASON_ID - 20002]
    weights = {seasons[0]: 2.0, seasons[1]: 1.0}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            """SELECT player_id, season_id, games_played, goals, assists FROM career_season
               WHERE season_id = ANY(%s) AND games_played >= %s""", (seasons, PRIOR_MIN_GAMES)).fetchall()
    acc = {}
    for r in rows:
        w = weights[r["season_id"]]
        a = acc.setdefault(r["player_id"], {"w": 0.0, "goals": 0.0, "assists": 0.0, "games": 0})
        a["w"] += w
        a["goals"] += w * r["goals"] / r["games_played"]
        a["assists"] += w * r["assists"] / r["games_played"]
        a["games"] += r["games_played"]
    return {"season": config.SEASON_ID, "seasons": seasons, "min_games": PRIOR_MIN_GAMES,
            "players": {pid: {"goals": a["goals"] / a["w"], "assists": a["assists"] / a["w"], "games": a["games"]}
                        for pid, a in acc.items()}}


# --- Rest-of-season projections ----------------------------------------------------------------
@app.get("/api/projections")
def projections_endpoint(position: str = "", ids: str = "", min_games: int = 1, sort: str = "final_points", limit: int = 100):
    """Where each skater's points, goals and assists are headed by the end of the season, with an 80% range for the
    finish (see projections.py for the method and how well it did in a backtest). position is C, L, R, D or F
    (forwards); ids is a comma-separated list of player ids."""
    try:
        wanted = {int(x) for x in ids.split(",") if x.strip()}
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    if sort not in ("final_points", "final_goals", "final_assists", "rest_points"):
        raise HTTPException(400, "sort must be final_points, final_goals, final_assists or rest_points")
    limit = max(1, min(limit, 1000))
    games_left = fantasy_games_left()["teams"]
    priors = fantasy_priors()["players"]
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            """SELECT player_id, name, team, position, games_played, goals, assists, points
               FROM skater_season WHERE season_id = %s AND games_played > 0""", (config.SEASON_ID,)).fetchall()
        luck_rows = {r["player_id"]: r for r in luck_db.skater_rows(conn, config.SEASON_ID, config.GAMES_PER_SEASON)}
    factor = projections.league_factor(list(luck_rows.values()))
    averages = projections.role_averages(rows)
    out = []
    for r in rows:
        if r["games_played"] < min_games or (wanted and r["player_id"] not in wanted):
            continue
        if position == "F" and r["position"] == "D" or position in ("C", "L", "R", "D") and r["position"] != position:
            continue
        team = (r["team"] or "").split(",")[-1]
        t = games_left.get(team)
        luck_row = luck_rows.get(r["player_id"])
        proj = projections.project({**r, "ixg": luck_row["ixg"] if luck_row else None}, priors.get(r["player_id"]), averages,
                                   factor, t["left"] if t else None, t["played"] if t else None)
        out.append({"player_id": r["player_id"], "name": r["name"], "team": r["team"], "position": r["position"],
                    "games_played": r["games_played"], "goals": r["goals"], "assists": r["assists"], "points": r["points"],
                    "point_pace": r["points"] / r["games_played"] * config.GAMES_PER_SEASON, **proj})
    out.sort(key=lambda x: (-x[sort], x["name"]))
    return {"season": config.SEASON_ID, "games_per_season": config.GAMES_PER_SEASON, "total": len(out),
            "method": {"prior_games": projections.PRIOR_GAMES, "xg_weight": projections.XG_WEIGHT},
            "rows": out[:limit]}


@app.get("/api/projections/goalies")
def projections_goalies(ids: str = "", min_games: int = 1, sort: str = "final_wins", limit: int = 100):
    """Where each goalie's wins, saves, goals against and shutouts are headed by the end of the season: what he has now
    plus the expected starts left (the chance he starts each remaining game of his team) times what a start in each of
    those games is worth, from the two teams' ratings. See streaming.py and projections.goalie_final. No range is given:
    the start count is a guess from recent usage and says nothing about injuries or trades."""
    try:
        wanted = {int(x) for x in ids.split(",") if x.strip()}
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    if sort not in ("final_wins", "final_saves", "final_shutouts", "rest_starts", "final_starts"):
        raise HTTPException(400, "sort must be final_wins, final_saves, final_shutouts, rest_starts or final_starts")
    limit = max(1, min(limit, 1000))
    plan = _streaming_plan(GOALIE_PROJECTION_DAYS)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        now = {r["player_id"]: r for r in conn.execute(
            """SELECT player_id, name, team, games_played, games_started, wins, losses, ot_losses, saves, shots_against,
                      goals_against, shutouts FROM goalie_season WHERE season_id = %s""", (config.SEASON_ID,)).fetchall()}
    out = []
    for g in plan["goalies"]:
        r = now.get(g["player_id"])
        if not r or (r["games_played"] or 0) < min_games or (wanted and g["player_id"] not in wanted):
            continue
        out.append({"player_id": g["player_id"], "name": g["name"], "team": g["team"], **projections.goalie_final(r, g["games"])})
    out.sort(key=lambda x: (-x[sort], x["name"]))
    return {"season": config.SEASON_ID, "total": len(out), "rows": out[:limit]}


_accuracy_cache = {"sig": None, "data": None}


@app.get("/api/accuracy")
def accuracy_endpoint(request: Request):
    """Owner only. How well two of the site's predictions did this season, replayed game by game using only what was known
    beforehand: the on-paper win chance (against simple baselines) and the probable-goalie model, plus the forward log of
    predictions made before each game (predictions.py). See accuracy.py."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        auth.require_admin(conn, request)
        games = conn.execute(
            """SELECT game_id, game_date AS date, home, away, home_score, away_score FROM game
               WHERE season_id = %s AND state IN ('OFF', 'FINAL') AND home_score IS NOT NULL ORDER BY game_date, game_id""",
            (config.SEASON_ID,)).fetchall()
        sig = (len(games), games[-1]["game_id"] if games else None)
        if _accuracy_cache["sig"] == sig:
            return {**_accuracy_cache["data"], "live": predictions.load_report()}
        shots = {}
        for r in conn.execute(
                """SELECT game_id, t AS team, coalesce(sum(xg) FILTER (WHERE side = 'f'), 0)::float AS xgf,
                          coalesce(sum(xg) FILTER (WHERE side = 'a'), 0)::float AS xga
                   FROM (SELECT game_id, team AS t, xg, 'f' AS side FROM shot WHERE season_id = %(s)s
                         UNION ALL SELECT game_id, opponent, xg, 'a' FROM shot WHERE season_id = %(s)s) x
                   GROUP BY game_id, t""", {"s": config.SEASON_ID}):
            shots[(r["game_id"], r["team"])] = {"xgf": r["xgf"], "xga": r["xga"]}
        for r in conn.execute(
                """SELECT game_id, count(*) FILTER (WHERE kind = 'goal') AS goals,
                          count(*) FILTER (WHERE kind IN ('shot', 'goal')) AS sog
                   FROM shot WHERE season_id = %s GROUP BY game_id""", (config.SEASON_ID,)):
            shots[(r["game_id"], None)] = {"goals": r["goals"], "sog": r["sog"]}
        starters = {}
        for r in conn.execute(
                """SELECT game_id, game_date AS date, team, player_id FROM goalie_game
                   WHERE season_id = %s AND started ORDER BY toi_sec DESC NULLS LAST""", (config.SEASON_ID,)):
            starters.setdefault((r["game_id"], r["team"]), {"game_id": r["game_id"], "date": r["date"], "team": r["team"], "starter": r["player_id"]})
    data = {"season": config.SEASON_ID, "games_finished": len(games),
            "win": accuracy.win_report(accuracy.win_replay(games, shots)),
            "goalie": accuracy.goalie_report(accuracy.goalie_replay(list(starters.values())))}
    _accuracy_cache.update(sig=sig, data=data)
    return {**data, "live": predictions.load_report()}


# --- Matchup quality ------------------------------------------------------------------------------
@app.get("/api/matchups/teams")
def matchup_teams():
    """Every team's offense and defense rating (ratios to the league average, from expected goals) and the matchup
    ratios for skaters and goalies facing it, where above 1 is favorable to the player. See matchups.py."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        teams, league = matchups_db.team_table(conn, config.SEASON_ID)
    return {"season": config.SEASON_ID, "league": league, "label_at": matchups.LABEL_AT,
            "priors": {"team_games": matchups.TEAM_PRIOR_GAMES, "goalie_shots": matchups.GOALIE_PRIOR_SHOTS}, "teams": teams}


def _game_ratios(opp_row, own_kind, gaps, goals_pg):
    """One game's matchup fields for a team's players against opp_row (the opponent's team_table row): skater and goalie
    ratios with the rest adjustment applied (see matchups.py), their labels, and the team's rest situation."""
    if not opp_row:
        return {"skater_ratio": None, "goalie_ratio": None, "skater_label": None, "goalie_label": None, "rest": own_kind}
    skater = matchups.skater_game_ratio(opp_row["skater_ratio"], own_kind, gaps, goals_pg)
    goalie = matchups.goalie_game_ratio(opp_row["off_ratio"], own_kind, gaps, goals_pg)
    return {"skater_ratio": skater, "goalie_ratio": goalie, "skater_label": matchups.label(skater),
            "goalie_label": matchups.label(goalie), "rest": own_kind}


@app.get("/api/matchups/schedule")
def matchup_schedule(days: int = 7):
    """Each team's games in the next `days` days (today first, Eastern) with how favorable each is for skaters and for
    goalies, and the stretch's summary: games, average ratio and opportunity index (sum of ratio - 1)."""
    return _matchup_schedule(max(1, min(days, 21)))


REST_OF_SEASON_DAYS = 250


@app.get("/api/fantasy/schedule")
def fantasy_schedule():
    """Every team's remaining games this season with the matchup ratios of /api/matchups/schedule. The Fantasy page's playoff-week
    planner picks its weeks from this, so a skater's games are his team's games. Ratios use today's team ratings, so late-season
    games are only as good as the ratings are today."""
    return _matchup_schedule(REST_OF_SEASON_DAYS)


@app.get("/api/fantasy/goalie-schedule")
def fantasy_goalie_schedule(ids: str = ""):
    """The given goalies' chance to start each remaining game and what a start there is worth (as /api/streaming/goalies, but for the
    rest of the season and only for the goalies asked for, since the full plan is large). Starts far ahead are a guess from the
    team's recent split."""
    try:
        wanted = {int(i) for i in ids.split(",") if i.strip()}
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    plan = _streaming_plan(REST_OF_SEASON_DAYS)
    return {**plan, "goalies": [g for g in plan["goalies"] if g["player_id"] in wanted]}


def _matchup_schedule(days):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        teams, league = matchups_db.team_table(conn, config.SEASON_ID)
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        games = conn.execute(
            """SELECT game_id, game_date, start_time, home, away FROM game
               WHERE season_id = %s AND game_date >= %s AND game_date < %s AND state NOT IN ('OFF', 'FINAL')
               ORDER BY game_date, start_time, game_id""", (config.SEASON_ID, today, today + timedelta(days=days))).fetchall()
        gaps, kinds = _rest_context(conn)
    by_team = {t["team"]: t for t in teams}
    goals_pg = league.get("goals_pg") if league else None
    out = []
    for t in teams:
        mine = []
        for g in games:
            if t["team"] not in (g["home"], g["away"]):
                continue
            opp = g["away"] if g["home"] == t["team"] else g["home"]
            o = by_team.get(opp)
            mine.append({"game_id": g["game_id"], "date": g["game_date"], "opponent": opp, "home_game": g["home"] == t["team"],
                         **_game_ratios(o, kinds.get((t["team"], g["game_id"])), gaps, goals_pg)})
        out.append({"team": t["team"], "name": t["name"], "logo_url": t["logo_url"], "logo_dark_url": t["logo_dark_url"],
                    "games": mine,
                    "skaters": matchups.schedule_summary([g["skater_ratio"] for g in mine]),
                    "goalies": matchups.schedule_summary([g["goalie_ratio"] for g in mine])})
    return {"season": config.SEASON_ID, "from": today, "to": today + timedelta(days=days - 1), "days": days,
            "label_at": matchups.LABEL_AT, "teams": out}


# --- Special teams ----------------------------------------------------------------------------------
def _special_team_table(conn, last):
    """Every team's special-teams figures with league ranks (1 = best), plus PP% and PK% from the standings."""
    rows = specialteams_db.team_rows(conn, config.SEASON_ID, last)
    names = {r["abbrev"]: r for r in conn.execute(
        "SELECT abbrev, name, pp_pct, pk_pct, logo_url, logo_dark_url FROM team_season WHERE season_id = %s", (config.SEASON_ID,))}
    for r in rows:
        n = names.get(r["team"], {})
        r.update(name=n.get("name", r["team"]), pp_pct=n.get("pp_pct"), pk_pct=n.get("pk_pct"),
                 logo_url=n.get("logo_url"), logo_dark_url=n.get("logo_dark_url"))
    for key, high in (("pp_xgf60", True), ("pp_gf60", True), ("pp_pct", True), ("pp_toi_pg", True),
                      ("pk_xga60", False), ("pk_ga60", False), ("pk_pct", True), ("pk_toi_pg", False)):
        specialteams.rank_by(rows, key, high)
    rows.sort(key=lambda r: r["team"])
    return rows


@app.get("/api/special-teams")
def special_teams(last: int = 0):
    """Every team's power play and penalty kill: time per game, expected goals and goals per 60 minutes, and the NHL's
    PP% and PK%, each ranked. last limits it to each team's most recent N games (0 = the season so far). See specialteams.py."""
    last = max(0, min(last, 82))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = _special_team_table(conn, last)
    return {"season": config.SEASON_ID, "last": last, "teams": rows}


@app.get("/api/teams/{abbrev}/special-teams")
def team_special_teams(abbrev: str, last: int = 0):
    """One team's power-play and penalty-kill units (inferred from ice time, see specialteams.py) next to its special-teams
    figures and their league ranks."""
    abbrev = abbrev.upper()
    last = max(0, min(last, 82))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        table = _special_team_table(conn, last)
        line = next((r for r in table if r["team"] == abbrev), None)
        if not line:
            raise HTTPException(404, "No special-teams data for that team yet")
        players = specialteams_db.team_players(conn, config.SEASON_ID, abbrev, last)
    return {"season": config.SEASON_ID, "last": last, "team": line, "league_teams": len(table),
            "thresholds": {"pp1": specialteams.PP1_SHARE, "pp2": specialteams.PP2_SHARE, "pk1": specialteams.PK1_SHARE,
                           "pk2": specialteams.PK2_SHARE, "min_games": specialteams.MIN_GAMES},
            "power_play": specialteams.power_play_units(players), "penalty_kill": specialteams.penalty_kill_units(players)}


# --- Prospects ----------------------------------------------------------------------------------
PROSPECT_SORTS = {"points_per_game", "points", "goals", "assists", "games", "age", "draft", "name", "save_pct"}


def _prospect_row(p, line, today):
    """One prospect as the API returns them: bio, draft, and this season's line in the league they played most in."""
    pts = prospectlib.points_per_game(line)
    return {"player_id": p["player_id"], "name": p["name"], "team": p["team"], "position": p["position"], "shoots": p["shoots"],
            "age": prospectlib.age_on(p["birth_date"], today), "birth_country": p["birth_country"],
            "height_in": p["height_in"], "weight_lb": p["weight_lb"], "headshot": p["headshot"],
            "draft": {"year": p["draft_year"], "round": p["draft_round"], "pick": p["draft_pick"], "overall": p["draft_overall"],
                      "team": p["draft_team"]} if p["draft_year"] else None,
            "league": line["league"] if line else None, "club": line["team_name"] if line else None,
            "games": line["games"] if line else 0, "goals": line["goals"] if line else None,
            "assists": line["assists"] if line else None, "points": line["points"] if line else None,
            "points_per_game": pts, "wins": line["wins"] if line else None,
            "save_pct": line["save_pct"] if line else None, "gaa": line["gaa"] if line else None}


@app.get("/api/prospects")
def prospects_list(team: str = "", position: str = "", league: str = "", q: str = "", sort: str = "points_per_game",
                   min_games: int = 5, limit: int = 100):
    """Players on NHL teams' prospect lists with this season's line in the league they played most in (junior, college,
    European or minor league). position is C, L, R, D, F (forwards) or G; sort is one of PROSPECT_SORTS (age and draft
    run lowest first). See prospects.py."""
    if sort not in PROSPECT_SORTS:
        raise HTTPException(400, f"sort must be one of {', '.join(sorted(PROSPECT_SORTS))}")
    limit = max(1, min(limit, 1000))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        people = conn.execute("SELECT * FROM prospect WHERE on_list").fetchall()
        lines = defaultdict(list)
        for r in conn.execute("SELECT * FROM prospect_season WHERE season_id = %s AND game_type = 2", (config.SEASON_ID,)):
            lines[r["player_id"]].append({**r, "season_id": r["season_id"]})
    rows = [_prospect_row(p, prospectlib.current_line(lines.get(p["player_id"], []), config.SEASON_ID), today) for p in people]
    leagues = sorted({r["league"] for r in rows if r["league"]})
    team, league, needle = team.upper(), league.upper(), q.strip().lower()
    out = []
    for r in rows:
        if team and r["team"] != team or league and (r["league"] or "").upper() != league:
            continue
        if position == "F" and r["position"] == "G" or position in ("C", "L", "R", "D", "G") and r["position"] != position:
            continue
        if needle and needle not in r["name"].lower():
            continue
        if r["games"] < min_games and not needle:
            continue
        out.append(r)
    key = {"age": lambda r: (r["age"] is None, r["age"] or 0), "draft": lambda r: (r["draft"] is None, (r["draft"] or {}).get("overall") or 0),
           "name": lambda r: r["name"]}.get(sort, lambda r: (r[sort] is None, -(r[sort] or 0)))
    out.sort(key=lambda r: (key(r), r["name"]))
    return {"season": config.SEASON_ID, "total": len(out), "leagues": leagues, "rows": out[:limit]}


@app.get("/api/prospects/{player_id}")
def prospect_detail(player_id: int):
    """A prospect's bio, draft details and every season's line in every league they've played in."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        p = conn.execute("SELECT * FROM prospect WHERE player_id = %s", (player_id,)).fetchone()
        if not p:
            raise HTTPException(404, "No prospect with that id")
        seasons = conn.execute(
            """SELECT season_id, game_type, league, team_name, games, goals, assists, points, pim, plus_minus, wins, save_pct, gaa
               FROM prospect_season WHERE player_id = %s ORDER BY season_id DESC, game_type, games DESC""", (player_id,)).fetchall()
    line = prospectlib.current_line(seasons, config.SEASON_ID)
    return {**_prospect_row(p, line, today), "on_list": p["on_list"], "birth_date": p["birth_date"],
            "seasons": [{**s, "points_per_game": prospectlib.points_per_game(s)} for s in seasons]}


# The upcoming draft class: NHL Central Scouting's rankings. They carry no player ids, so there are no stats here.
DRAFT_CATEGORIES = {1: "North American skaters", 2: "International skaters", 3: "North American goalies", 4: "International goalies"}
_draft_cache = {}   # category -> (fetched at, response)
DRAFT_TTL = 6 * 3600


def _draft_rankings_raw(category, upcoming):
    """The NHL's rankings response for the upcoming draft if it has published them, else for the latest class it has."""
    r = requests.get(f"{config.WEB_API}/draft/rankings/{upcoming}/{category}", timeout=15)
    if r.status_code == 200:
        return r.json()
    latest = requests.get(f"{config.WEB_API}/draft/rankings/now", timeout=15).json()
    if category == 1:
        return latest
    return requests.get(f"{config.WEB_API}/draft/rankings/{latest['draftYear']}/{category}", timeout=15).json()


@app.get("/api/draft/rankings")
def draft_rankings(category: int = 1):
    """Central Scouting's rankings for the upcoming draft (category 1 NA skaters, 2 international skaters, 3 NA goalies,
    4 international goalies), cached for six hours. `already_drafted` is true when the NHL has not yet published rankings
    for the next draft and these are last June's class."""
    if category not in DRAFT_CATEGORIES:
        raise HTTPException(400, "category must be 1, 2, 3 or 4")
    hit = _draft_cache.get(category)
    today = datetime.now(timezone.utc).date()
    upcoming = today.year if today.month <= 6 else today.year + 1   # the draft is in June
    if not hit or time.time() - hit[0] > DRAFT_TTL:
        try:
            raw = _draft_rankings_raw(category, upcoming)
            rows = raw["rankings"]
        except (requests.RequestException, ValueError, KeyError):
            if hit:
                raw, rows = hit[1]
            else:
                raise HTTPException(502, "The NHL rankings are not available right now")
        else:
            _draft_cache[category] = (time.time(), (raw, rows))
            hit = _draft_cache[category]
    raw, rows = hit[1]
    out = []
    for r in rows:
        born = date.fromisoformat(r["birthDate"]) if r.get("birthDate") else None
        out.append({"rank": r.get("finalRank") or r.get("midtermRank"), "midterm_rank": r.get("midtermRank"),
                    "final_rank": r.get("finalRank"), "name": f"{r.get('firstName', '')} {r.get('lastName', '')}".strip(),
                    "position": r.get("positionCode"), "shoots": r.get("shootsCatches"),
                    "club": r.get("lastAmateurClub"), "league": r.get("lastAmateurLeague"),
                    "age": prospectlib.age_on(born, today), "height_in": r.get("heightInInches"), "weight_lb": r.get("weightInPounds"),
                    "birth_country": r.get("birthCountry")})
    out.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0, r["name"]))
    year = raw.get("draftYear")
    # the NHL keeps serving last June's class until it publishes the next one: say so rather than call it upcoming
    return {"draft_year": year, "upcoming_year": upcoming, "already_drafted": bool(year and year < upcoming),
            "category": category, "categories": DRAFT_CATEGORIES, "rows": out}


# --- What changed ------------------------------------------------------------------------------
@app.get("/api/skaters/{player_id}/explain")
def skater_explain(player_id: int):
    """The biggest things behind a skater's season so far: luck against real changes in shot volume, shot quality, ice time
    and role, priced in goals or points over a full season (see explain.py)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        out = explain_db.explanation(conn, player_id)
    if out is None:
        raise HTTPException(404, "No games this season for that skater")
    return out


# --- Role changes ---------------------------------------------------------------------------------
@app.get("/api/roles/changes")
def role_changes(window: int = 5, kind: str = "all", dir: str = "up", position: str = "", limit: int = 50):
    """Skaters whose power-play unit or even-strength ice time moved over their last `window` games compared with
    their earlier games this season (see roles.py). dir=up lists promotions and rising ice time, dir=down the
    opposite; kind=pp or ev narrows it to one of the two."""
    if kind not in ("all", "pp", "ev"):
        raise HTTPException(400, "kind must be all, pp or ev")
    if dir not in ("up", "down"):
        raise HTTPException(400, "dir must be up or down")
    window = max(2, min(window, 20))
    limit = max(1, min(limit, 200))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        lines = roles_db.player_lines(conn, config.SEASON_ID, window)
    rows = []
    for r in lines.values():
        if position == "F" and r["position"] == "D" or position in ("C", "L", "R", "D") and r["position"] != position:
            continue
        hit = {"all": (r["pp_change"], r["ev_change"]), "pp": (r["pp_change"],), "ev": (r["ev_change"],)}[kind]
        if dir in hit:
            rows.append(r)
    # Biggest move first. Together, a power-play move outweighs a change in even-strength time: the share moves by
    # tenths while the time moves by minutes, so the two are put on a similar scale (0.1 of share ~ 30 seconds).
    size = {"pp": lambda r: r["pp_share_delta"], "ev": lambda r: r["ev_delta"],
            "all": lambda r: r["pp_share_delta"] * 10 + r["ev_delta"] / 300}[kind]
    rows.sort(key=lambda r: (size(r), r["name"]), reverse=dir == "up")
    return {"season": config.SEASON_ID, "window": window, "kind": kind, "dir": dir, "rows": rows[:limit],
            "thresholds": {"pp1": roles.PP1_SHARE, "pp2": roles.PP2_SHARE, "ev_seconds": roles.EV_CHANGE_SEC,
                           "min_base_games": roles.MIN_BASE_GAMES}}


@app.get("/api/roles/players")
def role_players(ids: str = "", window: int = 5):
    """Role-change figures for specific skaters (comma-separated ids), keyed by player id. Skaters without enough
    games to compare are left out."""
    try:
        wanted = [int(x) for x in ids.split(",") if x.strip()][:100]
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    window = max(2, min(window, 20))
    if not wanted:
        return {"season": config.SEASON_ID, "window": window, "players": {}}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        lines = roles_db.player_lines(conn, config.SEASON_ID, window, ids=wanted)
    return {"season": config.SEASON_ID, "window": window, "players": lines}


# --- Games and schedules ------------------------------------------------------------------------
def _game_win_probability(game, goals, teams):
    """How the home team's chance of winning moved through a finished game, with a short written story (see winprob.py), or None when the
    goals we hold do not add up to the final score (so the timeline would be wrong)."""
    if game["state"] not in ("OFF", "FINAL") or game["home_score"] is None or game["away_score"] is None:
        return None
    timed = [(g["time_sec"], 1 if g["team"] == game["home"] else 0) for g in goals if g["period"] <= 4]
    shootout = game["last_period"] == "SO"
    home_goals, away_goals = sum(h for _, h in timed), sum(1 - h for _, h in timed)
    if (home_goals, away_goals) != (game["home_score"] - (shootout and game["home_score"] > game["away_score"]),
                                    game["away_score"] - (shootout and game["away_score"] > game["home_score"])):
        return None
    end_type = game["last_period"] if game["last_period"] in ("OT", "SO") else "REG"
    ended = winprob.REGULATION if end_type == "REG" else 3900 if end_type == "SO" else max(winprob.REGULATION + 1, timed[-1][0])
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        gap = winprob_db.gap_before(conn, game["season_id"], game["game_date"], game["home"], game["away"])
    home_won = game["home_score"] > game["away_score"]
    points, events = winprob.timeline(timed, gap, ended, home_won)
    xg = {"home": teams[game["home"]]["xg"], "away": teams[game["away"]]["xg"]} if teams[game["home"]]["attempts"] else None
    return {"pregame": winprob.win_prob(0, 0, gap), "gap": gap, "ended": ended, "end_type": end_type,
            "points": [[t, round(p, 4)] for t, p in points],
            "events": [{**e, "before": round(e["before"], 4), "after": round(e["after"], 4)} for e in events],
            "story": winprob.story(game["home"], game["away"], gap, events, game["home_score"], game["away_score"], end_type, points, xg)}


@app.get("/api/games/{game_id}")
def game_detail(game_id: int):
    """Box score for one game: result, goals, team shot totals, skater and goalie lines, shots."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        game = conn.execute("SELECT * FROM game WHERE game_id = %s", (game_id,)).fetchone()
        if game is None:
            raise HTTPException(404, "Game not found")
        skaters = conn.execute(
            """SELECT g.player_id, coalesce(s.name, g.player_id::text) AS name, s.position, g.team, g.goals, g.assists,
                      g.points, g.shots, g.plus_minus, g.pim, g.toi_sec, g.hits, g.blocked_shots, g.takeaways,
                      g.giveaways, o.cf, o.ca, o.xgf, o.xga, o.toi_5v5_sec
               FROM skater_game g
               LEFT JOIN skater_season s ON s.player_id = g.player_id AND s.season_id = g.season_id
               LEFT JOIN skater_game_onice o ON o.player_id = g.player_id AND o.game_id = g.game_id
               WHERE g.game_id = %s ORDER BY g.points DESC, g.goals DESC, g.toi_sec DESC""",
            (game_id,),
        ).fetchall()
        goalies = conn.execute(
            """SELECT g.player_id, coalesce(s.name, g.player_id::text) AS name, g.team, g.started, g.decision,
                      g.shots_against, g.saves, g.goals_against, g.toi_sec
               FROM goalie_game g LEFT JOIN goalie_season s ON s.player_id = g.player_id AND s.season_id = g.season_id
               WHERE g.game_id = %s ORDER BY g.started DESC NULLS LAST, g.toi_sec DESC""",
            (game_id,),
        ).fetchall()
        names, positions = {}, {}
        for r in conn.execute("SELECT player_id, name, position FROM skater_season WHERE season_id = %s", (game["season_id"],)):
            names[r["player_id"]], positions[r["player_id"]] = r["name"], r["position"]
        shots = conn.execute(
            """SELECT event_id, team, opponent, period, time_sec, kind, shot_type, x, y, distance, xg, strength,
                      rebound, shooter_id, goalie_id, situation, %s::date AS game_date
               FROM shot WHERE game_id = %s ORDER BY time_sec""",
            (game["game_date"], game_id),
        ).fetchall()
        lines = conn.execute(
            """SELECT team, p1, p2, p3, toi_sec, cf, ca, gf, ga FROM line_game WHERE game_id = %s
               ORDER BY team, toi_sec DESC""", (game_id,)).fetchall()
        pairs = conn.execute(
            """SELECT team, p1, p2, toi_sec, cf, ca, gf, ga FROM pair_game WHERE game_id = %s
               ORDER BY team, toi_sec DESC""", (game_id,)).fetchall()

    goals = [
        {"period": s["period"], "time_sec": s["time_sec"], "team": s["team"], "scorer": names.get(s["shooter_id"], "–"),
         "shooter_id": s["shooter_id"], "strength": s["strength"], "empty_net": s["empty_net"] if "empty_net" in s else None,
         "shot_type": s["shot_type"], "xg": s["xg"]}
        for s in shots if s["kind"] == "goal"
    ]
    teams = {}
    for side in (game["home"], game["away"]):
        mine = [s for s in shots if s["team"] == side]
        theirs = [s for s in shots if s["opponent"] == side]
        sk = [p for p in skaters if p["team"] == side]
        teams[side] = {
            "attempts": len(mine), "on_goal": sum(1 for s in mine if s["kind"] in ("shot", "goal")),
            "xg": round(sum(s["xg"] or 0 for s in mine), 2), "xg_against": round(sum(s["xg"] or 0 for s in theirs), 2),
            "hits": sum(p["hits"] or 0 for p in sk), "blocks": sum(p["blocked_shots"] or 0 for p in sk),
            "takeaways": sum(p["takeaways"] or 0 for p in sk), "giveaways": sum(p["giveaways"] or 0 for p in sk),
            "pim": sum(p["pim"] or 0 for p in sk),
        }
    return {"game": game, "teams": teams, "goals": goals, "win_probability": _game_win_probability(game, goals, teams), "skaters": skaters, "goalies": goalies,
            "shots": shots, "lines": [{**l, "names": [names.get(l[k], str(l[k])) for k in ("p1", "p2", "p3")]} for l in lines],
            # pair_game holds every two skaters who shared the ice; the defense pairings are the ones where both are defensemen
            "pairs": [{**p, "names": [names.get(p[k], str(p[k])) for k in ("p1", "p2")]} for p in pairs
                      if positions.get(p["p1"]) == "D" and positions.get(p["p2"]) == "D"]}


# Shift charts come straight from the NHL (we only store the on-ice totals derived from them) and are
# cached in memory: a finished game never changes, a live one is refreshed every half minute.
_shift_cache = {}
SHIFT_TTL_LIVE = 30
SHIFT_CACHE_MAX = 200


def _clock_seconds(period, mmss):
    minutes, seconds = mmss.split(":")
    return (period - 1) * 1200 + int(minutes) * 60 + int(seconds)


@app.get("/api/games/{game_id}/shifts")
def game_shifts(game_id: int):
    """Every skater's shifts in absolute game seconds, forwards then defensemen, busiest first."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        game = conn.execute("SELECT season_id, state FROM game WHERE game_id = %s", (game_id,)).fetchone()
        if game is None:
            raise HTTPException(404, "Game not found")
        positions = {r["player_id"]: r["position"] for r in conn.execute(
            "SELECT player_id, position FROM skater_season WHERE season_id = %s", (game["season_id"],))}
        goalie_ids = {r["player_id"] for r in conn.execute(
            "SELECT player_id FROM goalie_game WHERE game_id = %s", (game_id,))}
    final = game["state"] in ("OFF", "FINAL")
    hit = _shift_cache.get(game_id)
    if hit and (final or time.time() - hit[0] < SHIFT_TTL_LIVE):
        return hit[1]
    if game["state"] == "FUT":
        return {"players": [], "length_sec": 3600}
    try:
        rows = requests.get(f"{config.STATS_API}/shiftcharts", params={"limit": -1, "cayenneExp": f"gameId={game_id}"},
                            timeout=20).json()["data"]
    except (requests.RequestException, ValueError, KeyError):
        if hit:
            return hit[1]
        raise HTTPException(502, "NHL shift data unavailable")
    players = {}
    for s in rows:
        if s.get("typeCode") != 517 or not s.get("startTime") or not s.get("endTime") or s["period"] > 4:
            continue
        if s["playerId"] in goalie_ids:
            continue
        start, end = _clock_seconds(s["period"], s["startTime"]), _clock_seconds(s["period"], s["endTime"])
        if end < start:
            continue
        p = players.setdefault(s["playerId"], {
            "player_id": s["playerId"], "name": f"{s.get('firstName', '')} {s.get('lastName', '')}".strip(),
            "team": s["teamAbbrev"], "position": positions.get(s["playerId"]), "shifts": [], "toi_sec": 0})
        p["shifts"].append([start, end])
        p["toi_sec"] += end - start
    ordered = sorted(players.values(), key=lambda p: (p["team"], p["position"] == "D", -p["toi_sec"]))
    for p in ordered:
        p["shifts"].sort()
    length = max([e for p in ordered for _, e in p["shifts"]], default=3600)
    data = {"players": ordered, "length_sec": 3600 if length <= 3600 else math.ceil(length / 60) * 60}  # overtime runs short
    if len(_shift_cache) >= SHIFT_CACHE_MAX:
        _shift_cache.pop(next(iter(_shift_cache)))
    _shift_cache[game_id] = (time.time(), data)
    return data


@app.get("/api/teams/{abbrev}/schedule")
def team_schedule(abbrev: str):
    """Results so far (newest first) and the upcoming schedule for one team."""
    abbrev = abbrev.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            """SELECT game_id, game_date, start_time, home, away, home_score, away_score, last_period, state, venue
               FROM game WHERE season_id = %s AND (home = %s OR away = %s) ORDER BY game_date, game_id""",
            (config.SEASON_ID, abbrev, abbrev),
        ).fetchall()
    done = [r for r in rows if r["state"] in ("OFF", "FINAL")]
    todo = [r for r in rows if r["state"] not in ("OFF", "FINAL")]
    for r in done:
        us, them = (r["home_score"], r["away_score"]) if r["home"] == abbrev else (r["away_score"], r["home_score"])
        r["result"] = "W" if us > them else ("L" if r["last_period"] == "REG" else "OTL")
    return {"results": list(reversed(done))[:10], "upcoming": todo[:10]}


@app.get("/api/teams/{abbrev}/game-log")
def team_game_log(abbrev: str):
    """A team's finished games this season, oldest first, each with the score next to what the shots said (expected goals,
    attempts, power-play chances), plus the season summary, a rolling 5-game picture and the team's top scorers with their
    recent form. See teamlog.py."""
    abbrev = abbrev.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        info = conn.execute(
            """SELECT abbrev, name, common_name, logo_url, logo_dark_url, wins, losses, ot_losses, points, games_played
               FROM team_season WHERE season_id = %s AND abbrev = %s""", (config.SEASON_ID, abbrev)).fetchone()
        if not info:
            raise HTTPException(404, "Team not found")
        games = conn.execute(
            """SELECT game_id, game_date, home, away, home_score, away_score, last_period FROM game
               WHERE season_id = %s AND (home = %s OR away = %s) AND state IN ('OFF', 'FINAL')
               ORDER BY game_date, game_id""", (config.SEASON_ID, abbrev, abbrev)).fetchall()
        # this team's shot totals for and against in each game: one pass over the shots of games it played in
        totals = {r["game_id"]: r for r in conn.execute(
            """SELECT game_id,
                      coalesce(sum(xg) FILTER (WHERE team = %(t)s), 0)::float AS xgf,
                      coalesce(sum(xg) FILTER (WHERE opponent = %(t)s), 0)::float AS xga,
                      count(*) FILTER (WHERE team = %(t)s) AS cf, count(*) FILTER (WHERE opponent = %(t)s) AS ca,
                      count(*) FILTER (WHERE team = %(t)s AND kind IN ('shot', 'goal')) AS sf,
                      count(*) FILTER (WHERE opponent = %(t)s AND kind IN ('shot', 'goal')) AS sa,
                      coalesce(sum(xg) FILTER (WHERE team = %(t)s AND strength = 'pp'), 0)::float AS pp_xgf,
                      coalesce(sum(xg) FILTER (WHERE opponent = %(t)s AND strength = 'pp'), 0)::float AS pk_xga
               FROM shot WHERE season_id = %(s)s AND (team = %(t)s OR opponent = %(t)s) GROUP BY game_id""",
            {"t": abbrev, "s": config.SEASON_ID})}
        skaters = conn.execute(SKATERS_SQL, {
            "season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}).fetchall()
    rows = [teamlog.game_row(g, abbrev, totals.get(g["game_id"])) for g in games]
    mine = sorted((r for r in skaters if abbrev in (r["team"] or "").split(",") and r["games_played"]),
                  key=lambda r: (-r["points"], r["games_played"]))[:8]
    players = [{"player_id": r["player_id"], "name": r["name"], "position": r["position"], "games_played": r["games_played"],
                "points": r["points"], "point_pace": r["point_pace"], "recent_games": r["recent_games"],
                "recent_points": r["recent_points"], "recent_pace": r["recent_pace"], "form": teamlog.player_form(r)}
               for r in mine]
    return {"team": info, "games": rows, "summary": teamlog.summary(rows), "rolling": teamlog.rolling(rows),
            "window": teamlog.ROLL, "players": players}


# --- Pace history -------------------------------------------------------------------------------
def _cumulative(rows):
    """[(value per game, ...)] -> running totals by game number (1-based)."""
    total, out = 0, []
    for v in rows:
        total += v
        out.append(total)
    return out


@app.get("/api/skaters/{player_id}/pace-history")
def skater_pace_history(player_id: int, stat: str = "points"):
    """Cumulative points (or goals/assists) by game number: this season against past seasons."""
    if stat not in ("points", "goals", "assists"):
        raise HTTPException(400, "stat must be points, goals or assists")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        current = conn.execute(
            f"SELECT {stat} AS v FROM skater_game WHERE player_id = %s AND season_id = %s ORDER BY game_date, game_id",
            (player_id, config.SEASON_ID)).fetchall()
        past = conn.execute(
            f"SELECT season_id, {stat} AS v FROM skater_game_hist WHERE player_id = %s ORDER BY season_id DESC, game_date, game_id",
            (player_id,)).fetchall()
    seasons = [{"season_id": config.SEASON_ID, "current": True, "games": len(current), "totals": _cumulative(r["v"] for r in current)}]
    by_season = {}
    for r in past:
        by_season.setdefault(r["season_id"], []).append(r["v"])
    for sid, vals in sorted(by_season.items(), reverse=True):
        seasons.append({"season_id": sid, "current": False, "games": len(vals), "totals": _cumulative(vals)})
    return {"stat": stat, "games_per_season": config.GAMES_PER_SEASON, "seasons": seasons}


@app.get("/api/teams/{abbrev}/pace-history")
def team_pace_history(abbrev: str):
    """Cumulative standings points by team game number: this season against past seasons."""
    abbrev = abbrev.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        team = conn.execute("SELECT name FROM team_season WHERE season_id = %s AND abbrev = %s", (config.SEASON_ID, abbrev)).fetchone()
        if team is None:
            raise HTTPException(404, "Team not found")
        # Points for a finished game: 2 for a win, 1 for an overtime/shootout loss, 0 for a regulation loss.
        current = conn.execute(
            """SELECT CASE WHEN (home = %(t)s AND home_score > away_score) OR (away = %(t)s AND away_score > home_score) THEN 2
                           WHEN last_period = 'REG' THEN 0 ELSE 1 END AS v
               FROM game WHERE season_id = %(s)s AND (home = %(t)s OR away = %(t)s) AND state IN ('OFF', 'FINAL')
               ORDER BY game_date, game_id""", {"t": abbrev, "s": config.SEASON_ID}).fetchall()
        past = conn.execute(
            "SELECT season_id, points AS v FROM team_game_hist WHERE team_name = %s ORDER BY season_id DESC, game_date, game_id",
            (team["name"],)).fetchall()
    seasons = [{"season_id": config.SEASON_ID, "current": True, "games": len(current), "totals": _cumulative(r["v"] for r in current)}]
    by_season = {}
    for r in past:
        by_season.setdefault(r["season_id"], []).append(r["v"])
    for sid, vals in sorted(by_season.items(), reverse=True):
        seasons.append({"season_id": sid, "current": False, "games": len(vals), "totals": _cumulative(vals)})
    return {"stat": "points", "games_per_season": config.GAMES_PER_SEASON, "seasons": seasons}


@app.get("/api/records")
def records():
    """Single-season records and who is on pace to threaten them (scaled to this season's length)."""
    params = {"season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        recs = conn.execute("SELECT stat, rank, player_id, name, season_id, games, value FROM season_record ORDER BY stat, rank").fetchall()
        skaters = conn.execute(SKATERS_SQL, params).fetchall()
    min_gp = max(1, -(-max(r["games_played"] for r in skaters) // 2))
    out = {}
    for stat in ("points", "goals", "assists"):
        best = next(r for r in recs if r["stat"] == stat and r["rank"] == 1)
        paces = sorted(
            ({"player_id": r["player_id"], "name": r["name"], "team": r["team"], "games_played": r["games_played"],
              "value": r[stat], "pace": round(r[stat] / r["games_played"] * config.GAMES_PER_SEASON, 1)}
             for r in skaters if r["games_played"] >= min_gp),
            key=lambda p: -p["pace"])[:5]
        out[stat] = {"record": best, "top_ten": [r for r in recs if r["stat"] == stat], "on_pace": paces}
    return {"records": out, "min_gp": min_gp, "games_per_season": config.GAMES_PER_SEASON}

