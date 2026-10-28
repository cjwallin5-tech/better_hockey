"""Study: when a regular is out, who gets his ice time, and how much of it can be predicted?

Run from backend/: .venv/bin/python -I analysis/backtest_absences.py      (needs data/absence_toi.json.gz: analysis/absence_data.py)

Four seasons (2022-23 to 2025-26) of every skater's even-strength, power-play and shorthanded seconds in every game. An event is a team game in
which exactly one regular (see absences.regulars: in at least 7 of the previous 10 games) did not play. For every teammate who did play, the
change is his seconds that game minus his own average over the previous ten games in which he and the absent player both played. The same
change in games with NO regular missing is the "null": game-to-game drift that has nothing to do with an absence (a few more or fewer penalties,
a blowout) and is subtracted, so every figure is the extra caused by the absence.

Prints the average extra by position group and the absent player's role, then fits the table absences.expected_change reads (the average extra
for each absent-role and teammate-role pair, per group), scores it on a season it was not fitted on (R^2), and prints the MODEL constants.

Findings (run on 2026-10-27, 52,986 teammate-games with one regular out, 27,507 with none):
  - Only the absence of a top-role player moves anyone's ice time. When a forward from the top power-play unit (100+ seconds a game) is out, his
    teammate forwards gain about 17 seconds a game at even strength and 10 on the power play (31 in total, +-7); when a top-unit defenseman is
    out, the other defensemen gain about 53 and 16 (74 in total). When a second-unit player is out the gains are 10-30 seconds, and when a player
    with no power-play time is out the teammates gain nothing measurable (a few seconds either way).
  - The gains are spread thinly over the group, not handed to one player: the biggest single cell, a bottom-pair defenseman when a top-pair one is
    out, is around two minutes.
  - The table below explains a few percent of a teammate's change in a game on a season it was not fitted on, so it is an average for his spot, not a
    forecast for him.
  - Points: the extra points per game for a teammate did not line up with anything measured (the signs flip between roles, R^2 near 0 held out), so no
    points forecast is made.
"""
import collections
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
sys.path.insert(0, str(Path(__file__).resolve().parent))          # -I drops the script's own folder
import absence_data
import absences


def build():
    """(events, nulls): lists of dicts for teammate-games, from the cached per-game ice time."""
    rows = absence_data.load()
    teams = collections.defaultdict(lambda: collections.defaultdict(dict))
    dates = {}
    for gid, date, team, pid, pos, ev, pp, sh, pts in rows:
        teams[team, gid // 1000000][gid][pid] = {"ev": ev or 0, "pp": pp or 0, "sh": sh or 0, "position": pos, "points": pts or 0}
        dates[gid] = date
    events, nulls = [], []
    for (team, season), games in teams.items():
        order = sorted(games, key=lambda g: (dates[g], g))
        for i in range(absences.WINDOW + 2, len(order)):
            prev = order[i - absences.WINDOW:i]
            cur = games[order[i]]
            regs = absences.regulars(games, prev)
            missing = [p for p in regs if p not in cur]
            if len(missing) > 1:
                continue
            base = {p: absences.baseline(games, prev, p) for p in regs}
            base = {p: b for p, b in base.items() if b}
            if missing and missing[0] not in base:
                continue
            x = missing[0] if missing else None
            for y, line in cur.items():
                if y not in base or y == x:
                    continue
                by = absences.baseline(games, prev, y, with_player=x) if x else base[y]
                if not by:
                    continue
                row = {"season": season, "y_group": absences.group(line["position"]), "ev": line["ev"] - by["ev"], "pp": line["pp"] - by["pp"],
                       "total": line["ev"] + line["pp"] + line["sh"] - by["total"], "points": line["points"], "y_base": by}
                if x:
                    xg = absences.group(games[prev[-1]].get(x, next(games[g][x] for g in prev if x in games[g]))["position"])
                    row.update(x_group=xg, x_base=base[x], below=by["total"] < base[x]["total"])
                    events.append(row)
                else:
                    nulls.append(row)
    return events, nulls


ROLES = ("PP1", "PP2", "none")
PRIOR_N = 50      # games' worth of the absent role's overall average blended into a sparse cell


def fit_cells(rows, null_mean):
    """{group: {x role: {y role: (ev, pp)}}} extra seconds, each cell pulled toward the absent role's overall average."""
    out = {}
    for g in ("F", "D"):
        out[g] = {}
        for xr in ROLES:
            xs = [r for r in rows if r["x_group"] == g and r["y_group"] == g and absences.role(r["x_base"]["pp"]) == xr]
            if not xs:
                continue
            overall = [np.mean([r[k] for r in xs]) - null_mean[g][k] for k in ("ev", "pp")]
            out[g][xr] = {}
            for yr in ROLES:
                cell = [r for r in xs if absences.role(r["y_base"]["pp"]) == yr]
                n = len(cell)
                out[g][xr][yr] = tuple(round(float((n * (np.mean([r[k] for r in cell]) - null_mean[g][k]) + PRIOR_N * overall[i]) / (n + PRIOR_N)) if n
                                             else overall[i], 1) for i, k in enumerate(("ev", "pp")))
    return out


def main():
    events, nulls = build()
    print(f"{len(events)} teammate-games with one regular out, {len(nulls)} with none")
    null_mean = {g: {k: np.mean([r[k] for r in nulls if r["y_group"] == g]) for k in ("ev", "pp", "total", "points")} for g in ("F", "D")}
    print("\nNull (no one out): mean change in seconds a game, by group:", {g: {k: round(v, 1) for k, v in d.items()} for g, d in null_mean.items()})

    print("\nExtra when a regular is out, same position group, by the absent player's power-play role (PP1 = 100+ s a game, PP2 = 30+):")
    role = lambda sec: "PP1" if sec >= 100 else "PP2" if sec >= 30 else "no PP"
    cells = collections.defaultdict(list)
    for r in events:
        if r["x_group"] == r["y_group"]:
            cells[r["x_group"], role(r["x_base"]["pp"])].append(r)
    for (g, rl), rs in sorted(cells.items()):
        m = null_mean[g]
        ex = lambda k: np.mean([r[k] for r in rs]) - m[k]
        se = lambda k: np.std([r[k] for r in rs]) / math.sqrt(len(rs))
        print(f"  {g} out ({rl:<5}) -> teammates in the same group: ev {ex('ev'):+5.0f}s (+-{1.96 * se('ev'):.0f})  pp {ex('pp'):+4.0f}s  total {ex('total'):+5.0f}s  points {ex('points'):+.3f}   n={len(rs)}")

    print("\nCell model vs a single average (leave one season out; R^2 of even-strength and power-play seconds against that season's mean):")
    seasons = sorted({r["season"] for r in events})
    for g in ("F", "D"):
        same = [r for r in events if r["x_group"] == g and r["y_group"] == g]
        for ti, k in enumerate(("ev", "pp")):
            scores = []
            for test in seasons:
                cells = fit_cells([r for r in events if r["season"] != test], null_mean)
                te = [r for r in same if r["season"] == test]
                truth = np.array([r[k] - null_mean[g][k] for r in te])
                pred = np.array([cells[g][absences.role(r["x_base"]["pp"])][absences.role(r["y_base"]["pp"])][ti] for r in te])
                scores.append(1 - ((truth - pred) ** 2).sum() / ((truth - np.mean([r[k] - null_mean[g][k] for r in same if r["season"] != test])) ** 2).sum())
            print(f"  {g} {k}: R^2 by held-out season " + ", ".join(f"{s:+.3f}" for s in scores))
    cells = fit_cells(events, null_mean)
    print("\nFor absences.py:\nMODEL = {")
    for g, xs in cells.items():
        print(f'    "{g}": {{')
        for xr, ys in xs.items():
            print(f'        "{xr}": {ys},')
        print("    },")
    print("}")


if __name__ == "__main__":
    main()
