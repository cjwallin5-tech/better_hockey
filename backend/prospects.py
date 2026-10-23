"""Prospects: players on NHL teams' prospect lists who haven't made the NHL yet, with their junior, college, European
and minor-league stats.

Everything comes from two NHL web endpoints: /prospects/{team} (the list, with bio) and /player/{id}/landing (draft
details and a season-by-season line for every league they've played in). Draft-class rankings (/draft/rankings) carry
no player ids, so the upcoming class is shown as a ranking only (see api.py), without stats.

A prospect's stat line this season is their regular-season row in the league where they played the most games, since
a prospect on loan or called up can have several. Leagues aren't comparable (a point a game in the OHL is not a point a
game in the AHL), so nothing here converts between them.
"""

POSITIONS = {"L", "R", "C", "D", "G"}


def _name(d):
    """The English text of a {'default': ...} name field, or a plain string."""
    if isinstance(d, dict):
        return d.get("default")
    return d


def parse_list(data):
    """Prospect bios from a /prospects/{team} response, one dict per player."""
    out = []
    for key in ("forwards", "defensemen", "goalies"):
        for p in data.get(key) or []:
            out.append({
                "player_id": p["id"], "name": f"{_name(p.get('firstName'))} {_name(p.get('lastName'))}".strip(),
                "position": p.get("positionCode"), "shoots": p.get("shootsCatches"), "birth_date": p.get("birthDate"),
                "birth_country": p.get("birthCountry"), "height_in": p.get("heightInInches"),
                "weight_lb": p.get("weightInPounds"), "headshot": p.get("headshot"),
            })
    return out


def parse_landing(data):
    """(draft, seasons) from a /player/{id}/landing response. draft is {year, round, pick, overall, team} or None;
    seasons are the regular-season and playoff rows (game types 2 and 3) of every league."""
    d = data.get("draftDetails")
    draft = {"year": d.get("year"), "round": d.get("round"), "pick": d.get("pickInRound"),
             "overall": d.get("overallPick"), "team": d.get("teamAbbrev")} if d else None
    seasons = []
    for s in data.get("seasonTotals") or []:
        if s.get("gameTypeId") not in (2, 3):
            continue
        seasons.append({
            "season_id": s["season"], "game_type": s["gameTypeId"], "league": s.get("leagueAbbrev"),
            "team_name": _name(s.get("teamName")) or "", "games": s.get("gamesPlayed") or 0,
            "goals": s.get("goals"), "assists": s.get("assists"), "points": s.get("points"),
            "pim": s.get("pim"), "plus_minus": s.get("plusMinus"),
            "wins": s.get("wins"), "save_pct": s.get("savePctg"), "gaa": s.get("goalsAgainstAvg"),
        })
    return draft, seasons


def current_line(seasons, season_id):
    """The prospect's regular-season row for `season_id` in the league where they played the most, or None."""
    rows = [s for s in seasons if s["season_id"] == season_id and s["game_type"] == 2]
    return max(rows, key=lambda s: s["games"]) if rows else None


def age_on(birth_date, on):
    """Whole years of age on a date (both datetime.date), or None without a birth date."""
    if not birth_date:
        return None
    return on.year - birth_date.year - ((on.month, on.day) < (birth_date.month, birth_date.day))


def points_per_game(row):
    """Points per game for a skater row, None for a goalie or an unplayed row."""
    if not row or not row.get("games") or row.get("points") is None:
        return None
    return row["points"] / row["games"]
