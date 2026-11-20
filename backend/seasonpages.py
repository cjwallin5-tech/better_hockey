"""Past-season pages: a season's final standings, playoff results and league leaders.

Standings and playoff series come from the NHL web API (`standings/{date}` on the day the regular season ended, and
`playoff-bracket/{year}`); the leaders come from our own season tables. Past seasons never change, so the API payloads are
read once and kept. These functions only reshape payloads; fetching lives in api.py."""


def end_date(seasons_payload, season):
    """The last day of a season's standings from the `standings-season` list, or None for a season the NHL doesn't list."""
    for s in seasons_payload.get("seasons", []):
        if s.get("id") == season:
            return s.get("standingsEnd")
    return None


def _name(value):
    return (value or {}).get("default") if isinstance(value, dict) else value


def standings_row(r):
    """One team's final line. Rank fields are 0 in eras without that grouping (no divisions before 1967, say), so they become None."""
    seq = lambda key: r.get(key) or None
    return {
        "abbrev": _name(r.get("teamAbbrev")), "name": _name(r.get("teamName")), "gp": r.get("gamesPlayed"),
        "wins": r.get("wins"), "losses": r.get("losses"), "otl": r.get("otLosses"), "ties": r.get("ties"), "points": r.get("points"),
        "gf": r.get("goalFor"), "ga": r.get("goalAgainst"), "diff": r.get("goalDifferential"),
        "conference": r.get("conferenceName"), "division": r.get("divisionName"),
        "conference_rank": seq("conferenceSequence"), "division_rank": seq("divisionSequence"), "league_rank": seq("leagueSequence"),
        "wildcard_rank": seq("wildcardSequence"),
    }


def standings(payload):
    """Final standings, best first (by the NHL's league rank, else by points). Empty when the payload has no teams."""
    rows = [standings_row(r) for r in payload.get("standings", [])]
    rows.sort(key=lambda r: (r["league_rank"] is None, r["league_rank"] or 0, -(r["points"] or 0), r["name"] or ""))
    return rows


def _seed(series, side, teams):
    team = series.get(f"{side}SeedTeam") or {}
    wins = series.get(f"{side}SeedWins")
    code = team.get("abbrev")
    if code is None and series.get(f"{side}SeedTeamId") in teams:
        code = teams[series[f"{side}SeedTeamId"]]
    return {"abbrev": code, "name": _name(team.get("name")), "wins": wins, "rank": series.get(f"{side}SeedRankAbbrev")}


def playoffs(payload):
    """The playoff rounds in order, each a list of series: {title, top, bottom, winner} (a seed is {abbrev, name, wins, rank}; winner is
    the winning team's abbreviation). `champion` is the name of the winner of the last round's single series, None when there is no bracket (a lost season)."""
    series = payload.get("series") or []
    rounds = {}
    for s in series:
        top, bottom = _seed(s, "top", {}), _seed(s, "bottom", {})
        won = s.get("winningTeamId")
        winner = None
        if won is not None:
            winner = top["abbrev"] if (s.get("topSeedTeam") or {}).get("id") == won else bottom["abbrev"]
        rounds.setdefault(s.get("playoffRound") or 0, []).append(
            {"title": s.get("seriesTitle"), "letter": s.get("seriesLetter"), "top": top, "bottom": bottom, "winner": winner})
    ordered = [{"round": n, "title": rs[0]["title"], "series": sorted(rs, key=lambda x: x["letter"] or "")} for n, rs in sorted(rounds.items())]
    champion = None
    if ordered and len(ordered[-1]["series"]) == 1:
        final = ordered[-1]["series"][0]
        if final["winner"]:
            champion = final["top"]["name"] if final["winner"] == final["top"]["abbrev"] else final["bottom"]["name"]
    return {"rounds": ordered, "champion": champion}


LEADERS = 10
MIN_GOALIE_GAMES = 20   # a goalie needs this many games to lead in save percentage or goals-against average


def leaders(conn, season):
    """The top ten in a season, from our own tables: {skaters: {goals, assists, points}, goalies: {wins, save_pct, gaa, shutouts} or None}.
    Skater lines go back to 1917-18; goalie lines start in 2005-06. Players are listed with the team(s) they played for that season."""
    skaters = {}
    for stat in ("goals", "assists", "points"):
        skaters[stat] = conn.execute(
            f"""SELECT c.player_id, s.name, c.team, c.games_played AS gp, c.{stat} AS value
                  FROM career_season c JOIN career_skater s ON s.player_id = c.player_id AND s.game_type = 2
                 WHERE c.season_id = %s AND c.{stat} > 0
                 ORDER BY c.{stat} DESC, c.games_played, s.name LIMIT {LEADERS}""", (season,)).fetchall()
    goalies = None
    if conn.execute("SELECT 1 FROM goalie_season WHERE season_id = %s LIMIT 1", (season,)).fetchone():
        goalies = {}
        for stat, order, where in (("wins", "DESC", "wins > 0"), ("shutouts", "DESC", "shutouts > 0"),
                                   ("save_pct", "DESC", f"games_played >= {MIN_GOALIE_GAMES} AND save_pct IS NOT NULL"),
                                   ("gaa", "ASC", f"games_played >= {MIN_GOALIE_GAMES} AND gaa IS NOT NULL")):
            goalies[stat] = conn.execute(
                f"""SELECT player_id, name, team, games_played AS gp, {stat} AS value FROM goalie_season
                     WHERE season_id = %s AND {where} ORDER BY {stat} {order}, games_played DESC, name LIMIT {LEADERS}""", (season,)).fetchall()
    return {"skaters": skaters, "goalies": goalies, "min_goalie_games": MIN_GOALIE_GAMES}
