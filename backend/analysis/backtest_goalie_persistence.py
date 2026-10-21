"""Backtest: how much of a goalie's goals saved above expected carries into the next season?

Run from backend/ (needs shot_hist): .venv/bin/python -I analysis/backtest_goalie_persistence.py

Predicts next season's goals saved above expected per 100 shots from the goalie's earlier seasons pooled, pulled toward 0 (an
average goalie) with a prior of k shots. Findings behind backend/matchups.py and streaming.py: it barely repeats. The best prior is
about 8,000 shots and improves on assuming an average goalie by under 2% (the slope of next season on the earlier rate is about 0.16).
"""
from pathlib import Path
import math, sys
from collections import defaultdict
import psycopg
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config, luck_db
with psycopg.connect(config.DATABASE_URL) as conn:
    rows = conn.execute(f"""WITH {luck_db.GOALIE_CALIBRATION_CTE}
        SELECT goalie_id, season_id, count(*) AS faced,
               count(*) FILTER (WHERE kind='goal' AND xg IS NOT NULL) AS goals, sum({luck_db.GOALIE_XG}) AS xga
        FROM shot_hist JOIN gcal USING (season_id) WHERE goalie_id IS NOT NULL AND kind IN ('shot','goal')
        GROUP BY goalie_id, season_id""").fetchall()
data = defaultdict(dict)
for gid, season, faced, goals, xga in rows:
    data[gid][season] = (faced, float(xga) - goals)       # shots faced, GSAx
seasons = sorted({s for d in data.values() for s in d})
ks = [0, 500, 1000, 2000, 4000, 8000, 16000]
for min_target in (600,):
    errs = defaultdict(list); n = 0
    for gid, d in data.items():
        for s in seasons[1:]:
            if s not in d or d[s][0] < min_target: continue
            prior = [d[p] for p in seasons if p < s and p in d]
            shots = sum(f for f, _ in prior); gsax = sum(g for _, g in prior)
            if shots < 300: continue
            target = d[s][1] / d[s][0] * 100
            for k in ks: errs[k].append(gsax / (shots + k) * 100 - target)
            errs["zero"].append(0 - target); n += 1
    rm = lambda e: math.sqrt(sum(x*x for x in e)/len(e))
    print(f"goalie seasons with {min_target}+ shots and 300+ prior shots: {n}")
    print("predict league average (0):    rmse %.4f" % rm(errs["zero"]))
    print("prior seasons, prior k shots:  " + "  ".join(f"k={k}: {rm(errs[k]):.4f}" for k in ks))
    # regression slope of next-season rate on prior pooled rate
    xs, ys = [], []
    for gid, d in data.items():
        for s in seasons[1:]:
            if s not in d or d[s][0] < min_target: continue
            prior = [d[p] for p in seasons if p < s and p in d]
            shots = sum(f for f, _ in prior)
            if shots < 300: continue
            xs.append(sum(g for _, g in prior) / shots * 100); ys.append(d[s][1] / d[s][0] * 100)
    mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
    slope = sum((x-mx)*(y-my) for x,y in zip(xs,ys)) / sum((x-mx)**2 for x in xs)
    sd = lambda v: math.sqrt(sum((a-sum(v)/len(v))**2 for a in v)/len(v))
    print(f"slope of next season on prior rate: {slope:.3f}   (sd of prior rate {sd(xs):.3f}, of next {sd(ys):.3f}, n={len(xs)})")
