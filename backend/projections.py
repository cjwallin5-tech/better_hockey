"""Rest-of-season projections for skaters: points, goals and assists the rest of the way, and a finish range.

Method (the numbers come from analysis/backtest_projection_xg.py, a backtest on 744 player-seasons):
- Goals and assists per game are each pulled toward the player's own record over the last two seasons (the more recent
  counting double, see /api/fantasy/priors), worth PRIOR_GAMES games of it. A player with no record is pulled toward
  the average for forwards or defensemen, worth NO_RECORD_GAMES games.
- The goals part uses a blend of the goals scored and the goals the player's own shots were worth (expected goals,
  scaled so the league's total matches its goals): XG_WEIGHT of the second. That beat plain goals by about 1% in the
  backtest at every checkpoint, so it is a small gain, not a big one.
- Games left come from the schedule, scaled by the share of the team's games the player has played so far (injuries
  and scratches still to come are not predicted).
- The range is an 80% interval for the points still to come, from how far off the backtest was: the variance grows
  with the games left (scoring is lumpy) and with their square (the player's true rate is uncertain). It was right
  about 84% of the time in the backtest. It says nothing about injuries.
"""
import math

PRIOR_GAMES = 40
NO_RECORD_GAMES = 10
XG_WEIGHT = 0.5
VARIANCE_PER_POINT = 1.5    # backtest fit: variance of points over L games = 1.5 * L * rate + 0.0066 * L^2
RATE_VARIANCE = 0.0066
Z80 = 1.2816
MIN_REGULAR_SHARE = 1 / 3   # a "regular" for the position averages has played at least this share of the most games


def shrink(total, games, prior_rate, prior_games):
    return (total + prior_games * prior_rate) / (games + prior_games)


def role(position):
    return "D" if position == "D" else "F"


def league_factor(rows):  # rows: luck_db.skater_rows output (ixg and goals from the shot table)
    """Goals per expected goal over every skater with both figures (1.0 when there is nothing to scale against)."""
    goals = sum(r["goals"] for r in rows if r.get("ixg"))
    xg = sum(r["ixg"] for r in rows if r.get("ixg"))
    return goals / xg if xg else 1.0


def role_averages(rows):
    """{role: (goals per game, assists per game)} over regulars, so a rookie is pulled toward their own kind."""
    out = {}
    most = max((r["games_played"] for r in rows), default=0)
    for ro in ("F", "D"):
        reg = [r for r in rows if role(r["position"]) == ro and r["games_played"] >= max(1, most * MIN_REGULAR_SHARE)]
        gp = sum(r["games_played"] for r in reg)
        out[ro] = (sum(r["goals"] for r in reg) / gp, sum(r["assists"] for r in reg) / gp) if gp else (0.0, 0.0)
    return out


def interval(rate, games):
    """(low, high) 80% range for the points over `games` more games at `rate` points a game."""
    sd = math.sqrt(VARIANCE_PER_POINT * games * rate + RATE_VARIANCE * games * games)
    mid = rate * games
    return max(0.0, mid - Z80 * sd), mid + Z80 * sd


def project(r, prior, averages, factor, team_left, team_played):
    """One skater's projection.

    r: games_played, goals, assists, position, and ixg (the player's expected goals, optional).
    prior: {goals, assists} per game over earlier seasons, or None. team_left / team_played: the team's games left
    and played, or None when unknown (then a full season is assumed to be the games left).
    """
    gp = r["games_played"]
    ixg = r.get("ixg")
    goals = r["goals"] if ixg is None else (1 - XG_WEIGHT) * r["goals"] + XG_WEIGHT * ixg * factor
    if prior:
        pg, pa, k = prior["goals"], prior["assists"], PRIOR_GAMES
    else:
        (pg, pa), k = averages[role(r["position"])], NO_RECORD_GAMES
    goal_rate, assist_rate = shrink(goals, gp, pg, k), shrink(r["assists"], gp, pa, k)
    share = min(1.0, gp / team_played) if team_played else 1.0
    games = (team_left or 0) * share
    low, high = interval(goal_rate + assist_rate, games)
    now = r["goals"] + r["assists"]
    return {
        "games_left": team_left, "expected_games": games, "play_share": share,
        "goals_rate": goal_rate, "assists_rate": assist_rate, "points_rate": goal_rate + assist_rate,
        "rest_goals": goal_rate * games, "rest_assists": assist_rate * games, "rest_points": (goal_rate + assist_rate) * games,
        "final_goals": r["goals"] + goal_rate * games, "final_assists": r["assists"] + assist_rate * games,
        "final_points": now + (goal_rate + assist_rate) * games,
        "low_points": now + low, "high_points": now + high,
        "has_record": bool(prior),
    }


def goalie_final(now, games):
    """One goalie's projected finish: what he has now plus the expected rest of the season.

    now: his season row (games_started, wins, losses, ot_losses, saves, shots_against, goals_against, shutouts; None counts
    as 0). games: his remaining games from the streaming plan, each with the chance he starts it and the line a start there
    is worth (streaming.py). The rest is the sum of those lines weighted by the start chance; no range is given because the
    start count comes from recent usage and cannot see injuries or trades."""
    have = lambda k: now.get(k) or 0
    rest = {"starts": 0.0, "win": 0.0, "loss": 0.0, "otl": 0.0, "saves": 0.0, "shots": 0.0, "ga": 0.0, "shutout": 0.0}
    for g in games:
        p = g.get("probability") or 0.0
        rest["starts"] += p
        for k in rest:
            if k != "starts":
                rest[k] += p * (g["line"].get(k) or 0.0)
    return {
        "games_played": have("games_played"), "starts": have("games_started"), "wins": have("wins"), "saves": have("saves"),
        "goals_against": have("goals_against"), "shutouts": have("shutouts"),
        "rest_starts": rest["starts"], "rest_wins": rest["win"], "rest_saves": rest["saves"], "rest_goals_against": rest["ga"],
        "rest_shutouts": rest["shutout"],
        "final_starts": have("games_started") + rest["starts"], "final_wins": have("wins") + rest["win"],
        "final_saves": have("saves") + rest["saves"], "final_goals_against": have("goals_against") + rest["ga"],
        "final_shutouts": have("shutouts") + rest["shutout"],
    }
