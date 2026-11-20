"""Trophy and award endpoints: award odds, trophy races, the trophy index and each trophy's winners."""
import math

from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row

import awards
import config
import trophies as trophy_lib
from routes.common import GOALIES_SQL, RECORDS_API, SKATERS_SQL, _goalie_params, _records_rows, ttl_cached
from routes.fantasy import projections_endpoint, projections_goalies
from routes.league import playoff_odds_endpoint

router = APIRouter()


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
                    "trophy": trophy, "rank": better + 1, "of": len(pool), "tied": sum(1 for o in pool if o[stat] == r[stat]) > 1,
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


@router.get("/api/award-odds")
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


@router.get("/api/trophy-races")
@ttl_cached(60)
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
                "player_id": pid, "name": r["name"], "team": r["team"], "rank": e["rank"], "tied": e["tied"],
                "value": e["value"], "games_played": r["games_played"],
            })
    for race in races.values():
        race["contenders"].sort(key=lambda c: (c["rank"], c["name"]))
    return {"size": CONTENTION_SIZE, "races": list(races.values())}


def _team_codes():
    """{team id: abbreviation} for every franchise past and present. Empty if the stats API won't answer, which only costs the
    team column (the winners themselves don't depend on it)."""
    try:
        return {t["id"]: t["triCode"] for t in _records_rows(f"{config.STATS_API}/team")}
    except HTTPException:
        return {}


@router.get("/api/trophy-index")
def trophy_index():
    """Every NHL trophy with the key that matches it to the award names on player pages."""
    rows = _records_rows(f"{RECORDS_API}/trophy")
    return {"trophies": [{"id": t["id"], "name": t["name"], "key": trophy_lib.key(t["name"])} for t in rows]}


@router.get("/api/trophy-summary")
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


@router.get("/api/trophy/{trophy_id}")
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


@router.get("/api/trophies")
@ttl_cached(60)
def trophies():
    """Who is in contention for each stat-driven trophy this season, keyed by player id."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        sk = conn.execute(SKATERS_SQL, {"season": config.SEASON_ID, "window": config.RECENT_WINDOW,
                                        "games": config.GAMES_PER_SEASON}).fetchall()
        gl = conn.execute(GOALIES_SQL, _goalie_params()).fetchall()
    return {"size": CONTENTION_SIZE, "players": {str(k): v for k, v in _contenders(sk, gl).items()}}
