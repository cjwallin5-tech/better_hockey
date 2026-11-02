"""Backtest: does close-and-late finishing repeat from one season to the next?

Run from backend/: .venv/bin/python -I analysis/backtest_clutch.py        (needs ingest.py backfill-shot-times for the past seasons)

A skater's clutch score in a season is the z-score of his goals on close-and-late attempts (third period, within one goal either way,
all strengths) against the goals his own finishing everywhere else predicts for those attempts (scorestate.clutch). If clutch is a skill,
a player's score in one season should predict his score in the next. For every pair of consecutive seasons the players with at least
MIN_ATTEMPTS close-and-late attempts in BOTH seasons are compared: the correlation of their two scores. The same is done for finishing
in general (goals minus xG per attempt outside those moments) as a yardstick, since finishing is itself only weakly persistent. Also
reported: the share of player-seasons beyond |z| = 2 (about 4.6% by chance alone).

Writes data/clutch_backtest.json for the player page.

Finding (run on 2026-10-28, 2022-23 to 2025-26, 1,304 player-seasons with 25+ close-and-late attempts):
  - Clutch does not repeat: r = -0.01 across 726 consecutive-season pairs. Finishing in general repeats weakly (r = 0.18, 972 pairs).
  - 7.1% of player-seasons were beyond |z| = 2 against about 4.6% by chance, and the z-scores have a standard deviation of 1.29 rather than 1, so
    the z-score slightly overstates how unusual a gap is (it ignores that the player's own finishing rate is estimated). Read |z| < 2 as nothing.
"""
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import psycopg
from psycopg.rows import dict_row

import config
import scorestate as ss
import scorestate_db as db

MIN_ATTEMPTS = 25


def corr(xs, ys):
    if len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx and sy else None


def main():
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        seasons = [r["season_id"] for r in conn.execute(
            "SELECT season_id FROM shot_hist_game WHERE timed GROUP BY season_id ORDER BY season_id").fetchall()]
        rows = db.all_player_shots(conn, seasons)
    by = defaultdict(list)
    for r in rows:
        r["state"] = ss.state_of(r["diff"])
        by[r["season_id"], r["shooter_id"]].append(r)

    score, finish = {}, {}
    for key, shots in by.items():
        c = ss.clutch(shots)
        n_late = c["close_late"]["attempts"]
        if n_late >= MIN_ATTEMPTS and c["z"] is not None:
            score[key] = c["z"]
        o = c["other"]
        if o["attempts"] >= 100:
            finish[key] = o["gsax"] / o["attempts"]

    def pairs(table):
        xs, ys = [], []
        for (season, pid), v in table.items():
            nxt = next((s for s in seasons if s > season), None)
            if nxt and (nxt, pid) in table and nxt - season == 10001:
                xs.append(v)
                ys.append(table[nxt, pid])
        return xs, ys

    cx, cy = pairs(score)
    fx, fy = pairs(finish)
    zs = list(score.values())
    out = {
        "seasons": seasons, "min_attempts": MIN_ATTEMPTS,
        "player_seasons": len(zs), "pairs": len(cx),
        "r_clutch": None if corr(cx, cy) is None else round(corr(cx, cy), 3),
        "r_finishing": None if corr(fx, fy) is None else round(corr(fx, fy), 3), "pairs_finishing": len(fx),
        "share_beyond_2": round(sum(1 for z in zs if abs(z) >= 2) / len(zs), 3) if zs else None,
        "expected_beyond_2": 0.046,
        "sd_of_z": round(statistics.pstdev(zs), 2) if zs else None,
    }
    path = Path(__file__).resolve().parent.parent / "data" / "clutch_backtest.json"
    path.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
