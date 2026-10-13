"""Shot attempts from play-by-play, with rink coordinates normalized so every team attacks +x.

Used both to train the expected-goals model (train_xg.py) and to store shots at ingest time.
"""
import math

KINDS = {"shot-on-goal": "shot", "missed-shot": "miss", "blocked-shot": "block", "goal": "goal"}
GOAL_X = 89.0  # goal line, in feet from center ice


def _clock(period, mmss):
    m, s = mmss.split(":")
    return (period - 1) * 1200 + int(m) * 60 + int(s)


def extract_shots(pbp):
    """One dict per shot attempt, in game order. Coordinates are None when the feed has none."""
    home_id = pbp["homeTeam"]["id"]
    out, last_by_team = [], {}
    for p in sorted(pbp["plays"], key=lambda p: p.get("sortOrder", 0)):
        kind = KINDS.get(p["typeDescKey"])
        if not kind:
            continue
        per = p["periodDescriptor"]
        if per["number"] > 4 or per["periodType"] == "SO":  # shootouts aren't game play
            continue
        d = p.get("details", {})
        team = d.get("eventOwnerTeamId")
        is_home = team == home_id
        t = _clock(per["number"], p["timeInPeriod"])

        x = y = None
        if d.get("xCoord") is not None and d.get("yCoord") is not None and p.get("homeTeamDefendingSide"):
            attacks_right = (p["homeTeamDefendingSide"] == "left") == is_home
            x, y = (d["xCoord"], d["yCoord"]) if attacks_right else (-d["xCoord"], -d["yCoord"])

        sit = p.get("situationCode") or ""
        strength, empty_net = None, False
        if len(sit) == 4 and sit.isdigit():
            away_g, away_s, home_s, home_g = (int(c) for c in sit)
            own, opp = (home_s, away_s) if is_home else (away_s, home_s)
            defending_goalie = away_g if is_home else home_g
            empty_net = defending_goalie == 0
            strength = "ev" if own == opp else "pp" if own > opp else "sh"

        prev = last_by_team.get(team)
        rebound = bool(prev and per["number"] == prev[1] and 0 <= t - prev[0] <= 3 and prev[2] != "block")
        if kind != "block" or True:
            last_by_team[team] = (t, per["number"], kind)

        dist = angle = None
        if x is not None:
            dx = GOAL_X - x
            dist = math.hypot(dx, y)
            angle = math.degrees(math.atan2(abs(y), dx))  # 0 = straight on, >90 = behind the goal line

        out.append({
            "event_id": p.get("eventId"), "period": per["number"], "time_sec": t, "kind": kind,
            "team_id": team, "is_home": is_home,
            "shooter_id": d.get("shootingPlayerId") or d.get("scoringPlayerId"),
            "blocker_id": d.get("blockingPlayerId"), "goalie_id": d.get("goalieInNetId"),
            "shot_type": d.get("shotType"), "x": x, "y": y, "distance": dist, "angle": angle,
            "strength": strength, "empty_net": empty_net, "rebound": rebound, "situation": sit,
        })
    return out


# --- Expected goals -------------------------------------------------------------------------------
import json
import pathlib

TYPES = ["wrist", "snap", "slap", "backhand", "tip-in", "deflected", "wrap-around", "poke", "bat", "between-legs", "cradle"]
FEATURE_NAMES = (
    ["distance", "distance_sq", "angle", "angle_sq", "behind_net", "rebound", "power_play", "short_handed"]
    + [f"type_{t}" for t in TYPES[1:]]  # wrist shot is the baseline
    + ["type_other"]
)


def features(s):
    """Model inputs for one attempt (must only be called when it has coordinates and a strength)."""
    d, a = s["distance"], s["angle"]
    v = [d, d * d / 100.0, a, a * a / 100.0, 1.0 if a > 90 else 0.0, 1.0 if s["rebound"] else 0.0,
         1.0 if s["strength"] == "pp" else 0.0, 1.0 if s["strength"] == "sh" else 0.0]
    st = s.get("shot_type")
    v += [1.0 if st == t else 0.0 for t in TYPES[1:]]
    v.append(1.0 if st not in TYPES and st is not None else 0.0)
    return v


_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        path = pathlib.Path(__file__).with_name("xg_model.json")
        _MODEL = json.loads(path.read_text()) if path.exists() else {}
    return _MODEL


def xg(s):
    """Probability this attempt is a goal, or None for blocked shots, empty nets, or no location."""
    m = _model()
    if not m or s["kind"] == "block" or s["empty_net"] or s["x"] is None or s["strength"] is None:
        return None
    z = m["intercept"] + sum(c * x for c, x in zip(m["coef"], features(s)))
    return 1.0 / (1.0 + math.exp(-z))
