"""Backtest: how strongly should an early-season points-per-game rate be pulled toward a prior?

Run from backend/ (needs the stored game logs): .venv/bin/python -I analysis/backtest_player_prior.py

For each past season and each player with 40+ games: take the first N games (10 and 25), predict points per game over the rest
of the season, and score each predictor by root-mean-square error. Compared: the raw early rate, the early rate pulled toward the
position average with a prior weight of k games, and pulled toward the player's own previous season. (The two-season version
is in backtest_player_prior_two_seasons.py.) This is where the prior weights in frontend/src/value.js came from: pulling toward the
position average is best at k = 5 to 10, and pulling toward the player's own record is much better (error about 0.15 against 0.20).
Only goals, assists and points have past game logs, so nothing else can be backtested this way.
"""
import math
from pathlib import Path
import sys
from collections import defaultdict

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config

with psycopg.connect(config.DATABASE_URL) as conn:
    games = defaultdict(lambda: defaultdict(list))   # season -> player -> [points per game in date order]
    for pid, season, pts in conn.execute(
            "SELECT player_id, season_id, points FROM skater_game_hist ORDER BY player_id, season_id, game_date, game_id"):
        games[season][pid].append(pts)
    pos = dict(conn.execute("SELECT player_id, CASE WHEN position = 'D' THEN 'D' ELSE 'F' END FROM career_skater WHERE game_type = 2"))

seasons = sorted(games)
ks = [0, 5, 10, 15, 20, 30, 50, 80]


def rmse(errors):
    return math.sqrt(sum(e * e for e in errors) / len(errors))


for early_n in (10, 25):
    group_err = defaultdict(list)
    own_err = defaultdict(list)
    raw_err, last_only_err, n_players = [], [], 0
    for season in seasons[1:]:
        prev = games[seasons[seasons.index(season) - 1]]
        # group means from this season's early games (what we would know at the time)
        tot = defaultdict(lambda: [0, 0])
        for pid, pts in games[season].items():
            if len(pts) >= 40 and pid in pos:
                tot[pos[pid]][0] += sum(pts[:early_n])
                tot[pos[pid]][1] += early_n
        for pid, pts in games[season].items():
            if len(pts) < 40 or pid not in pos:
                continue
            early, rest = pts[:early_n], pts[early_n:]
            target = sum(rest) / len(rest)
            rate = sum(early) / early_n
            g = pos[pid]
            mean = tot[g][0] / tot[g][1]
            raw_err.append(rate - target)
            for k in ks:
                group_err[k].append((sum(early) + k * mean) / (early_n + k) - target)
            if pid in prev and len(prev[pid]) >= 40:
                last = sum(prev[pid]) / len(prev[pid])
                last_only_err.append(last - target)
                for k in ks:
                    own_err[k].append((sum(early) + k * last) / (early_n + k) - target)
                n_players += 1
    print(f"\n=== first {early_n} games -> rest of season ({len(raw_err)} player-seasons; {n_players} with a prior season)")
    print(f"raw early rate:                  rmse {rmse(raw_err):.4f}")
    print("shrunk toward the position mean:  " + "  ".join(f"k={k}: {rmse(group_err[k]):.4f}" for k in ks))
    if own_err[0]:
        print(f"last season's rate alone:        rmse {rmse(last_only_err):.4f}")
        print("shrunk toward own last season:    " + "  ".join(f"k={k}: {rmse(own_err[k]):.4f}" for k in ks))
