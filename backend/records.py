"""NHL-records-style career figures for every skater: hat tricks and other big games, milestone seasons (100-point, 50-goal, ...),
best single seasons and rookie-season lines. Pure functions over plain dicts; ingest.py loads the rows and writes the results onto
career_skater, so the all-time board can sort, filter and page them like any other column.

Notes that shape the numbers:
- Big games come from per-game rows with 3+ goals, 3+ assists or 4+ points (the stats API's game-level report, back to 1917-18).
  Every figure here is a count of games, so a player who scored in other games is simply not in the list.
- Milestone seasons and best seasons are regular season only (the playoffs have no 82-game season to measure against).
- A rookie season is the first season with more than ROOKIE_GAMES games, as long as the player was under the NHL's age limit when
  it started. A short call-up before that does not use up rookie status. The NHL's second test (fewer than six games in each of
  two earlier seasons) is not applied, so a handful of cases can differ from the official Calder-eligible list."""
from datetime import date

ROOKIE_GAMES = 25      # a player who has played more than this many games in an earlier season is no longer a rookie
ROOKIE_MAX_AGE = 25    # on September 15 of the season's start year (the Calder Trophy's age limit is under 26)

# (column, stat, threshold): how many seasons reached at least `threshold` of `stat`.
MILESTONES = [
    ("seasons_20g", "goals", 20), ("seasons_30g", "goals", 30), ("seasons_40g", "goals", 40), ("seasons_50g", "goals", 50),
    ("seasons_40a", "assists", 40), ("seasons_50a", "assists", 50), ("seasons_60a", "assists", 60),
    ("seasons_60p", "points", 60), ("seasons_80p", "points", 80), ("seasons_90p", "points", 90), ("seasons_100p", "points", 100),
]
GAME_COLUMNS = ["hat_tricks", "four_goal_games", "five_goal_games", "three_assist_games", "four_point_games", "five_point_games"]
SEASON_COLUMNS = ["seasons_played", "best_goals", "best_assists", "best_points"] + [m[0] for m in MILESTONES]
ROOKIE_COLUMNS = ["rookie_season", "rookie_gp", "rookie_goals", "rookie_assists", "rookie_points", "rookie_points_per_game"]
RATE_COLUMNS = ["goals_per_game", "assists_per_game"]
# Every column this module adds to career_skater, with its SQL type (schema.sql must declare the same ones; a test checks it).
COLUMNS = ([(c, "INTEGER") for c in GAME_COLUMNS + SEASON_COLUMNS + ROOKIE_COLUMNS if c != "rookie_points_per_game"]
           + [("rookie_points_per_game", "REAL")] + [(c, "REAL") for c in RATE_COLUMNS])


def game_counts(games):
    """{(player_id, game_type): {column: count}} from per-game rows (dicts with player_id, game_type, goals, assists, points)."""
    out = {}
    for g in games:
        c = out.setdefault((g["player_id"], g["game_type"]), dict.fromkeys(GAME_COLUMNS, 0))
        c["hat_tricks"] += g["goals"] >= 3
        c["four_goal_games"] += g["goals"] >= 4
        c["five_goal_games"] += g["goals"] >= 5
        c["three_assist_games"] += g["assists"] >= 3
        c["four_point_games"] += g["points"] >= 4
        c["five_point_games"] += g["points"] >= 5
    return out


def season_figures(seasons):
    """{player_id: {column: value}}: seasons played, best single season and each milestone count, from regular-season rows
    (dicts with player_id, goals, assists, points)."""
    out = {}
    for s in seasons:
        o = out.setdefault(s["player_id"], dict.fromkeys(SEASON_COLUMNS, 0))
        o["seasons_played"] += 1
        for col, stat in (("best_goals", "goals"), ("best_assists", "assists"), ("best_points", "points")):
            o[col] = max(o[col], s[stat])
        for col, stat, at in MILESTONES:
            o[col] += s[stat] >= at
    return out


def _age_at_season_start(birth, season_id):
    """Whole years old on September 15 of the season's first calendar year."""
    start = season_id // 10000
    return start - birth.year - ((birth.month, birth.day) > (9, 15))


def rookie_lines(seasons, birth_dates):
    """{player_id: {column: value}}: each player's rookie-season line. seasons: dicts with player_id, season_id, games_played, goals,
    assists, points. birth_dates: {player_id: date or None}; a missing birth date is not held against the player."""
    by_player = {}
    for s in seasons:
        by_player.setdefault(s["player_id"], []).append(s)
    out = {}
    for pid, rows in by_player.items():
        rookie = next((s for s in sorted(rows, key=lambda r: r["season_id"]) if s["games_played"] > ROOKIE_GAMES), None)
        if rookie is None:
            continue
        birth = birth_dates.get(pid)
        if isinstance(birth, date) and _age_at_season_start(birth, rookie["season_id"]) > ROOKIE_MAX_AGE:
            continue
        gp = rookie["games_played"]
        out[pid] = {"rookie_season": rookie["season_id"], "rookie_gp": gp, "rookie_goals": rookie["goals"],
                    "rookie_assists": rookie["assists"], "rookie_points": rookie["points"],
                    "rookie_points_per_game": round(rookie["points"] / gp, 3)}
    return out
