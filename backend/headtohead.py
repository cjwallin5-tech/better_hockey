"""Head-to-head summaries over the games we store: this season plus the previous four.

Team results come from team_game_hist (past seasons) and game (this season); a skater's games against a
team come from their stored game lines, with the opponent found by pairing the two teams of each game. A goalie's
come from this season's goalie_game and, for past seasons, from the stored shots they faced (shot_hist).
A game is one of W, OTW (won in overtime or a shootout), OTL or L from the first team's point of view.
"""
from collections import defaultdict


def team_summary(games):
    """games: dicts with season_id, game_date, gf, ga, result (W/OTW/OTL/L) for team A against team B,
    in any order. Returns the record, goals, a per-season split and the current streak."""
    games = sorted(games, key=lambda g: (g["game_date"], g["game_id"]), reverse=True)
    wins = [g for g in games if g["result"] in ("W", "OTW")]
    losses = [g for g in games if g["result"] in ("L", "OTL")]
    by_season = defaultdict(lambda: {"games": 0, "a_wins": 0, "b_wins": 0, "gf": 0, "ga": 0})
    for g in games:
        s = by_season[g["season_id"]]
        s["games"] += 1
        s["a_wins" if g["result"] in ("W", "OTW") else "b_wins"] += 1
        s["gf"] += g["gf"]
        s["ga"] += g["ga"]
    streak = None
    if games:
        side = games[0]["result"] in ("W", "OTW")
        n = 0
        for g in games:
            if (g["result"] in ("W", "OTW")) != side:
                break
            n += 1
        streak = {"team": "a" if side else "b", "games": n}
    return {
        "games": len(games),
        "a_wins": len(wins), "b_wins": len(losses),
        "a_ot_losses": sum(1 for g in games if g["result"] == "OTL"),
        "b_ot_losses": sum(1 for g in games if g["result"] == "OTW"),
        "a_goals": sum(g["gf"] for g in games), "b_goals": sum(g["ga"] for g in games),
        "streak": streak,
        "by_season": [{"season_id": k, **v} for k, v in sorted(by_season.items(), reverse=True)],
    }


def _line(rows):
    gp = len(rows)
    g, a = sum(r["goals"] for r in rows), sum(r["assists"] for r in rows)
    return {"games": gp, "goals": g, "assists": a, "points": g + a,
            "points_per_game": round((g + a) / gp, 2) if gp else None}


def player_summary(rows, team):
    """rows: every stored game of one player (season_id, game_date, opponent, goals, assists).
    Returns their line against `team`, the same line against everyone else, and a per-season split."""
    vs = [r for r in rows if r["opponent"] == team]
    rest = [r for r in rows if r["opponent"] != team]
    seasons = defaultdict(list)
    for r in vs:
        seasons[r["season_id"]].append(r)
    return {"vs": _line(vs), "rest": _line(rest),
            "by_season": [{"season_id": k, **_line(v)} for k, v in sorted(seasons.items(), reverse=True)]}


def _goalie_line(rows):
    gp = len(rows)
    sa, ga = sum(r["shots_against"] for r in rows), sum(r["goals_against"] for r in rows)
    return {"games": gp, "shots_against": sa, "goals_against": ga,
            "save_pct": round((sa - ga) / sa, 3) if sa else None,
            "shots_per_game": round(sa / gp, 1) if gp else None,
            "goals_against_per_game": round(ga / gp, 2) if gp else None}


def goalie_summary(rows, team):
    """rows: every stored game a goalie faced shots in (season_id, game_date, opponent, shots_against, goals_against).
    Returns their line against `team`, the same line against everyone else, and a per-season split."""
    vs = [r for r in rows if r["opponent"] == team]
    rest = [r for r in rows if r["opponent"] != team]
    seasons = defaultdict(list)
    for r in vs:
        seasons[r["season_id"]].append(r)
    return {"vs": _goalie_line(vs), "rest": _goalie_line(rest),
            "by_season": [{"season_id": k, **_goalie_line(v)} for k, v in sorted(seasons.items(), reverse=True)]}
