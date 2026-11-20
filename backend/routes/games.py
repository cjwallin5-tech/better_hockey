"""Game-day endpoints: tonight, live, a game's detail and shifts, rest, probable goalies, streaming and schedule strength."""
from datetime import datetime
import math
import time

from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row
import requests

import config
import matchupfit
import matchupfit_db
import matchups_db
import probable_goalies
import tonight
import winprob
import winprob_db
from routes.common import _confirmed_starters, _goalie_plans, _goalie_zone_summary, _rest_context, _rest_gaps_cache, _streaming_plan, _zone_sig, ttl_cached
from routes.league import playoff_odds_endpoint

router = APIRouter()


@router.get("/api/probable-goalies/week")
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


@router.get("/api/streaming/goalies")
@ttl_cached(60)
def streaming_goalies(days: int = 7):
    """Every goalie with a chance to start in the next `days` days: for each game his chance to start and what a start
    there is expected to be worth (win, loss and overtime-loss chances, saves, goals against, shutout chance), from the
    two teams' ratings. The Fantasy page turns these into points or category value under your league. See streaming.py."""
    return _streaming_plan(max(1, min(days, 14)))


# --- Schedule grid ------------------------------------------------------------------------------


@router.get("/api/probable-goalies")
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


def _shot_fits(conn, starters_games):
    """{game_id: {home_shooting, away_shooting}}: for each side, how its shot zones line up with the opposing probable goalie's weak and
    strong zones (see matchupfit.py). Sides without a goalie or enough shots are left out."""
    current, prior, games = matchupfit_db.team_diets(conn, config.SEASON_ID)
    league = matchupfit_db.league_shares(current)
    rates = {}
    sig = _zone_sig(conn, "all")  # once for every goalie

    def goalie_rates(pid):
        if pid not in rates:
            goalie, summary = _goalie_zone_summary(conn, pid, "all", sig)
            ok = goalie is not None and summary["total"]["shots"] >= matchupfit.MIN_FACED
            rates[pid] = (goalie, *matchupfit.goalie_rates(summary)) if ok else None
        return rates[pid]

    out = {}
    for g in starters_games:
        entry = {}
        for shooting, defending in (("home", "away"), ("away", "home")):
            team, goalie = g[shooting], (g.get(f"{defending}_goalies") or {}).get("candidates") or []
            top = goalie[0] if goalie else None
            if not top or sum(current.get(team, {}).values()) + sum(prior.get(team, {}).values()) < matchupfit.MIN_TEAM_SHOTS:
                continue
            info = goalie_rates(top["player_id"])
            if not info:
                continue
            who, zone_rates, overall = info
            shares, _ = matchupfit.diet(current.get(team, {}), prior.get(team, {}))
            n_games = games.get(team, 0)
            per_game = sum(current.get(team, {}).values()) / n_games if n_games >= 5 else matchupfit.LEAGUE_SHOTS_PER_GAME
            entry[f"{shooting}_shooting"] = {
                "team": team, "goalie": {"player_id": top["player_id"], "name": top["name"], "catches": who["catches"],
                                         "probability": top["probability"], "confirmed": (g[f"{defending}_goalies"] or {}).get("confirmed")},
                **matchupfit.fit(shares, per_game, zone_rates, overall, who["catches"], league)}
        if entry:
            out[g["game_id"]] = entry
    return out


@router.get("/api/tonight")
@ttl_cached(60)
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
            "SELECT game_id, start_time, state, home, away, home_score, away_score FROM game WHERE season_id = %s AND game_date = %s "
            "ORDER BY start_time, game_id", (config.SEASON_ID, day)).fetchall()
        ratings, league = matchups_db.team_table(conn, config.SEASON_ID)
        skaters = conn.execute(
            "SELECT player_id, name, team, games_played, points FROM skater_season WHERE season_id = %s AND games_played > 0",
            (config.SEASON_ID,)).fetchall()
        goalies = conn.execute(
            "SELECT player_id, name, team FROM goalie_season WHERE season_id = %s AND player_id = ANY(%s)",
            (config.SEASON_ID, wanted)).fetchall() if wanted else []
        _, kinds = _rest_context(conn)
        win_gaps = _rest_gaps_cache["win"]
    by_team = {t["team"]: t for t in ratings}
    try:
        odds = {t["abbrev"]: t["make_playoffs"] for t in playoff_odds_endpoint()["teams"]}
    except HTTPException:
        odds = {}
    try:
        starters = {g["game_id"]: g for g in probable_goalies_endpoint(str(day))["games"]}
    except HTTPException:
        starters = {}
    try:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as fit_conn:
            shot_fits = _shot_fits(fit_conn, list(starters.values()))
    except psycopg.Error:
        shot_fits = {}

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
        home_kind = kinds.get((g["home"], g["game_id"]))
        win, total = tonight.matchup(h, a, league, home_kind, win_gaps)
        plain_win = tonight.matchup(h, a, league)[0] if home_kind in ("tired", "edge") else win
        top = sorted((stars.get(g["home"], [])[:1] + stars.get(g["away"], [])[:1]), key=lambda s: -s["ppg"])
        yours = yours_by_team.get(g["home"], []) + yours_by_team.get(g["away"], [])
        starter = starters.get(g["game_id"])
        graded = tonight.score_game(win, total, 2 * league["goals_pg"] if league else None,
                                    [odds.get(g["home"]), odds.get(g["away"])], top[0] if top else None,
                                    [y["name"] for y in yours], sorted(followed & {g["home"], g["away"]}))
        out.append({
            "game_id": g["game_id"], "start_time": g["start_time"], "state": g["state"], "home": g["home"], "away": g["away"],
            "home_score": g["home_score"], "away_score": g["away_score"],
            "home_info": {k: h[k] for k in ("name", "logo_url", "logo_dark_url")} if h else None,
            "away_info": {k: a[k] for k in ("name", "logo_url", "logo_dark_url")} if a else None,
            "home_win": win, "rest_win_shift": None if win is None else win - plain_win, "expected_goals": total,
            "odds": {"home": odds.get(g["home"]), "away": odds.get(g["away"])},
            "stars": {"home": stars.get(g["home"], [])[:2], "away": stars.get(g["away"], [])[:2]},
            "goalies": {"home": goalie(starter["home_goalies"]), "away": goalie(starter["away_goalies"])} if starter else None,
            "shot_fit": shot_fits.get(g["game_id"]),
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


@router.get("/api/live")
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


@router.get("/api/games/{game_id}")
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


def _fix_mojibake(text):
    """The NHL's shift feed double-encodes some names ("BjÃ¶rck" for "Björck"); undo that when it is plainly the case, else leave the text alone."""
    if not any(c in text for c in "ÃÂ"):
        return text
    for encoding in ("latin-1", "cp1252"):
        try:
            return text.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text


@router.get("/api/games/{game_id}/shifts")
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
            "player_id": s["playerId"], "name": _fix_mojibake(f"{s.get('firstName', '')} {s.get('lastName', '')}".strip()),
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
