"""Backtest: how well do early-season team ratings predict goals against in the rest of the season?

Run from backend/ (needs shot_hist, so run `ingest.py backfill-shots` first): .venv/bin/python -I analysis/backtest_team_ratings.py

Predictors of a team's rest-of-season goals against per game, from its first N games (10 and 25): goals against, or expected
goals against (xGA, from the stored shots), each pulled toward the league average or toward last season's figure with a prior
weight of k games. Findings behind backend/matchups.py: raw early goals against is worse than just using the league average
(error 0.62 against 0.35 at 10 games), while xGA pulled toward the league average by about 20 games' worth cuts the error about
10% (0.31). Pulling toward last season's rating did not clearly help.
"""
import math
from pathlib import Path
import sys
from collections import defaultdict

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config

with psycopg.connect(config.DATABASE_URL) as conn:
    # per team-game goals for / against
    tg = defaultdict(list)      # (season, team) -> [(date, game_id, ga, gf)]
    for team, season, gid, date, gf, ga in conn.execute(
            "SELECT team, season_id, game_id, game_date, goals_for, goals_against FROM team_game_hist WHERE team IS NOT NULL ORDER BY game_date, game_id"):
        tg[(season, team)].append((date, gid, ga, gf))
    # expected goals for by shooting team in each game (shooter's team from the on-ice table)
    xgf = {}
    for gid, team, xg in conn.execute(
            """SELECT s.game_id, o.team, sum(s.xg) FROM shot_hist s JOIN skater_game_onice o
                 ON o.player_id = s.shooter_id AND o.game_id = s.game_id
               WHERE s.xg IS NOT NULL AND o.team IS NOT NULL GROUP BY 1, 2"""):
        xgf[(gid, team)] = float(xg)
    # opponent in each team-game, to turn the opponent's xGF into this team's xGA
    opp = {}
    for team, gid, o in conn.execute("SELECT team, game_id, opponent FROM team_game_hist WHERE team IS NOT NULL"):
        opp[(team, gid)] = o

seasons = sorted({s for s, _ in tg})


def rmse(errors):
    return math.sqrt(sum(e * e for e in errors) / len(errors))


def season_means(season):
    """league average goals against and xGA per game, and each team's full-season figures (for last-season priors)"""
    ga_tot = n = 0
    xga_tot = nx = 0
    per_team = {}
    for (s, team), games in tg.items():
        if s != season:
            continue
        ga = sum(g[2] for g in games) / len(games)
        xs = [xgf.get((gid, opp.get((team, gid)))) for _, gid, _, _ in games]
        xs = [x for x in xs if x is not None]
        per_team[team] = (ga, sum(xs) / len(xs) if xs else None)
        ga_tot += sum(g[2] for g in games); n += len(games)
        xga_tot += sum(xs); nx += len(xs)
    return ga_tot / n, xga_tot / nx if nx else None, per_team


ks = [0, 5, 10, 20, 40, 80]
for early_n in (10, 25):
    res = defaultdict(list)
    for si in range(1, len(seasons)):
        s, prev = seasons[si], seasons[si - 1]
        lg_ga, lg_xga, _ = season_means(s)
        _, _, prev_team = season_means(prev)
        for (season, team), games in tg.items():
            if season != s or len(games) < early_n + 20:
                continue
            early, rest = games[:early_n], games[early_n:]
            target = sum(g[2] for g in rest) / len(rest)
            e_ga = sum(g[2] for g in early) / early_n
            xs = [xgf.get((gid, opp.get((team, gid)))) for _, gid, _, _ in early]
            xs = [x for x in xs if x is not None]
            e_xga = sum(xs) / len(xs) if xs else None
            res["league avg only"].append(lg_ga - target)
            for k in ks:
                res[f"GA shrunk to league k={k}"].append((e_ga * early_n + k * lg_ga) / (early_n + k) - target)
                if e_xga is not None:
                    # xGA is on the same goals scale league-wide, but put it on the goals scale explicitly
                    scale = lg_ga / lg_xga
                    res[f"xGA shrunk to league k={k}"].append((e_xga * scale * early_n + k * lg_ga) / (early_n + k) - target)
                if team in prev_team and prev_team[team][1] is not None:
                    pga, pxga = prev_team[team]
                    prior = 0.5 * pga + 0.5 * pxga * (season_means(prev)[0] / season_means(prev)[1])
                    res[f"xGA shrunk to last season k={k}"].append((e_xga * scale * early_n + k * prior) / (early_n + k) - target)
            if team in prev_team:
                res["last season's GA alone"].append(prev_team[team][0] - target)
    print(f"\n=== first {early_n} games -> rest of season ({len(res['league avg only'])} team-seasons)")
    for name in ("league avg only", "last season's GA alone"):
        print(f"{name:34s} rmse {rmse(res[name]):.4f}")
    for kind in ("GA shrunk to league", "xGA shrunk to league", "xGA shrunk to last season"):
        print(f"{kind:34s} " + "  ".join(f"k={k}: {rmse(res[f'{kind} k={k}']):.4f}" for k in ks if res[f"{kind} k={k}"]))
