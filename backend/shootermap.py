"""Shooter zone map: where a skater shoots from, and where he scores more or fewer goals than the chances predict.

Uses the same nine zones as the goalie map (goaliemap.py): three ranges from the net (close, mid, long) by three lanes,
here left, middle and right as the shooter sees the net (positive rink y is the shooter's left, checked against left- and
right-shot defensemen). Every unblocked attempt with an expected-goal value counts (shots on goal, misses and goals,
all strengths, empty-net attempts left out), because the model's xG already includes the chance of missing the net.

Two things come out per zone: the share of his attempts taken there next to the league's share (his shot diet), and his
goals above expected there, goals minus xG (positive is good, the opposite sign to a goalie's GSAx). Expected goals are
scaled so the league sits at zero in each zone, shot type and situation (the xG model is a little off by location, and
without this a shooter would look good or bad in a zone because of the model), after each season's xG is scaled to that
season's goals. So the figures read "goals more or fewer than an average shooter scores from similar shots in the same
spot". A zone holds a few dozen of one player's attempts, so only gaps of about two standard deviations are flagged.
"""
import math

import goaliemap as gm

RANGES = gm.RANGES
LANES = ("left", "middle", "right")
FLAG_Z = gm.FLAG_Z
MIN_ZONE_ATTEMPTS = 15
SITUATION = {"ev": "Even strength", "pp": "Power play", "sh": "Short-handed"}


def zone(shot):
    """(range, lane) for a row with distance, angle and y, or None when its location is unknown."""
    d, a, y = shot.get("distance"), shot.get("angle"), shot.get("y")
    if d is None or a is None or y is None:
        return None
    rng = "close" if d < gm.CLOSE_FT else "mid" if d < gm.MID_FT else "long"
    if abs(a) <= gm.MIDDLE_ANGLE:
        return rng, "middle"
    return rng, "left" if y > 0 else "right"


def usable(shots):
    """Unblocked attempts with an expected-goal value and a goalie to beat."""
    return [s for s in shots if s["kind"] in ("shot", "miss", "goal") and not s.get("empty_net") and s.get("xg") is not None]


def groups_of(shot):
    keys = []
    z = zone(shot)
    if z:
        keys.append(("zone", *z))
    if shot.get("shot_type"):
        keys.append(("type", shot["shot_type"]))
    keys.append(("sit", "Rebounds" if shot.get("rebound") else "First shots"))
    if SITUATION.get(shot.get("strength")):
        keys.append(("sit", SITUATION[shot["strength"]]))
    return keys


def prob(shot):
    """One attempt's calibrated chance of being a goal. A row carries its season's scale as `f`."""
    return min(0.99, shot["xg"] * shot.get("f", 1.0))


def season_factors(shots):
    """{season_id: goals / xG} over every shooter's attempts, so a season where the model runs high or low washes out."""
    goals, xg = {}, {}
    for s in usable(shots):
        sid = s["season_id"]
        goals[sid] = goals.get(sid, 0) + (s["kind"] == "goal")
        xg[sid] = xg.get(sid, 0.0) + s["xg"]
    return {sid: goals[sid] / xg[sid] for sid in xg if xg[sid] > 0 and goals[sid] > 0}


def league_profile(shots):
    """From every shooter's attempts (each carrying `f`): per-group calibration factors (goals / expected, so the league sits
    at zero) and per-zone shares of all attempts."""
    use = usable(shots)
    goals, expected, zones = {}, {}, {}
    for s in use:
        for k in groups_of(s):
            goals[k] = goals.get(k, 0) + (s["kind"] == "goal")
            expected[k] = expected.get(k, 0.0) + prob(s)
        z = zone(s)
        if z:
            zones[z] = zones.get(z, 0) + 1
    total = sum(zones.values()) or 1
    return ({k: goals[k] / expected[k] for k in expected if expected[k] > 0 and goals[k] > 0},
            {z: n / total for z, n in zones.items()})


def tally(shots, group_factor=1.0):
    """Attempts, goals, expected goals, goals above expected and a z-score for one group of a player's attempts."""
    ps = [min(0.99, prob(s) * group_factor) for s in shots]
    goals = sum(1 for s in shots if s["kind"] == "goal")
    xg = sum(ps)
    var = sum(p * (1 - p) for p in ps)
    return {"attempts": len(shots), "on_goal": sum(1 for s in shots if s["kind"] in ("shot", "goal")), "goals": goals,
            "xg": round(xg, 2), "gsax": round(goals - xg, 2),
            "z": round((goals - xg) / math.sqrt(var), 2) if var > 0 else None}


def summarize(shots, calibration=None, league_shares=None):
    """The player's map from his attempt rows (kind, xg, f, distance, angle, y, shot_type, rebound, strength, empty_net,
    season_id) and the league profile. Returns zones (with share, league share and a result per season), shot types
    and situations."""
    calibration, league_shares = calibration or {}, league_shares or {}
    use = usable(shots)
    grouped = {}
    for s in use:
        for k in groups_of(s):
            grouped.setdefault(k, []).append(s)
    in_zones = sum(len(v) for k, v in grouped.items() if k[0] == "zone") or 1
    seasons = sorted({s["season_id"] for s in use if s.get("season_id")})

    def t(key):
        return tally(grouped.get(key, []), calibration.get(key, 1.0))

    def by_season(key):
        out = {}
        for sid in seasons:
            rows = [s for s in grouped.get(key, []) if s.get("season_id") == sid]
            if rows:
                out[sid] = tally(rows, calibration.get(key, 1.0))["gsax"]
        return out

    zones = []
    for rng in RANGES:
        for lane in LANES:
            r = t(("zone", rng, lane))
            r.update(range=rng, lane=lane, share=round(r["attempts"] / in_zones, 4),
                     league_share=round(league_shares.get((rng, lane), 0.0), 4),
                     graded=r["attempts"] >= MIN_ZONE_ATTEMPTS, by_season=by_season(("zone", rng, lane)))
            r["flag"] = r["graded"] and r["z"] is not None and abs(r["z"]) >= FLAG_Z
            zones.append(r)

    def rows(kind, labels=None):
        keys = [k for k in grouped if k[0] == kind and (labels is None or k[1] in labels)]
        return sorted(({"label": k[1], **t(k)} for k in keys), key=lambda r: -r["attempts"])

    return {
        "total": tally(use),
        "seasons": seasons,
        "zones": zones,
        "shot_types": [r for r in rows("type") if r["attempts"] >= 10],
        "situations": rows("sit", ("First shots", "Rebounds")) + rows("sit", tuple(SITUATION.values())),
    }


def headline(summary, min_attempts=20):
    """The zone he finishes best and worst in (with enough attempts), and the zone he favours most against the league."""
    graded = [z for z in summary["zones"] if z["attempts"] >= min_attempts]
    if not graded:
        return None
    pick = lambda z: {k: z[k] for k in ("range", "lane", "attempts", "gsax", "z", "share", "league_share")}
    favours = max(graded, key=lambda z: z["share"] - z["league_share"])
    return {"best": pick(max(graded, key=lambda z: z["gsax"])), "worst": pick(min(graded, key=lambda z: z["gsax"])),
            "favours": pick(favours)}
