"""Goalie weakness map: where on the ice a goalie gives up more (or fewer) goals than the shots' quality predicts.

Every non-empty-net shot on goal is put in one of nine zones: three ranges from the net (close, mid, long) by three
lanes (glove side, middle, blocker side). Lanes follow the shooter's angle to the net: within MIDDLE_ANGLE degrees of
straight on is the middle, and wider shots go to the side they come from. Which side is the glove side depends on the
hand the goalie catches with; NHL rink coordinates have the shooter's left at positive y, so a goalie who catches with
the left hand has the glove toward negative y.

Each zone reports shots, goals, expected goals, goals saved above expected (GSAx = expected - goals) and a z-score for
how unusual the gap is. Expected goals start from the model's xG scaled to the league's goal total (see
luck_db.goalie_factor), then are scaled again so that the league as a whole sits at zero in that same zone, shot type
or situation: the xG model is a little off by location (it over-predicts goals from the slot and under-predicts from
the sides), and without this a goalie would look good or bad in a zone only because of the model. So the figures
read "goals fewer or more than an average goalie allows on similar shots from the same spot".
The NHL feed has no shot height or net location, so "glove side" means the side of the ice the shot came from, not
where in the net it went. A season of one goalie's shots is a small sample: a zone holds a few dozen shots, so only
large gaps are flagged (|z| >= FLAG_Z).
"""
import math

CLOSE_FT, MID_FT = 15, 35        # zone range edges, feet from the net
MIDDLE_ANGLE = 15                # degrees either side of straight on that count as the middle lane
FLAG_Z = 2.0
MIN_ZONE_SHOTS = 15              # below this a zone is shown but not graded
RANGES = ("close", "mid", "long")
LANES = ("glove", "middle", "blocker")


def zone(shot, catches):
    """(range, lane) for a shot row with distance, angle and y, or None when its location is unknown."""
    d, a, y = shot.get("distance"), shot.get("angle"), shot.get("y")
    if d is None or a is None or y is None:
        return None
    rng = "close" if d < CLOSE_FT else "mid" if d < MID_FT else "long"
    if abs(a) <= MIDDLE_ANGLE:
        return rng, "middle"
    glove_y_sign = 1 if catches == "R" else -1   # an unknown hand is treated as the common left catch
    return rng, "glove" if (y > 0) == (glove_y_sign > 0) else "blocker"


def usable(shots):
    """Shots on goal with a modelled xG and a goalie in net."""
    return [s for s in shots if s["kind"] in ("shot", "goal") and not s.get("empty_net") and s.get("xg") is not None]


SITUATION = {"ev": "Even strength", "pp": "Against the power play", "sh": "Against the penalty kill"}


def groups_of(shot, catches):
    """The (kind, label...) keys a shot counts toward: its zone, its shot type, and its situations."""
    keys = []
    z = zone(shot, catches)
    if z:
        keys.append(("zone", *z))
    if shot.get("shot_type"):
        keys.append(("type", shot["shot_type"]))
    keys.append(("sit", "Rebounds" if shot.get("rebound") else "First shots"))
    if SITUATION.get(shot.get("strength")):
        keys.append(("sit", SITUATION[shot["strength"]]))
    return keys


def prob(shot, factor):
    """One shot's calibrated chance of beating the goalie. A row can carry its own season's factor as `f`."""
    return min(0.99, shot["xg"] * shot.get("f", factor))


def league_calibration(shots, factor):
    """Per-group scale factors from every goalie's shots (each row also carries `catches`): the league's goals in
    the group divided by its expected goals, so the league sits at zero in each group."""
    goals, expected = {}, {}
    for s in usable(shots):
        for k in groups_of(s, s.get("catches")):
            goals[k] = goals.get(k, 0) + (s["kind"] == "goal")
            expected[k] = expected.get(k, 0) + prob(s, factor)
    return {k: goals[k] / expected[k] for k in expected if expected[k] > 0 and goals[k] > 0}


def tally(shots, factor, group_factor=1.0):
    """Totals for a group of shots (rows with kind, xg): faced, goals, xg, gsax, expected save %, save %, z."""
    n = len(shots)
    goals = sum(1 for s in shots if s["kind"] == "goal")
    ps = [min(0.99, prob(s, factor) * group_factor) for s in shots]
    xg = sum(ps)
    var = sum(p * (1 - p) for p in ps)
    return {
        "shots": n, "goals": goals, "xg": round(xg, 2), "gsax": round(xg - goals, 2),
        "sv_pct": round(1 - goals / n, 4) if n else None,
        "exp_sv_pct": round(1 - xg / n, 4) if n else None,
        "z": round((xg - goals) / math.sqrt(var), 2) if var > 0 else None,
    }


def summarize(shots, factor, catches=None, calibration=None):
    """The full map from one goalie's shot rows (kind, xg, distance, angle, y, shot_type, rebound, strength).

    Shots that are not on goal, are empty-net, or have no xG are left out (counted in `skipped`). `calibration` is
    league_calibration's result; without it the figures are against the model as it stands.
    """
    calibration = calibration or {}
    use = usable(shots)
    grouped = {}
    for s in use:
        for k in groups_of(s, catches):
            grouped.setdefault(k, []).append(s)

    def t(key):
        return tally(grouped.get(key, []), factor, calibration.get(key, 1.0))

    seasons = sorted({s["season_id"] for s in use if s.get("season_id")})

    def by_season(key):
        """{season_id: GSAx} for the group, so a repeat weakness can be told from a one-year blip."""
        out = {}
        for sid in seasons:
            rows = [s for s in grouped.get(key, []) if s.get("season_id") == sid]
            if rows:
                out[sid] = tally(rows, factor, calibration.get(key, 1.0))["gsax"]
        return out

    zones = []
    for rng in RANGES:
        for lane in LANES:
            r = t(("zone", rng, lane))
            r["by_season"] = by_season(("zone", rng, lane))
            r.update(range=rng, lane=lane, graded=r["shots"] >= MIN_ZONE_SHOTS,
                     flag=(r["z"] is not None and r["shots"] >= MIN_ZONE_SHOTS and abs(r["z"]) >= FLAG_Z))
            zones.append(r)

    def rows(kind, labels=None):
        keys = [k for k in grouped if k[0] == kind and (labels is None or k[1] in labels)]
        return sorted(({"label": k[1], **t(k)} for k in keys), key=lambda r: -r["shots"])

    return {
        "total": tally(use, factor),
        "seasons": seasons,
        "zones": zones,
        "shot_types": [r for r in rows("type") if r["shots"] >= 5],
        "situations": rows("sit", ("First shots", "Rebounds")) + rows("sit", tuple(SITUATION.values())),
        "skipped": sum(1 for s in shots if s["kind"] in ("shot", "goal")) - len(use),
    }


def headline(summary, min_shots=20):
    """Plain-language read: the weakest and strongest graded zones, or None when no zone has enough shots."""
    graded = [z for z in summary["zones"] if z["shots"] >= min_shots]
    if not graded:
        return None
    worst, best = min(graded, key=lambda z: z["gsax"]), max(graded, key=lambda z: z["gsax"])
    return {"worst": {k: worst[k] for k in ("range", "lane", "shots", "gsax", "z")},
            "best": {k: best[k] for k in ("range", "lane", "shots", "gsax", "z")}}
