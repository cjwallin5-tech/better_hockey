"""Analysis: do teams and goalies do worse on the second night of a back-to-back?

Run from backend/ (needs team_game_hist, shot_hist and skater_game_onice): .venv/bin/python -I analysis/back_to_back_effects.py

Teams: every regular-season game in team_game_hist gets its rest (days since the team's previous game: 1 = played
yesterday). A team's results on the second night of a back-to-back are compared with the SAME team's other games,
so a strong team isn't mistaken for a rested one. The league figure is the average of those within-team gaps.
Goalies: the same idea with save percentage and goals saved above expected, for a goalie who also played the night before.
"""
from pathlib import Path
import math, sys
from collections import defaultdict
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config

with psycopg.connect(config.DATABASE_URL) as conn:
    team_rows = conn.execute("""SELECT team, season_id, game_id, game_date, points, wins, goals_for, goals_against, opponent
                                FROM team_game_hist WHERE team IS NOT NULL ORDER BY team, season_id, game_date""").fetchall()
print("team games:", len(team_rows))

by_team = defaultdict(list)
for team, season, gid, d, pts, wins, gf, ga, opp in team_rows:
    by_team[team, season].append((d, gid, pts, wins, gf, ga, opp))
rest_of = {}   # (team, game_id) -> days of rest
for (team, season), games in by_team.items():
    prev = None
    for d, gid, *_ in games:
        rest_of[team, gid] = (d - prev).days if prev else 9
        prev = d

def mean(x): return sum(x) / len(x) if x else float("nan")
def se(x): 
    if len(x) < 2: return float("nan")
    m = mean(x); return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1) / len(x))

def summarize(label, pred_a, pred_b, min_each=5):
    """Average within-team gap (a minus b) in points per game, goal difference and win rate."""
    gaps = defaultdict(list)
    per_team = defaultdict(lambda: ([], []))
    for team, season, gid, d, pts, wins, gf, ga, opp in team_rows:
        if (team, gid) not in rest_of: continue
        r, ro = rest_of[team, gid], rest_of.get((opp, gid), 9)
        side = 0 if pred_a(r, ro) else 1 if pred_b(r, ro) else None
        if side is None: continue
        per_team[team][side].append((pts, gf - ga, wins))
    for team, (a, b) in per_team.items():
        if len(a) < min_each or len(b) < min_each: continue
        for i, name in enumerate(("points", "goal diff", "win")):
            gaps[name].append(mean([x[i] for x in a]) - mean([x[i] for x in b]))
    n_a = sum(len(v[0]) for v in per_team.values())
    print(f"\n{label}: {n_a} games, {len(per_team)} teams")
    for name, g in gaps.items():
        print(f"  {name:10s} per game: {mean(g):+.3f}  (se {se(g):.3f}, {len(g)} teams)")

summarize("second night of a back-to-back (opponent rested) vs other games", lambda r, ro: r == 1 and ro > 1, lambda r, ro: r > 1 and ro > 1)
summarize("second night of a back-to-back (opponent also on one) vs other games", lambda r, ro: r == 1 and ro == 1, lambda r, ro: r > 1 and ro > 1)
summarize("rested (2+ days) while opponent is on a back-to-back vs other games", lambda r, ro: r > 1 and ro == 1, lambda r, ro: r > 1 and ro > 1)
summarize("3+ days of rest vs 1 day of rest", lambda r, ro: 3 <= r < 9, lambda r, ro: r == 2)

# goalies: shots faced and goals allowed per goalie-game from stored shots
with psycopg.connect(config.DATABASE_URL) as conn:
    goalie_rows = conn.execute("""
        WITH cal AS (SELECT season_id, count(*) FILTER (WHERE kind='goal' AND xg IS NOT NULL)::float / sum(xg) AS f
                     FROM shot_hist WHERE goalie_id IS NOT NULL AND kind IN ('shot','goal') GROUP BY season_id)
        SELECT s.goalie_id, s.season_id, s.game_id, t.game_date, o.team,
               count(*) FILTER (WHERE s.kind IN ('shot','goal')) AS sa, count(*) FILTER (WHERE s.kind='goal') AS ga,
               sum(least(0.99, s.xg * c.f)) FILTER (WHERE s.kind IN ('shot','goal')) AS xga
        FROM shot_hist s JOIN cal c USING (season_id)
        JOIN (SELECT DISTINCT player_id, game_id, team FROM skater_game_onice) o ON o.player_id = s.shooter_id AND o.game_id = s.game_id
        JOIN team_game_hist t ON t.game_id = s.game_id AND t.team = o.team
        WHERE s.goalie_id IS NOT NULL
        GROUP BY s.goalie_id, s.season_id, s.game_id, t.game_date, o.team""").fetchall()
games_of = defaultdict(list)
for gid_, season, game, d, opp, sa, ga, xga in goalie_rows:
    games_of[gid_, season].append((d, sa, ga, float(xga or 0)))
b2b, other = defaultdict(lambda: [0, 0, 0.0, 0]), defaultdict(lambda: [0, 0, 0.0, 0])
for (goalie, season), games in games_of.items():
    games.sort()
    prev = None
    for d, sa, ga, xga in games:
        slot = (b2b if prev is not None and (d - prev).days == 1 else other)[goalie]
        slot[0] += sa; slot[1] += ga; slot[2] += xga; slot[3] += 1
        prev = d
gaps_sv, gaps_gsax, n_b = [], [], 0
for goalie in b2b:
    a, o = b2b[goalie], other[goalie]
    if a[3] < 4 or o[3] < 15: continue
    gaps_sv.append(((a[0] - a[1]) / a[0]) - ((o[0] - o[1]) / o[0]))
    gaps_gsax.append((a[2] - a[1]) / a[0] * 100 - (o[2] - o[1]) / o[0] * 100)   # goals saved above expected per 100 shots
    n_b += a[3]
print(f"\ngoalies on the second night of a back-to-back (played the night before): {n_b} starts, {len(gaps_sv)} goalies")
print(f"  save % vs their other games: {mean(gaps_sv):+.4f} (se {se(gaps_sv):.4f})")
print(f"  goals saved above expected per 100 shots: {mean(gaps_gsax):+.2f} (se {se(gaps_gsax):.2f})")
