"""Backtest: does a player's last TWO seasons predict better than the last one, and with what weight?

Run from backend/: .venv/bin/python -I analysis/backtest_player_prior_two_seasons.py

Predicts points per game for the rest of a season from the first N games (10 and 25) pulled toward the player's earlier record:
last season only, the last two seasons by games, or the last two with the recent one counting double (2:1). The 2:1 version with a
prior weight of about 40 games was best (error 0.143 against 0.150 for one season), which is what /api/fantasy/priors serves.
"""
from pathlib import Path
import math, sys
from collections import defaultdict
import psycopg
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config
with psycopg.connect(config.DATABASE_URL) as conn:
    games = defaultdict(lambda: defaultdict(list))
    for pid, season, pts in conn.execute("SELECT player_id, season_id, points FROM skater_game_hist ORDER BY player_id, season_id, game_date, game_id"):
        games[season][pid].append(pts)
seasons = sorted(games)
def rmse(e): return math.sqrt(sum(x*x for x in e)/len(e))
ks=[10,20,30,40,60]
for early_n in (10, 25):
    one, two = defaultdict(list), defaultdict(list); n=0
    for si in range(2, len(seasons)):          # need two earlier seasons
        s=seasons[si]; p1=games[seasons[si-1]]; p2=games[seasons[si-2]]
        for pid, pts in games[s].items():
            if len(pts)<40 or pid not in p1 or pid not in p2 or len(p1[pid])<40 or len(p2[pid])<40: continue
            early, rest = pts[:early_n], pts[early_n:]
            target=sum(rest)/len(rest)
            last1=sum(p1[pid])/len(p1[pid])
            last2=(sum(p1[pid])+sum(p2[pid]))/(len(p1[pid])+len(p2[pid]))
            # recency weighting: 2:1
            w=(2*sum(p1[pid])/len(p1[pid]) + sum(p2[pid])/len(p2[pid]))/3
            for k in ks:
                one[k].append((sum(early)+k*last1)/(early_n+k)-target)
                two[k].append((sum(early)+k*last2)/(early_n+k)-target)
                two[('w',k)].append((sum(early)+k*w)/(early_n+k)-target)
            n+=1
    print(f"\n=== first {early_n} games ({n} players with two prior seasons)")
    print("prior = last season:            " + "  ".join(f"k={k}: {rmse(one[k]):.4f}" for k in ks))
    print("prior = last two (by games):    " + "  ".join(f"k={k}: {rmse(two[k]):.4f}" for k in ks))
    print("prior = last two (2:1 recency): " + "  ".join(f"k={k}: {rmse(two[('w',k)]):.4f}" for k in ks))
