"""In-game win probability: the chance the home team wins given the score, the time left and how the two teams were rated beforehand.

The state is (goal difference d = home - away, seconds played in regulation, rating gap). Three features and a constant, fitted by a logistic regression in
analysis/backtest_winprob.py on four seasons of goal timelines (about 4,900 games):
  lead      d / sqrt(minutes left + LEAD_PAD): a lead is worth more the less time is left to lose it (the usual random-walk shape)
  strength  rating gap x share of the game left: how the teams were rated beforehand matters in proportion to the time still to play
  home      the share of the game left: the home edge, likewise
(a pulled-goalie term for one-goal games in the last minutes was tried and added nothing once LEAD_PAD was tuned). A game tied at the end of regulation goes to
overtime (a 3-on-3 sudden death, then a shootout): `overtime_prob` is the home win chance from there, which is close to a coin flip.

Ratings are each team's goal differential per game in the season so far, pulled toward zero as if it also had PRIOR_GAMES average games (the same
rating the playoff odds use). What the model cannot see: who is on the ice, penalties, injuries, the shots and expected goals so far (the stored
history has shot quality but not when each shot happened), so a team that has been badly outshot while leading is treated like any other leader.
"""
import math

PRIOR_GAMES = 25
REGULATION = 3600
LEAD_PAD = 2.0                 # minutes added under the square root so a lead at the last second is large but finite (2.0 was best on the late-game calibration)

# Fitted by analysis/backtest_winprob.py (the script prints these lines).
COEF = {"lead": 5.087, "strength": 0.884, "home": 0.086, "const": 0.087}
OVERTIME = {"const": 0.098, "strength": 0.248}


def ratings(results, prior=PRIOR_GAMES):
    """{team: goal differential per game, pulled toward 0} from finished games [(home, away, home_score, away_score)]."""
    gd, gp = {}, {}
    for h, a, hs, as_ in results:
        gd[h] = gd.get(h, 0) + hs - as_
        gd[a] = gd.get(a, 0) + as_ - hs
        gp[h] = gp.get(h, 0) + 1
        gp[a] = gp.get(a, 0) + 1
    return {t: gd[t] / (gp[t] + prior) for t in gd}


def sigmoid(x):
    return 1 / (1 + math.exp(-x)) if x > -700 else 0.0


def features(d, elapsed, gap):
    """The regression's inputs for a regulation state."""
    left = max(REGULATION - elapsed, 0) / 60                 # minutes
    share = left / 60
    return {"lead": d / math.sqrt(left + LEAD_PAD), "strength": gap * share, "home": share, "const": 1.0}


def overtime_prob(gap):
    """The home team's chance once the game is tied after regulation (overtime, then the shootout)."""
    return sigmoid(OVERTIME["const"] + OVERTIME["strength"] * gap)


def win_prob(d, elapsed, gap, coef=None):
    """Home team's chance to win. d: home goals minus away goals; elapsed: seconds played (past regulation means overtime or later);
    gap: home rating minus away rating."""
    if elapsed >= REGULATION:
        return 1.0 if d > 0 else 0.0 if d < 0 else overtime_prob(gap)
    c = coef or COEF
    f = features(d, elapsed, gap)
    return sigmoid(sum(c[k] * v for k, v in f.items()))


def timeline(goals, gap, ended=REGULATION, final_home_win=None, step=60):
    """The home team's win chance through a game.

    goals: [(second, is_home)] in order; ended: the second the game ended (3600 in regulation, later in overtime; a shootout counts as the end of
    overtime, 3900); final_home_win: how it finished, used to close a game the goals alone do not settle (the shootout).
    Returns (points, events): points [[second, p]] every `step` seconds with a step at each goal (two points at the same second, before and after),
    events [{t, home, before, after, diff}] for each goal in order."""
    times = sorted({*range(step, ended, step), min(REGULATION, ended), ended})
    pts = [[0, win_prob(0, 0, gap)]]
    events = []
    d = gi = 0
    for t in times:
        while gi < len(goals) and goals[gi][0] <= t:
            gt, home = goals[gi]
            before = win_prob(d, gt, gap)
            d += 1 if home else -1
            after = win_prob(d, gt, gap)
            events.append({"t": gt, "home": bool(home), "before": before, "after": after, "diff": d})
            pts += [[gt, before], [gt, after]]
            gi += 1
        pts.append([t, win_prob(d, t, gap)])
    if final_home_win is not None and ended >= REGULATION:
        pts.append([ended, 1.0 if final_home_win else 0.0])
    return pts, events


def clock(second):
    """'P2 12:41' (or 'OT 1:05') for a second of game time."""
    period = min(int(max(second - 1, 0) // 1200) + 1, 4)
    into = (max(second - 1, 0) % 1200) + 1
    return f"{'OT' if period == 4 else f'P{period}'} {int(into // 60)}:{int(into % 60):02d}"


def _pct(p):
    return f"{round(p * 100)}%"


def story(home, away, gap, events, home_score, away_score, end_type, points, xg=None):
    """A few plain sentences about how the game was won, from its win-probability timeline: who was favored, how it finished, the goal that
    swung it most, a comeback if the winner was ever in trouble, and when it was settled. end_type: 'REG', 'OT' or 'SO'; xg: {home, away}
    expected goals, optional."""
    home_won = home_score > away_score
    winner, loser = (home, away) if home_won else (away, home)
    won = lambda p: p if home_won else 1 - p          # the home chance seen from the winner's side
    pre = win_prob(0, 0, gap)
    fav, fav_p = (home, pre) if pre >= 0.5 else (away, 1 - pre)
    out = [f"{fav} were the favorites going in ({_pct(fav_p)})." if fav_p >= 0.56 else "The teams were close to even going in (home ice aside)."]
    how = {"REG": "", "OT": " in overtime", "SO": " in a shootout"}.get(end_type, "")
    out.append(f"{winner} won {max(home_score, away_score)}-{min(home_score, away_score)}{how}.")
    if events:
        top = max(events, key=lambda e: abs(e["after"] - e["before"]))
        if abs(top["after"] - top["before"]) >= 0.12:
            scorer = home if top["home"] else away
            b, a = (top["before"], top["after"]) if top["home"] else (1 - top["before"], 1 - top["after"])
            out.append(f"The biggest swing was {scorer}'s goal at {clock(top['t'])}, which moved their win chance from {_pct(b)} to {_pct(a)}.")
    low = min(((won(p), t) for t, p in points if t > 0), default=(1.0, 0))
    if low[0] < 0.2 and not (end_type != "REG" and low[1] >= REGULATION):
        out.append(f"{winner} were down to {_pct(low[0])} at {clock(low[1])} before coming back.")
    else:
        settled = None
        for t, p in points:                                  # the last time the winner's chance was under 90%
            if won(p) < 0.9:
                settled = t
        if settled is not None and settled < 3300 and end_type == "REG":
            out.append(f"It was effectively settled by {clock(settled)}, when {winner}'s chance passed 90% for good.")
    if xg and abs(xg["home"] - xg["away"]) >= 0.6:
        better = home if xg["home"] > xg["away"] else away
        hi, lo = max(xg["home"], xg["away"]), min(xg["home"], xg["away"])
        out.append(f"{better} had the better of the chances ({hi:.1f} to {lo:.1f} expected goals)" + (" and won it." if better == winner else f", but {winner} won."))
    return out
