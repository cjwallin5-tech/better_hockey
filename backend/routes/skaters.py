"""Skater endpoints: the leaderboard, a skater's page data, shots, zones, linemates, score effects and pace."""
import json
import math
from pathlib import Path
import statistics

from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row

import chemistry
import config
import explain_db
import scorestate
import scorestate_db
import scouting
import shootermap
from routes.common import SKATERS_SQL, _context, _cumulative, _shots, _stored_season, _timed_seasons, ttl_cached

router = APIRouter()


@router.get("/api/meta")
def meta():
    with psycopg.connect(config.DATABASE_URL) as conn:
        updated = conn.execute("SELECT max(updated_at) FROM skater_season WHERE season_id = %s", (config.SEASON_ID,)).fetchone()[0]
    return {
        "updated_at": updated,
        "season_id": config.SEASON_ID,
        "games_per_season": config.GAMES_PER_SEASON,
        "recent_window": config.RECENT_WINDOW,
    }


@router.get("/api/seasons")
def seasons():
    """Seasons the Skaters and Goalies leaderboards can show, newest first (the current season is the default)."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        def ids(table):
            return [r[0] for r in conn.execute(f"SELECT DISTINCT season_id FROM {table} ORDER BY season_id DESC")]
        return {"current": config.SEASON_ID, "skaters": ids("skater_season"), "goalies": ids("goalie_season")}


@router.get("/api/skaters")
@ttl_cached(60)
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


@router.get("/api/skaters/{player_id}")
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


@router.get("/api/skaters/{player_id}/similar")
def similar(player_id: int):
    params = {"season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        everyone = conn.execute(SKATERS_SQL, params).fetchall()
    player = next((r for r in everyone if r["player_id"] == player_id), None)
    if player is None:
        raise HTTPException(404, "Player not found")
    return _similar_players(everyone, player)


@router.get("/api/skaters/{player_id}/scouting")
def scouting_card(player_id: int):
    """Percentile card: the skater against same-role peers on nine measures of how they play (see scouting.py)."""
    params = {"season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        everyone = conn.execute(SKATERS_SQL, params).fetchall()
        speeds = {r["player_id"]: r["top_speed_mph"] for r in conn.execute(
            "SELECT player_id, top_speed_mph FROM edge_skater_season WHERE season_id = %s AND has_data",
            (config.SEASON_ID,)).fetchall()}
    for r in everyone:
        r["top_speed_mph"] = speeds.get(r["player_id"])
    player = next((r for r in everyone if r["player_id"] == player_id), None)
    if player is None:
        raise HTTPException(404, "Player not found")
    return {"player_id": player_id, "name": player["name"], "team": player["team"], "position": player["position"],
            "games_played": player["games_played"], **scouting.card(everyone, player)}


@router.get("/api/skaters/{player_id}/context")
def skater_context(player_id: int):
    return _context(player_id, goalie=False)


@router.get("/api/skaters/{player_id}/linemates")
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


@router.get("/api/skaters/{player_id}/shots")
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


_shooter_profile = {"sig": None, "data": None}


SHOOTER_SHOT_SQL = """
    SELECT season_id, shooter_id, kind, xg, distance, angle, y, shot_type, rebound, strength, empty_net
    FROM shot_hist WHERE x IS NOT NULL AND kind IN ('shot', 'miss', 'goal') AND shooter_id IS NOT NULL
    UNION ALL
    SELECT season_id, shooter_id, kind, xg, distance, angle, y, shot_type, rebound, strength, empty_net
    FROM shot WHERE x IS NOT NULL AND kind IN ('shot', 'miss', 'goal') AND shooter_id IS NOT NULL
      AND season_id NOT IN (SELECT season_id FROM shot_hist_game)
"""


@router.get("/api/skaters/{player_id}/zones")
def skater_zones(player_id: int, span: str = "all", strength: str = "all"):
    """Where this skater shoots from and where he scores above or below what the chances predict, in nine ice zones, by
    shot type and by situation (see shootermap.py). span=all pools every season with stored shot locations; span=current
    is this season only. strength=all, ev or pp filters his attempts (the league profile is always every strength)."""
    if span not in ("all", "current") or strength not in ("all", "ev", "pp"):
        raise HTTPException(400, "span must be all or current, strength all, ev or pp")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        player = conn.execute("SELECT name FROM skater_season WHERE player_id = %s ORDER BY season_id DESC LIMIT 1",
                              (player_id,)).fetchone()
        if player is None:
            raise HTTPException(404, "Player not found")
        sig = (span, conn.execute("SELECT count(*) AS n FROM shot_hist_game WHERE located").fetchone()["n"],
               conn.execute("SELECT count(*) AS n FROM shot WHERE season_id = %s", (config.SEASON_ID,)).fetchone()["n"])
        only = "WHERE season_id = %(cur)s" if span == "current" else ""
        if _shooter_profile["sig"] != sig:
            league = conn.execute(f"SELECT * FROM ({SHOOTER_SHOT_SQL}) t {only}", {"cur": config.SEASON_ID}).fetchall()
            factors = shootermap.season_factors(league)
            for r in league:
                r["f"] = factors.get(r["season_id"], 1.0)
            cal, shares = shootermap.league_profile(league)
            _shooter_profile.update(sig=sig, data=(factors, cal, shares))
        factors, cal, shares = _shooter_profile["data"]
        extra = "" if strength == "all" else f" AND strength = '{strength}'"
        mine = conn.execute(f"SELECT * FROM ({SHOOTER_SHOT_SQL}) t {only} {'AND' if only else 'WHERE'} shooter_id = %(p)s{extra}",
                            {"p": player_id, "cur": config.SEASON_ID}).fetchall()
    for r in mine:
        r["f"] = factors.get(r["season_id"], 1.0)
    out = shootermap.summarize(mine, cal, shares)
    return {"player_id": player_id, "name": player["name"], "span": span, "strength": strength,
            "headline": shootermap.headline(out), "min_zone_attempts": shootermap.MIN_ZONE_ATTEMPTS,
            "flag_z": shootermap.FLAG_Z, **out}


@router.get("/api/skaters/{player_id}/score-state")
def skater_score_state(player_id: int, span: str = "all"):
    """A skater's finishing by score state and in close-and-late situations against the rest of his shots."""
    if span not in ("all", "current"):
        raise HTTPException(400, "span must be all or current")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        seasons = _timed_seasons(conn)
        if span == "current":
            seasons = [config.SEASON_ID]
        player = conn.execute("SELECT name FROM skater_season WHERE player_id = %s ORDER BY season_id DESC LIMIT 1",
                              (player_id,)).fetchone()
        if player is None:
            raise HTTPException(404, "Player not found")
        rows = scorestate_db.player_shots(conn, player_id, seasons)
    for r in rows:
        r["state"] = scorestate.state_of(r["diff"])
    out = scorestate.clutch(rows)
    out["states"] = scorestate.by_state([{**r, "strength": r["strength"]} for r in rows])
    seasons_with = sorted({r["season_id"] for r in rows})
    return {"player_id": player_id, "name": player["name"], "span": span, "seasons": seasons_with, **out,
            "backtest": _clutch_backtest()}


def _clutch_backtest():
    """The saved check of whether close-and-late finishing repeats between seasons (analysis/backtest_clutch.py)."""
    path = Path(__file__).parent / "data" / "clutch_backtest.json"
    return json.loads(path.read_text()) if path.exists() else None


# --- What changed ------------------------------------------------------------------------------
@router.get("/api/skaters/{player_id}/explain")
def skater_explain(player_id: int):
    """The biggest things behind a skater's season so far: luck against real changes in shot volume, shot quality, ice time
    and role, priced in goals or points over a full season (see explain.py)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        out = explain_db.explanation(conn, player_id)
    if out is None:
        raise HTTPException(404, "No games this season for that skater")
    return out


@router.get("/api/skaters/{player_id}/pace-history")
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
