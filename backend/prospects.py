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


# --- Watched prospects in the morning email ---------------------------------------------------------------------
RECENT_DAYS = 3        # a change in a prospect's games total this recent is "lately"
COMPARE_MIN_GAMES = 10  # games needed in both seasons (same league) to compare a points-per-game rate with last season's
COMPARE_GAP = 0.15     # points per game apart before the comparison is worth saying


def recent_change(line, now):
    """What a prospect's season line gained the last time the nightly refresh saw it move: {games, points, days_ago}, or None.

    The stored data is season totals, so this is a difference between two refreshes, not a fixed window: usually the last
    game or few. line: a prospect_season row with prev_games, prev_points and changed_at (a tz-aware datetime, or None)."""
    if not line or line.get("changed_at") is None or line.get("prev_games") is None or line.get("games") is None:
        return None
    games = line["games"] - line["prev_games"]
    days = (now - line["changed_at"]).days
    if games <= 0 or days > RECENT_DAYS:
        return None
    points = None
    if line.get("points") is not None and line.get("prev_points") is not None:
        points = line["points"] - line["prev_points"]
    return {"games": games, "points": points, "days_ago": days}


def prior_rate(seasons, season_id, league):
    """Points per game in the same league the season before `season_id`, when there were enough games to mean something."""
    prev = [s for s in seasons if s["season_id"] == season_id - 10001 and s["game_type"] == 2 and s["league"] == league]
    row = max(prev, key=lambda s: s["games"], default=None)
    return points_per_game(row) if row and row["games"] >= COMPARE_MIN_GAMES else None


def alert(p, line, seasons, now, season_id):
    """One watched prospect, ready for the email. p: the prospect row; line: this season's current line (current_line) or
    None; seasons: all their prospect_season rows. Skater lines carry a rate comparison with last season in the same league."""
    goalie = p["position"] == "G"
    out = {"name": p["name"], "team": p["team"], "position": p["position"], "goalie": goalie, "league": None, "games": 0,
           "goals": None, "assists": None, "points": None, "wins": None, "save_pct": None, "gaa": None,
           "ppg": None, "prior_ppg": None, "change": None}
    if line:
        out.update(league=line["league"], games=line["games"], goals=line["goals"], assists=line["assists"], points=line["points"],
                   wins=line["wins"], save_pct=line["save_pct"], gaa=line["gaa"], ppg=points_per_game(line),
                   change=recent_change(line, now))
        if not goalie:
            out["prior_ppg"] = prior_rate(seasons, season_id, line["league"])
    return out


def alert_line(a):
    """One sentence for a prospect in the email."""
    who = f"{a['name']} ({a['team']} prospect, {a['position']})"
    if a["games"] == 0:
        return f"{who} has no games on record this season yet."
    league = f" in the {a['league']}" if a["league"] else ""
    if a["goalie"]:
        sv = f", {a['save_pct']:.3f} save percentage" if a["save_pct"] is not None else ""
        wins = f", {a['wins']} wins" if a["wins"] is not None else ""
        text = f"{who}: {a['games']} games{league}{wins}{sv}."
    else:
        text = f"{who}: {a['goals']}-{a['assists']}-{a['points']} in {a['games']} games{league} ({a['ppg']:.2f} points a game)."
    c = a.get("change")
    if c:
        when = "since the last update" if c["days_ago"] == 0 else f"over the last {c['days_ago'] + 1} days"
        gained = f", {c['points']} point{'s' if c['points'] != 1 else ''}" if c["points"] is not None and not a["goalie"] else ""
        text += f" Lately: {c['games']} game{'s' if c['games'] != 1 else ''}{gained} {when}."
    if a.get("prior_ppg") is not None and a["ppg"] is not None and abs(a["ppg"] - a["prior_ppg"]) >= COMPARE_GAP:
        text += f" {'Up' if a['ppg'] > a['prior_ppg'] else 'Down'} from {a['prior_ppg']:.2f} a game last season."
    return text


def called_up_line(name, team, nhl_games, points, goalie=False):
    """One sentence for a watched prospect who now has NHL games this season."""
    stat = f"{nhl_games} NHL game{'s' if nhl_games != 1 else ''}" + ("" if goalie or points is None else f", {points} point{'s' if points != 1 else ''}")
    return f"{name} has reached the NHL with {team}: {stat} so far. He is now followed like any other player."
