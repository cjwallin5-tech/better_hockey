"""Team endpoints: the table, a team's page data, lines, shots, special teams, schedule, calendar, game log, history, pace."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response
import psycopg
from psycopg.rows import dict_row

import chemistry
import config
import franchise
import matchups_db
import previews
import special_shots
import specialteams
import specialteams_db
import srs
import teamcalendar
import teamlog
import tonight
from routes.common import GOALIES_SQL, RECORDS_API, SKATERS_SQL, TEAMS_SQL, _cumulative, _goalie_params, _records_rows, _rest_context, _rest_gaps_cache, _shots, ttl_cached

router = APIRouter()


@router.get("/api/teams")
def teams():
    """Every team's season line, with its Simple Rating System rating and strength of schedule so far (see srs.py)."""
    params = {"season": config.SEASON_ID, "games": config.GAMES_PER_SEASON}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(TEAMS_SQL, params).fetchall()
        games = conn.execute("SELECT home, away, home_score, away_score FROM game WHERE season_id = %s AND state IN ('OFF', 'FINAL')",
                             (config.SEASON_ID,)).fetchall()
    rated = srs.ratings([(g["home"], g["away"], g["home_score"], g["away_score"]) for g in games])
    return [{**r, "srs": round(rated[r["abbrev"]]["srs"], 2) if r["abbrev"] in rated else None,
             "sos": round(rated[r["abbrev"]]["sos"], 2) if r["abbrev"] in rated else None} for r in rows]


@router.get("/api/teams/{abbrev}")
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


# --- Lines, pairings and linemates --------------------------------------------------------------
@router.get("/api/teams/{abbrev}/lines")
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


@router.get("/api/teams/{abbrev}/shots")
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


@router.get("/api/special-teams")
def special_teams(last: int = 0):
    """Every team's power play and penalty kill: time per game, expected goals and goals per 60 minutes, and the NHL's
    PP% and PK%, each ranked. last limits it to each team's most recent N games (0 = the season so far). See specialteams.py."""
    last = max(0, min(last, 82))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = _special_team_table(conn, last)
    return {"season": config.SEASON_ID, "last": last, "teams": rows}


@router.get("/api/teams/{abbrev}/special-teams")
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


@router.get("/api/teams/{abbrev}/schedule")
@ttl_cached(60)
def team_schedule(abbrev: str):
    """Results so far (newest first) and the upcoming schedule for one team. Each upcoming game carries the team's win chance (the same
    on-paper model as the Games page, with home ice and rest) and the team's rest situation: tired, edge, both, normal (see fatigue.py)."""
    abbrev = abbrev.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            """SELECT game_id, game_date, start_time, home, away, home_score, away_score, last_period, state, venue
               FROM game WHERE season_id = %s AND (home = %s OR away = %s) ORDER BY game_date, game_id""",
            (config.SEASON_ID, abbrev, abbrev),
        ).fetchall()
        ratings, league = matchups_db.team_table(conn, config.SEASON_ID)
        _, kinds = _rest_context(conn)
        win_gaps = _rest_gaps_cache["win"]
    done = [r for r in rows if r["state"] in ("OFF", "FINAL")]
    todo = [r for r in rows if r["state"] not in ("OFF", "FINAL")]
    by_team = {t["team"]: t for t in ratings}
    for r in todo[:10]:
        home_win, _ = tonight.matchup(by_team.get(r["home"]), by_team.get(r["away"]), league, kinds.get((r["home"], r["game_id"])), win_gaps)
        r["win"] = None if home_win is None else (home_win if r["home"] == abbrev else 1 - home_win)
        r["rest"] = kinds.get((abbrev, r["game_id"]))
    for r in done:
        us, them = (r["home_score"], r["away_score"]) if r["home"] == abbrev else (r["away_score"], r["home_score"])
        r["result"] = "W" if us > them else ("L" if r["last_period"] == "REG" else "OTL")
    return {"results": list(reversed(done))[:10], "upcoming": todo[:10]}


@router.get("/api/teams/{abbrev}/calendar")
@ttl_cached(60)
def team_calendar(abbrev: str):
    """A team's whole season, every game in date order: opponent, home or away, the result or start time, and back-to-backs (see teamcalendar.py)."""
    abbrev = abbrev.upper()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        info = conn.execute("SELECT abbrev, name FROM team_season WHERE season_id = %s AND abbrev = %s", (config.SEASON_ID, abbrev)).fetchone()
        if not info:
            raise HTTPException(404, "Team not found")
        games = conn.execute(
            """SELECT game_id, game_date, start_time, home, away, home_score, away_score, last_period, state, venue
               FROM game WHERE season_id = %s AND (home = %s OR away = %s) ORDER BY game_date, game_id""",
            (config.SEASON_ID, abbrev, abbrev)).fetchall()
    return {"team": info, "season_id": config.SEASON_ID, **teamcalendar.build(games, abbrev)}


@router.get("/api/teams/{abbrev}/calendar.ics")
def team_calendar_ics(abbrev: str):
    """The same season as an iCalendar file, to add to a phone or desktop calendar (results are included for games already played)."""
    cal = team_calendar(abbrev)
    label = previews.season_label(cal["season_id"])
    body = teamcalendar.to_ics(cal["team"]["abbrev"], cal["team"]["name"], label, cal["games"], datetime.now(timezone.utc))
    return Response(content=body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{cal["team"]["abbrev"]}-{label}.ics"'})


@router.get("/api/teams/{abbrev}/game-log")
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


@router.get("/api/teams/{abbrev}/history")
def team_history(abbrev: str):
    """A franchise's all-time record, Cups, playoff appearances and a line per season, from the NHL records site (see franchise.py)."""
    abbrev = abbrev.upper()
    found = next((f for f in _records_rows(f"{RECORDS_API}/franchise") if f.get("teamAbbrev") == abbrev), None)
    if found is None:
        raise HTTPException(404, "Team not found")
    mine = lambda rows: [r for r in rows if r["franchiseId"] == found["id"]]
    totals = mine(_records_rows(f"{RECORDS_API}/franchise-totals"))
    appearances = next(iter(mine(_records_rows(f"{RECORDS_API}/franchise-playoff-appearances"))), None)
    seasons = _records_rows(f"{RECORDS_API}/franchise-season-results", cayenneExp=f"franchiseId={found['id']}", limit=-1)
    try:   # captains and retired numbers are extras: the page still works without them
        detail = next((r for r in _records_rows(f"{RECORDS_API}/franchise-detail") if r.get("id") == found["id"]), None)
    except HTTPException:
        detail = None
    return franchise.history(found, totals, appearances, seasons, config.SEASON_ID, detail)


@router.get("/api/teams/{abbrev}/special-shots")
def team_special_shots(abbrev: str):
    """A team's shootout record and shooters, its goalies' shootout saves, and its penalty shots for and against this season."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        return special_shots.team_view(conn, config.SEASON_ID, abbrev.upper())


@router.get("/api/teams/{abbrev}/pace-history")
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
