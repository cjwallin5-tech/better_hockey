"""What to watch tonight: rank a day's games by how much they are worth your attention, and say why.

Each game gets points for the things that make a game worth watching, and the reasons that earned them:
- close matchup: the two teams' strength (matchups.py ratings, the same win model as streaming.py) leaves the win chance near
  even, up to W_CLOSE points
- scoring: more expected goals than the league's average game, up to W_GOALS points
- stakes: both teams are in the playoff race (playoff odds between RACE_LOW and RACE_HIGH), up to W_STAKES points
- stars: the best scorer on either team is at or above STAR_PPG points a game, up to W_STARS points
- yours: players on your roster or watchlist playing, W_PLAYER each (at most MAX_PLAYERS), and W_TEAM when a team you follow plays

The weights are judgment calls, not fitted to anything: this is a way to sort the night, not a measurement of how good a game
will be. It can't see injuries or lineups, and early in a season the playoff odds are close to 50% for most teams, so stakes
barely separates games until the standings spread out.
"""
import streaming

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


def matchup(home, away, league):
    """(home win chance, expected total goals) for a game, from the two teams' ratings, or (None, None) without them.
    home, away: dicts with off_ratio and def_ratio; league: {goals_pg, shots_pg}."""
    if not home or not away or not league or not league.get("goals_pg") or not league.get("shots_pg"):
        return None, None
    line = streaming.expected_line(home, away, league["goals_pg"], league["shots_pg"])
    return line["win"], line["gf"] + line["ga"]


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
