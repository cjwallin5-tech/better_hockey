"""Player-page endpoints that work for skaters and goalies: career, finishes, defense, tracking, comparables, rankings, profile."""

from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row

import config
import defense
import finishes
import internationals
import trajectory
from routes.common import ALLTIME_TABLES, _career_payload, ttl_cached

router = APIRouter()


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


@router.get("/api/players/{player_id}/career")
def career(player_id: int):
    """Career totals and season-by-season history, cached in Postgres for CAREER_TTL, with each regular season's hits, blocks, takeaways and
    giveaways (`tracked`, since 2005-06) from our own stored season totals."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        raw = _career_payload(conn, player_id)
        tracked = conn.execute(
            "SELECT season_id, hits, blocked_shots, takeaways, giveaways FROM defense_season WHERE player_id = %s", (player_id,)).fetchall()
        # The NHL lists a nationality separate from the birthplace (Cutter Gauthier was born in Sweden and is American). Our stored
        # bio tables have it; the flag shows it, and the birthplace stays in the bio line.
        nat = conn.execute(
            """SELECT birth_country FROM career_skater WHERE player_id = %(p)s AND game_type = 2
               UNION ALL SELECT birth_country FROM career_goalie WHERE player_id = %(p)s AND game_type = 2 LIMIT 1""", {"p": player_id}).fetchone()
    if raw is None:
        raise HTTPException(503, "The NHL API is busy right now; try again in a minute.")
    view = _career_view(raw)
    view["bio"]["nationality"] = (nat and nat["birth_country"]) or view["bio"]["birth_country"]
    # Hits, blocks, takeaways and giveaways per regular season (the NHL's player record has none), keyed by season id. A season's counts are
    # for the whole season, so a player traded mid-season has the same figures against each of that season's team rows.
    view["tracked"] = {str(r["season_id"]): {"hits": r["hits"], "blocks": r["blocked_shots"], "takeaways": r["takeaways"],
                                            "giveaways": r["giveaways"]} for r in tracked}
    return view


@router.get("/api/players/{player_id}/finishes")
def player_finishes(player_id: int):
    """Where a player ranked among all NHL skaters in goals, assists and points in each finished season: the seasons they led the league and how
    often they were in the top 5 and top 10 (see finishes.py)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            """SELECT m.season_id, m.goals, m.assists, m.points, r.goals_rank, r.assists_rank, r.points_rank
               FROM career_season m
               CROSS JOIN LATERAL (
                   SELECT 1 + count(*) FILTER (WHERE c.goals > m.goals) AS goals_rank,
                          1 + count(*) FILTER (WHERE c.assists > m.assists) AS assists_rank,
                          1 + count(*) FILTER (WHERE c.points > m.points) AS points_rank
                   FROM career_season c WHERE c.season_id = m.season_id) r
               WHERE m.player_id = %s AND m.season_id <> %s""", (player_id, config.SEASON_ID)).fetchall()
    return {"stats": finishes.summarize(rows)}


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


@router.get("/api/players/{player_id}/defense")
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


@router.get("/api/players/{player_id}/tracking")
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


@router.get("/api/players/{player_id}/comparables")
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


@router.get("/api/players/{player_id}/international")
@ttl_cached(60)
def player_international(player_id: int):
    """A player's national-team tournaments (Olympics, World Championship, World Cup / Canada Cup, 4 Nations, World Juniors), newest first,
    with the medal his team won, worked out from his NHL tournament rows and data/international_results.json (see internationals.py)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        payload = _career_payload(conn, player_id)
    apps = internationals.appearances(internationals.rows_from_landing(payload))
    cups = internationals.stanley_cups(internationals.awards_from_landing(payload))
    name = " ".join(((payload or {}).get(k) or {}).get("default", "") for k in ("firstName", "lastName"))
    official = internationals.official_club().get(internationals.name_key(name))
    return {"appearances": apps, "medals": internationals.medal_counts(apps), "tournaments": internationals.by_tournament(apps),
            "stanley_cups": cups, "triple_gold": internationals.triple_gold(apps, cups, official),
            "honors": internationals.honors(name, (payload or {}).get("birthCountry"), apps)}


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
            floor = " AND games_played >= %s" if min_gp else ""
            counts = conn.execute(
                f"SELECT count(*) FILTER (WHERE {stat} {op} %s) AS better, count(*) FILTER (WHERE {stat} = %s) AS same "
                f"FROM {table} WHERE game_type = %s AND {stat} IS NOT NULL" + floor,
                (value, value, game_type, min_gp) if min_gp else (value, value, game_type),
            ).fetchone()
            better, same = counts["better"], counts["same"]
            of = conn.execute(
                f"SELECT count(*) AS n FROM {table} WHERE game_type = %s AND {stat} IS NOT NULL" + floor,
                (game_type, min_gp) if min_gp else (game_type,),
            ).fetchone()["n"]
            # Players with the same value share a rank, and `tied` says this is one of them (the player counts in `same`).
            group[stat] = {"value": value, "rank": better + 1, "of": of, "tied": same > 1}
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
        out[stat] = {"value": me[stat], "rank": better + 1, "of": len(pool), "tied": sum(1 for v in pool if v == me[stat]) > 1}
    return out, floor


@router.get("/api/players/{player_id}/rankings")
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


@router.get("/api/players/{player_id}/profile")
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
