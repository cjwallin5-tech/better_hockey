"""Backtest: how well does winprob.py's in-game win probability match what happened?

Run from backend/: .venv/bin/python -I analysis/backtest_winprob.py       (needs data/game_goals.json.gz: analysis/winprob_data.py)

Every game of four seasons (2022-23 to 2025-26) is sampled every 30 seconds of regulation: the score difference, the time left and the teams'
goal-differential ratings going in (from the games played earlier that season only). A logistic regression on winprob.features predicts whether the
home team went on to win (in regulation, overtime or the shootout). Each season is scored with coefficients fitted on the other three, against
two simpler rules: the score alone (no pregame strength, no home edge) and the pregame rating alone (ignoring the score). Games tied after regulation
get their own small model (overtime_prob). Prints calibration by time of game and the COEF / OVERTIME constants for winprob.py.

Findings (run on 2026-10-27, 5,248 games, 629,760 sampled states):
  - Scored on seasons it was not fitted on, the model beats the same score-and-time rule without the teams' ratings and the home edge in every
    part of the game (log loss 0.499 against 0.506 overall; the gain is the pregame strength, worth most early: 0.637 against 0.650 in the first period)
    and is far better than the pregame rating alone (0.674 at game level).
  - It is well calibrated: at 20, 40 and 55 minutes the chance it gives matches how often the home team won within a point or two in every band.
  - One-goal games in the last minutes (when a trailing team pulls its goalie) come out right once LEAD_PAD was set to 2 minutes: home up one
    58:00-60:00, said 94.2%, happened 93.8%; down one, said 7.2%, happened 7.3%. Extra pulled-goalie terms added nothing and were dropped.
  - Games tied after regulation: the home team won 52.3% (1,171 games); the rating gap moves that a little (OVERTIME).
  - Limits: it sees only the score, the time and the pregame ratings, not who is on the ice, penalties, injuries, or the shots so far (the stored history
    has shot quality but not shot times), so it is a baseline: a team being outshot badly while leading is treated like any other leader.
"""
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
sys.path.insert(0, str(Path(__file__).resolve().parent))          # -I drops the script's own folder
import winprob
import winprob_data

STEP = 30
EPS = 1e-4
KEYS = ("lead", "strength", "home", "const")


def games_with_gap(games):
    """Each game with the rating gap going in, using only earlier dates of the same season."""
    out = []
    by_season = defaultdict(list)
    for g in games:
        by_season[g["id"] // 1000000].append(g)
    for season, gs in by_season.items():
        done = []
        i = 0
        while i < len(gs):
            day = [g for g in gs if g["date"] == gs[i]["date"]]
            rate = winprob.ratings(done)
            for g in day:
                out.append({**g, "season": season, "gap": rate.get(g["home"], 0.0) - rate.get(g["away"], 0.0)})
            done += [(g["home"], g["away"], g["hs"], g["as"]) for g in day]
            i += len(day)
    return out


def states(games):
    """(feature rows, outcomes, elapsed, season, d) for regulation states every STEP seconds."""
    X, y, el, ss, ds = [], [], [], [], []
    for g in games:
        home_win = 1 if g["hs"] > g["as"] else 0
        goals = g["goals"]
        gi = d = 0
        for t in range(0, winprob.REGULATION, STEP):
            while gi < len(goals) and goals[gi][0] <= t:
                d += 1 if goals[gi][1] else -1
                gi += 1
            f = winprob.features(d, t, g["gap"])
            X.append([f[k] for k in KEYS])
            y.append(home_win)
            el.append(t)
            ss.append(g["season"])
            ds.append(d)
    return np.array(X), np.array(y), np.array(el), np.array(ss), np.array(ds)


def fit(X, y, cols):
    m = LogisticRegression(C=1e4, fit_intercept=False, max_iter=2000)
    m.fit(X[:, cols], y)
    return m


def scores(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), float(np.mean((p - y) ** 2))


def main():
    games = games_with_gap(winprob_data.load())
    X, y, el, ss, ds = states(games)
    print(f"{len(games)} games, {len(y)} sampled states")
    variants = {"the model": [0, 1, 2, 3], "score and time only": [0, 3]}
    pred = {name: np.zeros(len(y)) for name in variants}
    for season in sorted(set(ss)):
        tr, te = ss != season, ss == season
        for name, cols in variants.items():
            pred[name][te] = fit(X[tr], y[tr], cols).predict_proba(X[te][:, cols])[:, 1]
    # pregame rating alone (the game's final result against rating gap)
    game_gap = np.array([g["gap"] for g in games])
    game_y = np.array([1 if g["hs"] > g["as"] else 0 for g in games])
    game_season = np.array([g["season"] for g in games])
    pre = np.zeros(len(games))
    for season in sorted(set(game_season)):
        tr, te = game_season != season, game_season == season
        A = np.column_stack([game_gap, np.ones(len(games))])
        pre[te] = LogisticRegression(C=1e4, fit_intercept=False, max_iter=1000).fit(A[tr], game_y[tr]).predict_proba(A[te])[:, 1]
    print("\nLog loss and Brier on seasons not used to fit (lower is better; a coin flip is 0.693 / 0.250):")
    buckets = [(0, 1200, "first period"), (1200, 2400, "second period"), (2400, 3300, "third period to 55:00"), (3300, 3600, "last five minutes")]
    print(f"  {'':<30}" + "".join(f"{b[2]:>26}" for b in buckets) + f"{'all states':>20}")
    for name, p in {**pred}.items():
        row = []
        for lo, hi, _ in buckets:
            m = (el >= lo) & (el < hi)
            ll, br = scores(p[m], y[m])
            row.append(f"{ll:>14.4f} / {br:.4f}  ")
        ll, br = scores(p, y)
        print(f"  {name:<30}" + "".join(row) + f"{ll:>10.4f} / {br:.4f}")
    ll, br = scores(pre, game_y)
    print(f"  pregame rating alone (game level): {ll:.4f} / {br:.4f};  home wins {game_y.mean():.1%}; the rating gap fitted: see below")

    print("\nCalibration of the model (said vs happened) at three moments:")
    p = pred["the model"]
    for t0 in (1200, 2400, 3300):
        m = el == t0
        print(f"  {t0 // 60}:00 played, {int(m.sum())} games")
        for lo, hi in ((0, .1), (.1, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.01)):
            k = m & (p >= lo) & (p < hi)
            if k.sum():
                print(f"    {lo:.0%}-{min(hi, 1):.0%}: n={int(k.sum()):<5} said {p[k].mean():.1%}  happened {y[k].mean():.1%}")

    print("\nOne-goal games in the last minutes (the pulled-goalie effect): home win chance, said by the model vs happened")
    for d0, label in ((1, "home up one"), (-1, "home down one")):
        for lo, hi in ((3300, 3480), (3480, 3600)):
            m = (ds == d0) & (el >= lo) & (el < hi)
            if m.sum():
                print(f"  {label:<14} {lo // 60}:{lo % 60:02d}-{hi // 60}:{hi % 60:02d}: n={int(m.sum()):<5} said {p[m].mean():.1%}  happened {y[m].mean():.1%}")

    full = fit(X, y, [0, 1, 2, 3])
    coef = {k: round(float(v), 3) for k, v in zip(KEYS, full.coef_[0])}
    # overtime / shootout: games tied after regulation
    tied = [g for g in games if g["end"] != "REG"]
    A = np.array([[1.0, g["gap"]] for g in tied])
    ty = np.array([1 if g["hs"] > g["as"] else 0 for g in tied])
    ot = LogisticRegression(C=1e4, fit_intercept=False, max_iter=1000).fit(A, ty)
    print(f"\nTied after regulation: {len(tied)} games, home won {ty.mean():.1%}")
    print("\nFor winprob.py:")
    print(f"COEF = {coef}")
    print(f'OVERTIME = {{"const": {ot.coef_[0][0]:.3f}, "strength": {ot.coef_[0][1]:.3f}}}')


if __name__ == "__main__":
    main()
