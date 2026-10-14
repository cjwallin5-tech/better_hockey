"""Read-only JSON API over the ingested stats. Run: uvicorn api:app --reload"""
from datetime import datetime, timedelta, timezone

import math
import statistics
import time

import psycopg
import requests
from fastapi import FastAPI, HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import auth
import config

app = FastAPI(title="Hockey Stats")
app.include_router(auth.router)


@app.on_event("startup")
def _init_accounts():
    auth.init_db()

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
       date_part('year', age(current_date, s.birth_date))::int AS age,
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


@app.get("/api/skaters")
def skaters():
    params = {
        "season": config.SEASON_ID,
        "window": config.RECENT_WINDOW,
        "games": config.GAMES_PER_SEASON,
    }
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
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
def goalies():
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        return {
            "recent_window": config.RECENT_GOALIE_GAMES,
            "goalies": conn.execute(GOALIES_SQL, _goalie_params()).fetchall(),
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


# --- Live scores --------------------------------------------------------------------------------
# The nightly ingest only knows finished games, so in-progress games come straight from the NHL's
# scoreboard, cached briefly so many visitors don't each hit the NHL API.
LIVE_TTL = 20  # seconds
_live_cache = {"at": 0.0, "data": None}


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
    by_team = {}
    for g in games:
        by_team.setdefault(g["home"], []).append({**g, "opponent": g["away"], "home_game": True})
        by_team.setdefault(g["away"], []).append({**g, "opponent": g["home"], "home_game": False})
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
               "takeaways", "giveaways", "missed_shots", "shot_attempts", "empty_net_goals", "first_goals"},
    "goalie": {"name", "first_season", "games_played", "games_started", "wins", "losses", "ot_losses",
               "ties", "saves", "shots_against", "goals_against", "save_pct", "gaa", "shutouts", "toi_sec"},
}


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
                      sum(gf) AS gf, sum(ga) AS ga
               FROM line_game WHERE team = %s GROUP BY p1, p2, p3 ORDER BY sum(toi_sec) DESC LIMIT %s""",
            (abbrev, limit)).fetchall()
        pairs = conn.execute(
            """SELECT p1, p2, sum(toi_sec) AS toi, count(*) AS games, sum(cf) AS cf, sum(ca) AS ca,
                      sum(gf) AS gf, sum(ga) AS ga
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
                "gf": row["gf"], "ga": row["ga"]}
    return {
        "forwards": [shape(r, (r["p1"], r["p2"], r["p3"])) for r in fwd],
        "defense": [shape(r, (r["p1"], r["p2"])) for r in d_pairs],
    }


@app.get("/api/skaters/{player_id}/linemates")
def linemates(player_id: int, limit: int = 10):
    """Who this player spends 5v5 time with, and how each of them does together vs apart."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        names = {r["player_id"]: (r["name"], r["position"], r["team"]) for r in conn.execute(
            "SELECT player_id, name, position, team FROM skater_season WHERE season_id = %s", (config.SEASON_ID,))}
        totals = {r["player_id"]: r for r in conn.execute(
            """SELECT player_id, sum(cf) AS cf, sum(ca) AS ca, sum(toi_5v5_sec) AS toi
               FROM skater_game_onice WHERE season_id = %s GROUP BY player_id""", (config.SEASON_ID,))}
        rows = conn.execute(
            """SELECT CASE WHEN p1 = %(p)s THEN p2 ELSE p1 END AS partner,
                      sum(toi_sec) AS toi, count(*) AS games, sum(cf) AS cf, sum(ca) AS ca,
                      sum(gf) AS gf, sum(ga) AS ga
               FROM pair_game WHERE p1 = %(p)s OR p2 = %(p)s
               GROUP BY 1 ORDER BY sum(toi_sec) DESC LIMIT %(limit)s""",
            {"p": player_id, "limit": limit}).fetchall()
    me = totals.get(player_id)
    out = []
    for r in rows:
        partner = totals.get(r["partner"])
        together = r["cf"] + r["ca"]
        def apart_pct(t):
            if not t:
                return None
            cf, ca = t["cf"] - r["cf"], t["ca"] - r["ca"]
            return round(cf / (cf + ca), 4) if cf + ca > 0 else None
        n = names.get(r["partner"], (str(r["partner"]), None, None))
        out.append({
            "player_id": r["partner"], "name": n[0], "position": n[1], "team": n[2],
            "toi_sec": r["toi"], "games": r["games"],
            "cf_pct_together": round(r["cf"] / together, 4) if together else None,
            "cf_pct_player_apart": apart_pct(me), "cf_pct_partner_apart": apart_pct(partner),
            "gf": r["gf"], "ga": r["ga"],
        })
    return {"toi_5v5_sec": me["toi"] if me else None, "linemates": out}


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
    return {"shots": rows, "summary": summary}


# --- Games and schedules ------------------------------------------------------------------------
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
        names = {r["player_id"]: r["name"] for r in conn.execute(
            "SELECT player_id, name FROM skater_season WHERE season_id = %s", (game["season_id"],))}
        shots = conn.execute(
            """SELECT event_id, team, opponent, period, time_sec, kind, shot_type, x, y, distance, xg, strength,
                      rebound, shooter_id, goalie_id, %s::date AS game_date
               FROM shot WHERE game_id = %s ORDER BY time_sec""",
            (game["game_date"], game_id),
        ).fetchall()
        lines = conn.execute(
            """SELECT team, p1, p2, p3, toi_sec, cf, ca, gf, ga FROM line_game WHERE game_id = %s
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
    return {"game": game, "teams": teams, "goals": goals, "skaters": skaters, "goalies": goalies,
            "shots": shots, "lines": [{**l, "names": [names.get(l[k], str(l[k])) for k in ("p1", "p2", "p3")]} for l in lines]}


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
