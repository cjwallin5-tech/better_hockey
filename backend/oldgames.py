"""Games from before the seasons we store game by game, so head-to-head can reach back to 2005-06 (the first
shootout season, which is also when every game started producing a winner).

Team results come from each club's season schedule (/club-schedule-season/{team}/{season}); a skater's or goalie's
games against each team from their season game log (/player/{id}/game-log/{season}/2). Both are plain NHL web API
calls, so this module only parses what they return and keeps the franchise-code mapping in one place; the fetching and
storing happen in ingest.py (the schedules, in bulk) and api.py (a player's game logs, the first time someone asks).
"""
FIRST_SEASON = 20052006

# A franchise's current code for the code it used in earlier seasons (the Thrashers became the Jets, the Coyotes became Utah).
CURRENT_CODE = {"ATL": "WPG", "PHX": "UTA", "ARI": "UTA"}


def current_code(code):
    """The franchise's code today for a code that may be from an earlier season."""
    return CURRENT_CODE.get(code, code)


def code_in_season(team, season_id):
    """The code the NHL used for a (current-code) franchise in a season, to ask for its schedule."""
    if team == "WPG" and season_id < 20112012:
        return "ATL"
    if team == "UTA":
        if season_id < 20142015:
            return "PHX"
        if season_id < 20242025:
            return "ARI"
    return team


def parse_schedule(data):
    """Finished regular-season games from a club-schedule-season response, one dict per game with codes normalised to
    today's franchises: game_id, season_id, game_date, home, away, home_score, away_score, last_period."""
    out = []
    for g in data.get("games") or []:
        if g.get("gameType") != 2 or g.get("gameState") not in ("OFF", "FINAL"):
            continue
        home, away = g.get("homeTeam") or {}, g.get("awayTeam") or {}
        if home.get("score") is None or away.get("score") is None:
            continue
        out.append({
            "game_id": g["id"], "season_id": g["season"], "game_date": g["gameDate"],
            "home": current_code(home["abbrev"]), "away": current_code(away["abbrev"]),
            "home_score": home["score"], "away_score": away["score"],
            "last_period": (g.get("gameOutcome") or {}).get("lastPeriodType") or "REG",
        })
    return out


def _seconds(toi):
    """'26:16' -> 1576."""
    try:
        m, s = toi.split(":")
        return int(m) * 60 + int(s)
    except (AttributeError, ValueError):
        return 0


def parse_game_log(data, season_id, goalie):
    """A player's regular-season games from a game-log response, one dict per game with the opponent's current code.
    Skaters carry goals and assists; goalies carry shots_against, goals_against and whether they started."""
    out = []
    for g in data.get("gameLog") or []:
        row = {"game_id": g["gameId"], "season_id": season_id, "game_date": g["gameDate"],
               "opponent": current_code(g["opponentAbbrev"]), "toi_sec": _seconds(g.get("toi"))}
        if goalie:
            if row["toi_sec"] <= 0:
                continue
            row.update(shots_against=g.get("shotsAgainst") or 0, goals_against=g.get("goalsAgainst") or 0,
                       goals=0, assists=0)
        else:
            row.update(goals=g.get("goals") or 0, assists=g.get("assists") or 0, shots_against=0, goals_against=0)
        out.append(row)
    return out


def nhl_seasons(landing, before):
    """The regular seasons (FIRST_SEASON or later, and before `before`) a player has NHL games in, from a landing response."""
    seen = {s["season"] for s in landing.get("seasonTotals") or []
            if s.get("leagueAbbrev") == "NHL" and s.get("gameTypeId") == 2 and FIRST_SEASON <= s["season"] < before}
    return sorted(seen)
