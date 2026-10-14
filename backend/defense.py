"""Defensive-style profile: hits, blocks, takeaways and giveaways per 60 minutes, against the league.

The NHL only counts these from 2005-06, and how they are counted has drifted (league hits per game
are up about 40% since then), so raw rates can't be compared across seasons. Each rate is shown as:
- index: the player's rate divided by the league rate that season for the same role (forwards or
  defensemen); 1.0 is average, 1.5 is 50% above.
- percentile: the share of same-role skaters (MIN_GP+ games) with a lower rate that season.
Net takeaways (takeaways minus giveaways) can be negative, so it is shown as a difference from the
league's rate instead of a ratio. Hits and blocks describe style, not quality, and giveaways are bad, so nothing here is a rating.
"""
from bisect import bisect_left
from collections import defaultdict

MIN_GP = 20
STATS = ("hits", "blocks", "takeaways", "giveaways", "net_takeaways")
RATIO_STATS = STATS[:-1]  # net_takeaways has no meaningful ratio


def role(position):
    return "D" if position == "D" else "F"


def minutes(row):
    return row["games_played"] * (row["toi_per_game_sec"] or 0) / 60


def counts(row):
    return {"hits": row["hits"], "blocks": row["blocked_shots"], "takeaways": row["takeaways"],
            "giveaways": row["giveaways"], "net_takeaways": row["takeaways"] - row["giveaways"]}


def build(rows):
    """League context from every skater-season: per-60 baselines and sorted peer rates."""
    totals = defaultdict(lambda: defaultdict(float))
    peers = defaultdict(list)
    for r in rows:
        m = minutes(r)
        if r["games_played"] < MIN_GP or m <= 0:
            continue
        key = (r["season_id"], role(r["position"]))
        totals[key]["minutes"] += m
        for stat, v in counts(r).items():
            totals[key][stat] += v
            peers[key, stat].append(v / m * 60)
    base = {key: {s: t[s] / t["minutes"] * 60 for s in STATS} for key, t in totals.items()}
    for v in peers.values():
        v.sort()
    return {"base": base, "peers": peers}


def season_profile(row, ctx):
    """{stat: {rate, index, percentile}} for one skater-season, or None without ice time."""
    m, key = minutes(row), (row["season_id"], role(row["position"]))
    if m <= 0 or key not in ctx["base"]:
        return None
    out = {}
    for stat, v in counts(row).items():
        rate, league = v / m * 60, ctx["base"][key][stat]
        peers = ctx["peers"][key, stat]
        out[stat] = {"rate": round(rate, 2), "diff": round(rate - league, 2),
                     "index": round(rate / league, 2) if stat in RATIO_STATS and league > 0 else None,
                     "percentile": round(100 * bisect_left(peers, rate) / len(peers)) if peers else None}
    return out


def career_profile(rows, ctx):
    """Index over several seasons: actual counts against what an average same-role skater would have
    had in the same minutes of the same seasons."""
    actual, expected, mins = defaultdict(float), defaultdict(float), 0.0
    for r in rows:
        m, key = minutes(r), (r["season_id"], role(r["position"]))
        if m <= 0 or key not in ctx["base"]:
            continue
        mins += m
        for stat, v in counts(r).items():
            actual[stat] += v
            expected[stat] += ctx["base"][key][stat] * m / 60
    if mins <= 0:
        return None
    return {stat: {"rate": round(actual[stat] / mins * 60, 2),
                   "diff": round((actual[stat] - expected[stat]) / mins * 60, 2),
                   "index": round(actual[stat] / expected[stat], 2) if stat in RATIO_STATS and expected[stat] > 0 else None}
            for stat in STATS}


# --- On-ice impact (5v5 expected goals against), from the shift-chart data ------------------------
# Hits and blocks say how a player plays; on-ice xGA says what happens around him. Raw xGA/60 mostly
# reflects the team, so the main figure is relative: the team's xGA/60 with the player on the ice minus
# with him off it (in the same games). Negative is good. It still carries linemates, zone starts and
# opponents, so it is a clue, not a verdict.
ONICE_MIN_SEC = 300 * 60   # 5v5 time before a season counts toward percentiles
OFF_MIN_SEC = 600          # off-ice time needed for the "relative" figure to mean anything


def onice_metrics(r):
    """r: summed on-ice and team totals for one player-season (seconds and expected goals)."""
    per60 = lambda x, t: x / t * 3600 if t > 0 else None
    off_toi = r["t_toi"] - r["on_toi"]
    xga60 = per60(r["on_xga"], r["on_toi"])
    off_xga60 = per60(r["t_xga"] - r["on_xga"], off_toi) if off_toi >= OFF_MIN_SEC else None
    xgf, xga = r["on_xgf"], r["on_xga"]
    cf, ca = r["on_cf"], r["on_ca"]
    return {
        "toi_min": round(r["on_toi"] / 60), "xga60": round(xga60, 2) if xga60 is not None else None,
        "rel_xga60": round(xga60 - off_xga60, 2) if xga60 is not None and off_xga60 is not None else None,
        "xgf_pct": round(xgf / (xgf + xga), 3) if xgf + xga > 0 else None,
        "cf_pct": round(cf / (cf + ca), 3) if cf + ca > 0 else None,
    }


def build_onice(rows):
    """{(player_id, season_id): metrics}, with percentiles (higher is better) among same-role skaters."""
    out, peers = {}, defaultdict(list)
    for r in rows:
        m = onice_metrics(r)
        out[r["player_id"], r["season_id"]] = (role(r["position"]), m)
        if r["on_toi"] >= ONICE_MIN_SEC:
            for k in ("xga60", "rel_xga60"):
                if m[k] is not None:
                    peers[r["season_id"], role(r["position"]), k].append(m[k])
    result = {}
    for key, (rl, m) in out.items():
        m = dict(m)
        for k in ("xga60", "rel_xga60"):
            pool = peers.get((key[1], rl, k))
            if m[k] is not None and pool and m["toi_min"] * 60 >= ONICE_MIN_SEC:
                m[k + "_pct"] = round(100 * sum(1 for v in pool if v > m[k]) / len(pool))  # share of peers allowing more
        result[key] = m
    return result


def onice_career(rows):
    """Pooled on-ice metrics over several seasons of one player (sums, not an average of rates)."""
    keys = ("on_toi", "on_xgf", "on_xga", "on_cf", "on_ca", "t_toi", "t_xgf", "t_xga")
    total = {k: sum(r[k] or 0 for r in rows) for k in keys}
    return onice_metrics(total) if total["on_toi"] > 0 else None
