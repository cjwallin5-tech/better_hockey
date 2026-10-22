"""Analysis: do travel distance and time-zone changes cost a team goals, beyond rest and home ice?

Run from backend/ (needs team_game_hist with is_home): .venv/bin/python -I analysis/travel_effects.py

One regression over every stored team-game: the team's goal difference on team and opponent fixed effects (so strength is
accounted for) plus home ice, the rest situation (second night of a back-to-back against a rested team and its mirror),
kilometres travelled (in thousands, own and opponent's), time zones crossed eastward and westward, and a third straight road game.
Standard errors are the plain least-squares ones, so read anything near 2 standard errors as a hint, not a result.
"""
from pathlib import Path
import sys
import numpy as np
import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config, fatigue

with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
    rows = conn.execute("""SELECT CASE WHEN team = 'ARI' THEN 'UTA' ELSE team END AS team,
                                  CASE WHEN opponent = 'ARI' THEN 'UTA' ELSE opponent END AS opponent,
                                  season_id, game_id, game_date, goals_for, goals_against, points, wins, is_home
                           FROM team_game_hist WHERE team IS NOT NULL AND opponent IS NOT NULL AND is_home IS NOT NULL""").fetchall()
rest = fatigue.rest_days(rows)
trav = fatigue.travel(rows)
teams = sorted({r["team"] for r in rows})
idx = {t: i for i, t in enumerate(teams)}
X, y = [], []
names = ["home", "tired", "rested vs tired", "both tired", "own km (1000s)", "opp km (1000s)", "east zones", "west zones", "3rd+ road game"]
for r in rows:
    me, op = trav[r["team"], r["game_id"]], trav.get((r["opponent"], r["game_id"]))
    if op is None: continue
    k = fatigue.kind(rest[r["team"], r["game_id"]], rest[r["opponent"], r["game_id"]])
    f = [r["is_home"], k == "tired", k == "edge", k == "both", me["km"] / 1000, op["km"] / 1000,
         max(me["hours_east"], 0), max(-me["hours_east"], 0), me["road_game"] >= 3]
    own = [0] * len(teams); own[idx[r["team"]]] = 1
    opp = [0] * len(teams); opp[idx[r["opponent"]]] = -1
    X.append(f + own + opp); y.append(r["goals_for"] - r["goals_against"])
X, y = np.array(X, float), np.array(y, float)
coef, *_ = np.linalg.lstsq(X, y, rcond=None)
resid = y - X @ coef
dof = len(y) - np.linalg.matrix_rank(X)
cov = np.linalg.pinv(X.T @ X) * (resid @ resid / dof)
print(f"{len(y)} team-games")
for i, name in enumerate(names):
    print(f"{name:18s} {coef[i]:+.3f} goals  (se {np.sqrt(cov[i, i]):.3f})")
