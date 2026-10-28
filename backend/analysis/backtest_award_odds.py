"""Backtest: how well does a statistical model of the Hart, Norris, Calder, Selke and Vezina voting predict the winners?

Run from backend/: .venv/bin/python -I analysis/backtest_award_odds.py        (needs data/award_backtest.json: analysis/award_data.py)

For each award and each season from 2005-06 to 2024-25 the candidates are the stats' own short list (awards.pool) with unitless features
(awards.features), and a conditional logit (a softmax across the candidates) is fitted to the actual winners. Each season is scored with
weights fitted on the OTHER seasons (leave one season out), so no season helps predict itself. Reported per award: how many seasons the winner
was on the short list at all, the average chance given to the winner (a uniform guess on the short list gives 1 / its size), log loss against
that uniform guess, how often the top pick won and how often the winner was in the top three, and against a plain rule (the points
leader, or the leading goalie by goals saved above average). Shared awards (the Vezina was split in some seasons) count each co-winner.
It prints the fitted weights for awards.py.

Findings (run on 2026-10-27, 20 seasons, scored on seasons the weights had not seen):
  - Vezina: the winner got 70% on average (uniform 12.5%); the top pick won 15 of 20 (given 80%, won 75%), the winner was always in the top three.
  - Calder: 58% (uniform 12.5%); top pick won 11 of 16 (given 69%, won 69%). Winners who were goalies or off the list are not covered.
  - Hart: 50% (uniform 10%); top pick won 11 of 18 (given 63%, won 61%); the points leader alone won 12 of 18, so the model's value is its
    probabilities and the winners it sees coming from further down (Henrik Sedin, Perry), not a better single pick. Goalie winners (Price, 2015) are off the list.
  - Norris: 38% (uniform 12.5%) on the 16 seasons with shot-attempt data (2009-10 on); top pick won 7 of 15 (given 56%, won 47%: a little
    overconfident). Adding penalty-kill time and shot-attempt share to points and ice time cut the log loss on those seasons from 1.43 to 1.25;
    blocks, hits, takeaways, giveaways and the team's record added nothing (about 20 feature sets were tried, so the gain is a little flattered).
  - Selke: 40% (uniform 5%) on the same 16 seasons; top pick won 9 of 16 (given 58%, won 56%), winner in the top three 15 times; the top scorer
    alone won 2 of 16. Faceoff share for centers is the biggest single help (log loss 2.2 to 1.2 when added). The short list (forwards ranked best on
    points, shot-attempt share and penalty-kill time added up, top 20) held every winner in the 20 seasons I checked.
  - The NHL has no shot-attempt share before 2009-10, so seasons before that are skipped for the Norris and Selke.
  - Not tested: the early-season mode (odds() draws many finishes from the rest-of-season projections and adds a guessed 12% chance of a
    long absence). The stored data has only full-season lines, so it can only be checked as more seasons play out. 2025-26's awards are not in the data yet.
Limits: about 18 winners per award, so every figure here moves by a few points with one season; the features are all from season totals.
"""
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
sys.path.insert(0, str(Path(__file__).resolve().parent))          # -I drops the script's own folder
import awards
import award_data
import oldgames

RIDGE = 0.01
NEEDS_SAT = ('norris', 'selke')


def team_pct_for(teams, year, abbrevs):
    pcts = []
    for a in (abbrevs or "").split(","):
        t = teams.get(str(year), {}).get(oldgames.current_code(a.strip()))
        if t:
            pcts.append(awards.team_pct(t["points"], t["gp"]))
    return sum(pcts) / len(pcts) if pcts else 0.5


def season_rows(data, year):
    """(skaters, goalies) in awards.pool()'s shape for the season ending in `year`."""
    teams, bio = data["teams"], data["bio"]
    skaters = []
    for r in data["skaters"][str(year)]:
        b = bio.get(str(r["id"]), {})
        age = None
        if b.get("born"):
            age = year - int(b["born"][:4]) - (1 if int(b["born"][5:7]) > 2 else 0)
        skaters.append({"id": r["id"], "name": r["name"], "pos": r["pos"], "team": r["team"], "gp": r["gp"], "goals": r["goals"], "points": r["points"],
                        "toi_pg": r["toi_pg"], "team_pct": team_pct_for(teams, year, r["team"]), "sat": r.get("satPct"),
                        "sh": r.get("shTimeOnIcePerGame"), "fo": r.get("faceoffWinPct"), "fo_n": r.get("totalFaceoffs"), "takeaways": r.get("takeaways"),
                        "rookie": b.get("first") == (year - 1) * 10000 + year, "age": age})
    goalies = [{"id": r["id"], "name": r["name"], "team": r["team"], "gp": r["gp"], "wins": r["wins"], "saves": r["saves"],
                "shots_against": r["shots_against"], "team_pct": team_pct_for(teams, year, r["team"])} for r in data["goalies"][str(year)]]
    return skaters, goalies


def seasons_for(data, award):
    """[{year, rows, X, winners}]: each season's short list, its feature matrix and the indexes of the winner(s) on it."""
    out = []
    for year in range(award_data.FIRST, award_data.LAST + 1):
        if award in NEEDS_SAT and not any(r.get("satPct") is not None for r in data["skaters"][str(year)]):
            continue          # the NHL has no shot-attempt share before 2009-10, so those seasons cannot test a model that uses it
        status = data["awards"][award].get(str(year), {})
        winners = {int(p) for p, s in status.items() if s == "WINNER"}
        skaters, goalies = season_rows(data, year)
        rows = awards.pool(award, skaters, goalies)
        out.append({"year": year, "rows": rows, "X": np.array(awards.features(award, rows)), "winners": [i for i, r in enumerate(rows) if r["id"] in winners],
                    "winner_ids": winners})
    return out


def fit(seasons):
    """Conditional-logit weights for the seasons whose winner is on the short list."""
    usable = [s for s in seasons if s["winners"]]
    k = usable[0]["X"].shape[1]

    def nll(w):
        total = RIDGE * float(w @ w)
        for s in usable:
            scores = s["X"] @ w
            lse = scores.max() + math.log(np.exp(scores - scores.max()).sum())
            total += sum(lse - scores[i] for i in s["winners"]) / len(s["winners"])
        return total

    return minimize(nll, np.zeros(k), method="L-BFGS-B").x


def probs(X, w):
    z = X @ w
    e = np.exp(z - z.max())
    return e / e.sum()


def report(award, seasons):
    names = awards.FEATURES[award]
    usable = [s for s in seasons if s["winners"]]
    print(f"\n=== {award.title()} ({len(usable)} of {len(seasons)} seasons tested had the winner on the short list of {awards.POOL[award]}) ===")
    stats = {"p": [], "ll": [], "uniform_ll": [], "top1": [], "top3": [], "rule": []}
    detail = []
    for s in usable:
        w = fit([t for t in usable if t is not s])
        p = probs(s["X"], w)
        pw = sum(p[i] for i in s["winners"]) / len(s["winners"])
        order = list(np.argsort(-p))
        stats["p"].append(pw)
        stats["ll"].append(-math.log(max(pw, 1e-3)))
        stats["uniform_ll"].append(math.log(len(s["rows"])))
        stats["top1"].append(1.0 if order[0] in s["winners"] else 0.0)
        stats["top3"].append(1.0 if any(i in s["winners"] for i in order[:3]) else 0.0)
        stats["rule"].append(1.0 if 0 in s["winners"] else 0.0)      # the pool is sorted best-first by the plain rule
        detail.append((s["year"], s["rows"][order[0]]["name"], p[order[0]], s["rows"][s["winners"][0]]["name"], pw))
    n = len(usable)
    mean = lambda xs: sum(xs) / len(xs)
    print(f"  chance given to the winner: {mean(stats['p']):.1%} on average (uniform guess {mean([1 / len(s['rows']) for s in usable]):.1%})")
    print(f"  log loss {mean(stats['ll']):.3f} against {mean(stats['uniform_ll']):.3f} for a uniform guess")
    print(f"  the top pick was given {mean([d[2] for d in detail]):.1%} on average and won {mean(stats['top1']):.1%} of the time")
    print(f"  top pick won {sum(stats['top1']):.0f}/{n}, winner in the top three {sum(stats['top3']):.0f}/{n}, the plain rule's pick (leader) won {sum(stats['rule']):.0f}/{n}")
    print(f"  {'season':<8}{'model top pick':<26}{'chance':>8}  {'winner':<26}{'chance':>8}")
    for year, top, ptop, win, pw in detail:
        print(f"  {year:<8}{top:<26}{ptop:>8.1%}  {win:<26}{pw:>8.1%}{'' if top == win else '   <-'}")
    w = fit(usable)
    print(f"  fitted on all seasons: " + ", ".join(f"{name} {x:.2f}" for name, x in zip(names, w)))
    return {name: round(float(x), 2) for name, x in zip(names, w)}


def main():
    data = award_data.load()
    fitted = {}
    for award in awards.AWARDS:
        fitted[award] = report(award, seasons_for(data, award))
    print("\nFor awards.py:\nWEIGHTS = {")
    for award, w in fitted.items():
        print(f'    "{award}": {w},')
    print("}")


if __name__ == "__main__":
    main()
