"""Fantasy endpoints: the week ahead, form, games left, priors, schedules, projections, matchups and absences."""
from datetime import timedelta

from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row

import absences_db
import config
import luck_db
import matchups
import matchups_db
import projections
from routes.common import GOALIES_SQL, SKATERS_SQL, _goalie_params, _rest_context, _streaming_plan, ttl_cached

router = APIRouter()


GOALIE_PROJECTION_DAYS = 200   # longer than any season, so the window runs to the last game


# --- Fantasy roster support ---------------------------------------------------------------------
FANTASY_DAYS = 7


@router.get("/api/fantasy/week")
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


FORM_GAMES = 10


@router.get("/api/fantasy/form")
def fantasy_form(ids: str = ""):
    """For a roster: each player's last FORM_GAMES games this season, oldest first, for the sparklines on the Fantasy page.
    Skaters get points a game; goalies get the save percentage of each game they played (null when they faced no shots)."""
    try:
        wanted = [int(i) for i in ids.split(",") if i.strip()][:60]
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    if not wanted:
        return {"players": {}}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        skaters = conn.execute(
            """SELECT player_id, game_date, opponent, goals, assists, points FROM (
                   SELECT player_id, game_id, game_date, opponent, goals, assists, points,
                          row_number() OVER (PARTITION BY player_id ORDER BY game_date DESC, game_id DESC) AS n
                   FROM skater_game WHERE season_id = %s AND player_id = ANY(%s)) t
               WHERE n <= %s ORDER BY player_id, game_date, game_id""",
            (config.SEASON_ID, wanted, FORM_GAMES)).fetchall()
        goalies = conn.execute(
            """SELECT player_id, game_date, opponent, shots_against, saves, goals_against FROM (
                   SELECT player_id, game_id, game_date, opponent, shots_against, saves, goals_against,
                          row_number() OVER (PARTITION BY player_id ORDER BY game_date DESC, game_id DESC) AS n
                   FROM goalie_game WHERE season_id = %s AND player_id = ANY(%s) AND COALESCE(toi_sec, 0) > 0) t
               WHERE n <= %s ORDER BY player_id, game_date, game_id""",
            (config.SEASON_ID, wanted, FORM_GAMES)).fetchall()
    players = {}
    for r in skaters:
        players.setdefault(str(r["player_id"]), {"kind": "skater", "games": []})["games"].append({
            "date": r["game_date"], "opponent": r["opponent"], "goals": r["goals"], "assists": r["assists"], "points": r["points"]})
    for r in goalies:
        sa = r["shots_against"]
        players.setdefault(str(r["player_id"]), {"kind": "goalie", "games": []})["games"].append({
            "date": r["game_date"], "opponent": r["opponent"], "shots_against": sa, "goals_against": r["goals_against"],
            "save_pct": (r["saves"] / sa) if sa else None})
    return {"players": players}


_absence_cache = {"sig": None, "data": None}


@router.get("/api/absences")
def absences_endpoint():
    """Regulars who have missed their team's latest games (inferred from the box scores, since the NHL publishes no injury list) and what their
    teammates in the same position group are getting: the average extra ice time for a teammate in that spot, from four seasons of games, and
    what each has actually played in the games missed so far. See absences.py and its backtest."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        sig = tuple(conn.execute("SELECT count(*) AS n, max(game_date) AS d FROM skater_game_toi WHERE season_id = %s", (config.SEASON_ID,)).fetchone().values())
        if _absence_cache["sig"] != sig:
            _absence_cache.update(sig=sig, data={"season": config.SEASON_ID, "absences": absences_db.current(conn, config.SEASON_ID)})
    return _absence_cache["data"]


PRIOR_MIN_GAMES = 20  # games in a past season before its rates count as a track record


# --- Fantasy value ----------------------------------------------------------------------------------
def _games_left_by_team(conn):
    """{team: {played, left}} from the stored schedule."""
    rows = conn.execute(
        """SELECT team, count(*) FILTER (WHERE state IN ('OFF', 'FINAL')) AS played,
                  count(*) FILTER (WHERE state NOT IN ('OFF', 'FINAL')) AS left
           FROM (SELECT home AS team, state FROM game WHERE season_id = %(s)s
                 UNION ALL SELECT away, state FROM game WHERE season_id = %(s)s) t
           GROUP BY team""", {"s": config.SEASON_ID}).fetchall()
    return {r["team"]: {"played": r["played"], "left": r["left"]} for r in rows}


@router.get("/api/fantasy/games-left")
def fantasy_games_left():
    """Games each team has played and has left this season, from the stored schedule. The Fantasy page uses it to turn
    a player's per-game value into value over the rest of the season."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        teams = _games_left_by_team(conn)
    return {"season": config.SEASON_ID, "games_per_season": config.GAMES_PER_SEASON, "teams": teams}


@router.get("/api/fantasy/priors")
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
@router.get("/api/projections")
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


@router.get("/api/projections/goalies")
def projections_goalies(ids: str = "", min_games: int = 1, sort: str = "final_wins", limit: int = 100):
    """Where each goalie's wins, saves, goals against and shutouts are headed by the end of the season: what he has now
    plus the expected starts left (the chance he starts each remaining game of his team) times what a start in each of
    those games is worth, from the two teams' ratings. The starts come from the starter model blended with his share of his
    team's starts so far (projections.blend_starts), and the value of a start from what starters face (matchups_db.starter_rates);
    a backtest on four past seasons backs both (analysis/backtest_goalie_projection.py). See streaming.py and
    projections.goalie_final. The 80% ranges (low_/high_) come from a fit on the backtest and say nothing about injuries or trades;
    final_save_pct and final_gaa are the projected season figures."""
    try:
        wanted = {int(x) for x in ids.split(",") if x.strip()}
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    if sort not in ("final_wins", "final_saves", "final_shutouts", "rest_starts", "final_starts", "final_save_pct"):
        raise HTTPException(400, "sort must be final_wins, final_saves, final_shutouts, rest_starts, final_starts or final_save_pct")
    limit = max(1, min(limit, 1000))
    plan = _streaming_plan(GOALIE_PROJECTION_DAYS)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        now = {r["player_id"]: r for r in conn.execute(
            """SELECT player_id, name, team, games_played, games_started, wins, losses, ot_losses, saves, shots_against,
                      goals_against, shutouts, toi_sec FROM goalie_season WHERE season_id = %s""", (config.SEASON_ID,)).fetchall()}
        team_games = _games_left_by_team(conn)
        started = {(r["player_id"], r["team"]): r["starts"] for r in conn.execute(
            """SELECT player_id, team, count(*) AS starts FROM goalie_game WHERE season_id = %s AND started
               GROUP BY player_id, team""", (config.SEASON_ID,)).fetchall()}
    out = []
    for g in plan["goalies"]:
        r = now.get(g["player_id"])
        if not r or (r["games_played"] or 0) < min_games or (wanted and g["player_id"] not in wanted):
            continue
        tg = team_games.get(g["team"])
        chain = sum(x["probability"] or 0.0 for x in g["games"])
        games = g["games"]
        if tg and chain > 0:
            blended = projections.blend_starts(chain, tg["left"], started.get((g["player_id"], g["team"]), 0), tg["played"])
            games = projections.scale_starts(games, blended / chain)
        out.append({"player_id": g["player_id"], "name": g["name"], "team": g["team"], **projections.goalie_final(r, games)})
    out.sort(key=lambda x: (-(x[sort] or 0), x["name"]))
    return {"season": config.SEASON_ID, "total": len(out), "rows": out[:limit]}


# --- Matchup quality ------------------------------------------------------------------------------
@router.get("/api/matchups/teams")
@ttl_cached(60)
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


@router.get("/api/matchups/schedule")
def matchup_schedule(days: int = 7):
    """Each team's games in the next `days` days (today first, Eastern) with how favorable each is for skaters and for
    goalies, and the stretch's summary: games, average ratio and opportunity index (sum of ratio - 1)."""
    return _matchup_schedule(max(1, min(days, 21)))


REST_OF_SEASON_DAYS = 250


@router.get("/api/fantasy/schedule")
def fantasy_schedule():
    """Every team's remaining games this season with the matchup ratios of /api/matchups/schedule. The Fantasy page's playoff-week
    planner picks its weeks from this, so a skater's games are his team's games. Ratios use today's team ratings, so late-season
    games are only as good as the ratings are today."""
    return _matchup_schedule(REST_OF_SEASON_DAYS)


@router.get("/api/fantasy/goalie-schedule")
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
