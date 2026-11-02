"""Backtest: do a goalie's weak zones, seen in earlier seasons, predict the goals he allows later?

Run from backend/: .venv/bin/python -I analysis/backtest_goalie_zones.py        (needs backfill-shot-locations)

For each test season, a goalie's zone record (goaliemap.summarize, nine zones, calibrated against the league in each zone) is built from the
seasons BEFORE it only. For each game he played in the test season, the shots he actually faced are counted by zone and two predictions of the
goals above an average goalie's he allowed are made:
  overall: shots faced x his overall goals-saved-above-expected per shot before the season (shrunk toward zero by K pseudo-shots);
  zone:    the same shots, each priced at that zone's shrunk rate for him.
The question is whether the zone detail adds anything beyond overall skill, so the actual excess (goals minus the calibrated expected goals on those
shots) is regressed on the overall prediction and on (zone - overall). A coefficient near 1 means the prediction is right on average, near 0 means
it carries no signal. Using the shots actually faced (not a forecast of them) isolates the goalie's part from the guess about the opponent. Standard errors are clustered by
goalie-season, since a goalie's games in a season share one prior.

Findings (run on 2026-10-28, test seasons 2023-24 to 2026-27 on earlier seasons only, 7,287 goalie-games, goalies with 500+ prior shots):
  - K = 300 pseudo-shots calibrates best: overall coefficient 0.92 (se 0.24) and zone detail 1.03 (se 0.38). K = 200 gives 0.71 / 0.81 (too little
    shrinkage), K = 500 gives 1.29 / 1.40 (too much). Zone detail is about 2.7 standard errors from zero, so it adds signal beyond a goalie's overall record.
  - By test season the zone-detail coefficient is 1.63, -0.19, 0.69 and 2.53 (se 0.6 to 1.5): noisy, but consistent with 1 on average.
  - Size: the zone detail's standard deviation is about 0.14 goals per game (overall record 0.23), so a typical matchup nudge is about a tenth of a goal.
  - Caveat: a goalie's "zone weakness" may partly be his team's defensive habits (pass types xG does not see), which would still predict goals allowed.
"""
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import psycopg
from psycopg.rows import dict_row

import config
import goaliemap as gm
import luck_db

MIN_PRIOR_SHOTS = 500
KS = (200, 300, 500)


def load():
    sql = """
        SELECT season_id, game_id, goalie_id, kind, xg, distance, angle, y, shot_type, rebound, strength, empty_net
        FROM shot_hist WHERE x IS NOT NULL AND kind IN ('shot', 'goal') AND goalie_id IS NOT NULL
        UNION ALL
        SELECT season_id, game_id, goalie_id, kind, xg, distance, angle, y, shot_type, rebound, strength, empty_net
        FROM shot WHERE x IS NOT NULL AND kind IN ('shot', 'goal') AND goalie_id IS NOT NULL
          AND season_id NOT IN (SELECT season_id FROM shot_hist_game)"""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(sql).fetchall()
        catches = {r["player_id"]: r["catches"] for r in conn.execute(
            "SELECT DISTINCT ON (player_id) player_id, catches FROM goalie_season ORDER BY player_id, season_id DESC").fetchall()}
        factors = {r["season_id"]: r["f"] for r in conn.execute(
            f"WITH {luck_db.GOALIE_CALIBRATION_CTE} SELECT season_id, f FROM gcal").fetchall()}
    for r in rows:
        r["catches"] = catches.get(r["goalie_id"])
        r["f"] = factors.get(r["season_id"], 1.0)
    return rows


def ols(X, y, groups):
    """Coefficients and standard errors clustered by `groups` (a goalie's games in a season share one prior, so they are not independent)."""
    X = np.column_stack([np.ones(len(y)), *X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    inv = np.linalg.inv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    groups = np.asarray(groups)
    for g in np.unique(groups):
        m = groups == g
        score = X[m].T @ resid[m]
        meat += np.outer(score, score)
    se = np.sqrt(np.diag(inv @ meat @ inv))
    return beta, se


def main():
    rows = load()
    cal = gm.league_calibration(rows, 1.0)
    seasons = sorted({r["season_id"] for r in rows})
    by_goalie_season = defaultdict(list)
    for r in rows:
        by_goalie_season[r["goalie_id"], r["season_id"]].append(r)
    print(f"{len(rows)} shots, seasons {seasons}")
    for k in KS:
        xs_over, xs_zone, ys, w, seas, grp = [], [], [], [], [], []
        for test in seasons[1:]:
            prior_seasons = [s for s in seasons if s < test]
            for (gid, sid), shots in by_goalie_season.items():
                if sid != test:
                    continue
                prior = [r for s in prior_seasons for r in by_goalie_season.get((gid, s), [])]
                if len(gm.usable(prior)) < MIN_PRIOR_SHOTS:
                    continue
                catches = shots[0]["catches"]
                prior_map = gm.summarize(prior, 1.0, catches, cal)
                over_rate = prior_map["total"]["gsax"] / (prior_map["total"]["shots"] + k)   # goals saved above average per shot
                rate = {(z["range"], z["lane"]): z["gsax"] / (z["shots"] + k) for z in prior_map["zones"]}
                games = defaultdict(list)
                for r in shots:
                    games[r["game_id"]].append(r)
                for game in games.values():
                    use = gm.usable(game)
                    if len(use) < 10:
                        continue
                    n = defaultdict(int)
                    for r in use:
                        z = gm.zone(r, catches)
                        if z:
                            n[z] += 1
                    actual = -gm.tally(use, 1.0)["gsax"]                      # goals allowed above the calibrated expectation
                    # NOTE: tally() uses the model scaled by f only; re-price with the zone calibration so it is the same yardstick as the prior
                    exp = sum(min(0.99, gm.prob(r, 1.0) * cal.get(("zone", *gm.zone(r, catches)), 1.0)) for r in use if gm.zone(r, catches))
                    goals = sum(1 for r in use if r["kind"] == "goal" and gm.zone(r, catches))
                    actual = goals - exp
                    pred_over = -over_rate * sum(n.values())
                    pred_zone = -sum(c * rate[z] for z, c in n.items())
                    xs_over.append(pred_over); xs_zone.append(pred_zone - pred_over); ys.append(actual); w.append(len(use)); seas.append(test); grp.append((gid, sid))
        if not ys:
            print("no pairs"); return
        ys, xo, xz = np.array(ys), np.array(xs_over), np.array(xs_zone)
        gid_codes = np.unique([str(g) for g in grp], return_inverse=True)[1]
        beta, se = ols([xo, xz], ys, gid_codes)
        print(f"K={k}: {len(ys)} goalie-games | overall coef {beta[1]:.2f} (se {se[1]:.2f}) | zone-detail coef {beta[2]:.2f} (se {se[2]:.2f}) "
              f"| sd of overall pred {xo.std():.3f}, of zone detail {xz.std():.3f} goals per game")
        if k == 300:
            sa = np.array(seas)
            for t in sorted(set(seas)):
                m = sa == t
                b, e = ols([xo[m], xz[m]], ys[m], gid_codes[m])
                print(f"    test season {t}: {m.sum()} goalie-games | overall {b[1]:.2f} (se {e[1]:.2f}) | zone detail {b[2]:.2f} (se {e[2]:.2f})")


if __name__ == "__main__":
    main()
