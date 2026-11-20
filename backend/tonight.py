"""What to watch tonight: rank a day's games by how much they are worth your attention, and say why.

Each game gets points for the things that make a game worth watching, and the reasons that earned them:
- close matchup: the two teams' strength (matchups.py ratings, the win model of streaming.py plus home ice) leaves the win chance near
  even, up to W_CLOSE points
- scoring: more expected goals than the league's average game, up to W_GOALS points
- stakes: both teams are in the playoff race (playoff odds between RACE_LOW and RACE_HIGH), up to W_STAKES points
- stars: the best scorer on either team is at or above STAR_PPG points a game, up to W_STARS points
- yours: players on your roster or watchlist playing, W_PLAYER each (at most MAX_PLAYERS), and W_TEAM when a team you follow plays

The weights are judgment calls, not fitted to anything: this is a way to sort the night, not a measurement of how good a game
will be. It can't see injuries or lineups, and early in a season the playoff odds are close to 50% for most teams, so stakes
barely separates games until the standings spread out.
"""
import math

import streaming

# Home teams win a bit more than half their games whoever is playing. Measured over the 20,054 stored games from 2005-06 to
# 2021-22 it was 54.7% (54.1% over the last five of those seasons); 54.5% is used, applied as a shift in the log-odds so it
# fades toward the edges the way a real advantage does. Taken from the long history, not from this season, so a hot or cold
# stretch of home results this year doesn't leak into it.
HOME_WIN_RATE = 0.545
HOME_LOGIT = math.log(HOME_WIN_RATE / (1 - HOME_WIN_RATE))

W_CLOSE = 2.0
W_GOALS = 2.0
W_STAKES = 3.0
W_STARS = 2.0
W_PLAYER = 2.0
MAX_PLAYERS = 3
W_TEAM = 3.0
CLOSE_BAND = 0.06      # a win chance within this of even counts as a toss-up
RACE_LOW, RACE_HIGH = 0.2, 0.8
STAR_PPG = 1.2         # points a game for the best scorer on either team to count as a star matchup
GOALS_SCALE = 0.25     # 25% more goals than an average game earns the full scoring points


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


WIN_RATE_PER_LOGIT = 0.25   # near an even game, one logit of win chance is a quarter of a win-rate point (the slope of the logistic at 0.5)


def rest_logit(kind, win_gaps):
    """Log-odds shift to the home team's win chance from its rest situation, or 0.

    kind: the home team's situation (fatigue.kind: "tired" is a back-to-back against a rested team, "edge" is rested against a team on
    one). win_gaps: {kind: win-rate gap} from fatigue.effects, the change in a team's win rate in those games against its normal games
    (negative for tired, positive for edge). Only the home team's own kind is used: the figure already includes the opponent being
    rested (or tired), so adding the visitor's side as well would count the same game twice. Both teams tired, or neither, shifts nothing."""
    if kind not in ("tired", "edge"):
        return 0.0
    gap = (win_gaps or {}).get(kind)
    return 0.0 if gap is None else gap / WIN_RATE_PER_LOGIT


def matchup(home, away, league, home_rest=None, win_gaps=None):
    """(home win chance, expected total goals) for a game, from the two teams' ratings, or (None, None) without them.
    home, away: dicts with off_ratio and def_ratio; league: {goals_pg, shots_pg}. The win chance includes home ice (HOME_LOGIT) and, when
    home_rest and win_gaps are given, the back-to-back effect (see rest_logit)."""
    if not home or not away or not league or not league.get("goals_pg") or not league.get("shots_pg"):
        return None, None
    line = streaming.expected_line(home, away, league["goals_pg"], league["shots_pg"])
    p = line["win"]
    p = min(1 - 1e-9, max(1e-9, p))
    logit = math.log(p / (1 - p)) + HOME_LOGIT + rest_logit(home_rest, win_gaps)
    return 1 / (1 + math.exp(-logit)), line["gf"] + line["ga"]


def score_game(win, total, league_total, odds, star, yours, teams_followed):
    """Interest points and reasons for one game.

    win: home win chance or None. total: expected total goals or None. league_total: the average game's goals.
    odds: [home, away] playoff odds (None when unknown). star: {name, ppg, gp} for the best scorer on either team, or None.
    yours: names of your roster and watchlist players in the game. teams_followed: abbreviations of followed teams playing.
    Returns {score, reasons}, the reasons in the order they were earned (most points first).
    """
    parts = []   # (points, reason)
    if win is not None:
        close = _clip(1 - abs(win - 0.5) / 0.5)   # 1 at a coin flip, 0 for a sure thing
        if abs(win - 0.5) <= CLOSE_BAND:
            parts.append((W_CLOSE * close, f"Toss-up on paper (home team {round(win * 100)}% to win)"))
        else:
            parts.append((W_CLOSE * close * 0.5, None))
    if total is not None and league_total:
        extra = _clip((total / league_total - 1) / GOALS_SCALE)
        if extra > 0:
            parts.append((W_GOALS * extra, f"High-scoring matchup ({total:.1f} goals expected)" if extra >= 0.3 else None))
    if odds and None not in odds and all(RACE_LOW <= o <= RACE_HIGH for o in odds):
        mid = 1 - (abs(odds[0] - 0.5) + abs(odds[1] - 0.5))   # closer to 50% each is bigger stakes
        parts.append((W_STAKES * _clip(mid), f"Both teams are in the playoff race ({round(odds[0] * 100)}% and {round(odds[1] * 100)}% to make it)"))
    if star and star["ppg"] >= STAR_PPG:
        parts.append((W_STARS * _clip((star["ppg"] - STAR_PPG) / 0.6 + 0.5), f"Star power: {star['name']} ({star['ppg']:.2f} points a game)"))
    if yours:
        n = min(len(yours), MAX_PLAYERS)
        shown = ", ".join(yours[:3]) + (f" and {len(yours) - 3} more" if len(yours) > 3 else "")
        parts.append((W_PLAYER * n, f"Your players: {shown}"))
    if teams_followed:
        parts.append((W_TEAM, f"You follow {', '.join(teams_followed)}"))
    parts.sort(key=lambda p: -p[0])
    return {"score": round(sum(p[0] for p in parts), 2), "reasons": [r for _, r in parts if r]}
