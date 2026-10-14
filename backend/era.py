"""Era-adjusted scoring: what a player's goals and assists would be at today's scoring level.

Scoring has swung a lot (about 4 goals per team game in the early 1980s, under 3 in the mid-2000s, over
3 now), so raw totals favor some eras. For every season we measure the league's goals and assists per
game for forwards and defensemen separately, then scale each player-season by (today's rate / that
season's rate). Games played are left alone, so only the scoring environment is corrected.

What it does not correct: how many games were played, ice time, power-play share, roster and
expansion effects, or anything else that changed. Treat the results as a fair-fight estimate, not a
ruling.

- League rate: goals (or assists) per game among skaters who played at least MIN_GP_SHARE of the
  busiest skater's games that season (and MIN_GP_FLOOR), so call-ups don't drag it down.
- "Today": the average of the last REFERENCE_SEASONS completed seasons.
- Adjusted points are adjusted goals plus adjusted assists.
"""
from collections import defaultdict

MIN_GP_SHARE = 0.25
MIN_GP_FLOOR = 10
REFERENCE_SEASONS = 5
STATS = ("goals", "assists")


def role(position):
    return "D" if position == "D" else "F"


def league_rates(rows):
    """{(season_id, role): {goals, assists}} per game. rows: dicts with season_id, role, games_played, goals, assists."""
    busiest = defaultdict(int)
    for r in rows:
        busiest[r["season_id"]] = max(busiest[r["season_id"]], r["games_played"])
    gp, tot = defaultdict(int), defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["games_played"] >= max(MIN_GP_FLOOR, MIN_GP_SHARE * busiest[r["season_id"]]):
            key = (r["season_id"], r["role"])
            gp[key] += r["games_played"]
            for s in STATS:
                tot[key][s] += r[s]
    return {key: {s: tot[key][s] / gp[key] for s in STATS} for key in gp if gp[key]}


def reference_rates(rates, last_complete_season):
    """Today's scoring level per role: the mean rate over the last few completed seasons."""
    seasons = [last_complete_season - 10001 * i for i in range(REFERENCE_SEASONS)]
    ref = {}
    for rl in ("F", "D"):
        have = [rates[(s, rl)] for s in seasons if (s, rl) in rates]
        if have:
            ref[rl] = {st: sum(h[st] for h in have) / len(have) for st in STATS}
    return ref


def factors(rates, ref):
    """{(season_id, role): {goals, assists}} multipliers that turn that season's totals into today's terms."""
    return {key: {s: ref[key[1]][s] / v[s] for s in STATS if v[s] > 0}
            for key, v in rates.items() if key[1] in ref}


def adjust_careers(rows, fac):
    """{player_id: {adj_goals, adj_assists, adj_points, adj_points_per_game}} from per-season rows
    (player_id, season_id, role, games_played, goals, assists). Seasons without a factor are skipped."""
    tot = defaultdict(lambda: {"g": 0.0, "a": 0.0, "gp": 0})
    for r in rows:
        f = fac.get((r["season_id"], r["role"]))
        if not f or "goals" not in f or "assists" not in f:
            continue
        t = tot[r["player_id"]]
        t["g"] += r["goals"] * f["goals"]
        t["a"] += r["assists"] * f["assists"]
        t["gp"] += r["games_played"]
    return {pid: {"adj_goals": round(t["g"], 1), "adj_assists": round(t["a"], 1),
                  "adj_points": round(t["g"] + t["a"], 1),
                  "adj_points_per_game": round((t["g"] + t["a"]) / t["gp"], 3) if t["gp"] else None}
            for pid, t in tot.items()}


def load_rows(conn):
    """Every skater-season with the player's role, from the career_season and career_skater tables."""
    cur = conn.execute(
        """SELECT s.player_id, s.season_id, s.games_played, s.goals, s.assists, k.position
           FROM career_season s JOIN career_skater k ON k.player_id = s.player_id AND k.game_type = 2""")
    cols = [d.name for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        r["role"] = role(r["position"])
    return rows
