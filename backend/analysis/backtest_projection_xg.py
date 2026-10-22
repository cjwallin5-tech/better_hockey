"""Backtest: does expected goals (xG) improve the rest-of-season points projection?

Run from backend/ (needs skater_game_hist and shot_hist): .venv/bin/python -I analysis/backtest_projection_xg.py

For each past season with two earlier seasons on file and each player with 40+ games: take the first N games (10, 25, 40),
predict points per game over the rest of the season, and score each predictor by root-mean-square error.
Compared, all pulled toward the player's earlier record (last two seasons, 2:1 recency, as /api/fantasy/priors does):
  base      points per game as they happened (what the Fantasy page does today)
  xg w      goals replaced by (1 - w) * actual goals + w * expected goals from the player's own shots in the first N
            games, assists as they happened (so the shot-quality signal replaces some of the finishing noise)
  xg2 w     the same, and the earlier seasons' goals are blended with their xG the same way
xG is scaled each season so league xG equals league goals (empty-net and shootout goals excluded from neither side).
"""
from pathlib import Path
import math, sys
from collections import defaultdict

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config

with psycopg.connect(config.DATABASE_URL) as conn:
    games = defaultdict(lambda: defaultdict(list))   # season -> player -> [(game_id, goals, assists)] in date order
    for pid, season, gid, g, a in conn.execute(
            "SELECT player_id, season_id, game_id, goals, assists FROM skater_game_hist ORDER BY player_id, season_id, game_date, game_id"):
        games[season][pid].append((gid, g, a))
    xg = defaultdict(float)                          # (player, game) -> expected goals from the player's own attempts
    for pid, gid, x in conn.execute("""SELECT shooter_id, game_id, sum(xg) FROM shot_hist
                                       WHERE kind IN ('shot', 'miss', 'goal') AND xg IS NOT NULL AND shooter_id IS NOT NULL
                                       GROUP BY shooter_id, game_id"""):
        xg[pid, gid] = float(x)

seasons = sorted(games)
factor = {}
for s in seasons:   # league goals per league xG
    goals = sum(g for lst in games[s].values() for _, g, _ in lst)
    total = sum(xg[p, gid] for p, lst in games[s].items() for gid, _, _ in lst)
    factor[s] = goals / total


def rmse(errors):
    return math.sqrt(sum(e * e for e in errors) / len(errors))


def totals(season, pid, upto=None):
    lst = games[season][pid][:upto]
    n = len(lst)
    g = sum(x[1] for x in lst)
    a = sum(x[2] for x in lst)
    x = sum(xg[pid, x_[0]] for x_ in lst) * factor[season]
    return n, g, a, x


def shrink(total, n, prior, k):
    return (total + k * prior) / (n + k)


K = 40
WS = [0.25, 0.5, 0.75, 1.0]
for early_n in (10, 25, 40):
    errs = defaultdict(list)
    n_players = 0
    for si in range(2, len(seasons)):
        s, s1, s2 = seasons[si], seasons[si - 1], seasons[si - 2]
        for pid, lst in games[s].items():
            if len(lst) < 60 or pid not in games[s1] or pid not in games[s2] or len(games[s1][pid]) < 40 or len(games[s2][pid]) < 40:
                continue
            rest = lst[early_n:]
            target = sum(g + a for _, g, a in rest) / len(rest)
            n, g, a, x = totals(s, pid, early_n)
            # earlier seasons, the more recent counting double
            (n1, g1, a1, x1), (n2, g2, a2, x2) = totals(s1, pid), totals(s2, pid)
            pg = (2 * g1 / n1 + g2 / n2) / 3
            pa = (2 * a1 / n1 + a2 / n2) / 3
            px = (2 * x1 / n1 + x2 / n2) / 3
            errs["base"].append(shrink(g + a, n, pg + pa, K) - target)
            for w in WS:
                goals = (1 - w) * g + w * x
                errs[f"xg {w}"].append(shrink(goals, n, pg, K) + shrink(a, n, pa, K) - target)
                pgw = (1 - w) * pg + w * px
                errs[f"xg2 {w}"].append(shrink(goals, n, pgw, K) + shrink(a, n, pa, K) - target)
            n_players += 1
    base = rmse(errs["base"])
    print(f"\n=== first {early_n} games ({n_players} players)")
    for name, e in errs.items():
        print(f"{name:10s} rmse {rmse(e):.4f}  ({(rmse(e) / base - 1) * 100:+.1f}% vs base)")
