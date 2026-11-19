"""Shot attempts from play-by-play, with rink coordinates normalized so every team attacks +x.

Used both to train the expected-goals model (train_xg.py) and to store shots at ingest time.
"""
import math

KINDS = {"shot-on-goal": "shot", "missed-shot": "miss", "blocked-shot": "block", "goal": "goal"}
REBOUND_SECONDS = 3  # a follow-up attempt this soon after the same team's shot on goal counts as a rebound
QUICK_SECONDS = 1    # ...and within this many seconds it is a quick whack at a goalie who has not yet reset


def follow_flags(attempts):
    """[(rebound, quick_follow)] for each attempt of one game, given in game order as dicts with team_id (any hashable
    key for the shooting team), period, time_sec and kind. Both look only at the same team's previous attempt, in the same
    period, and only when that attempt was a shot ON GOAL (a miss or a block does not make a rebound). `rebound` is a
    follow-up within REBOUND_SECONDS; `quick_follow` marks the ones within QUICK_SECONDS, which score far less often (the
    goalie is still set) than a follow-up two or three seconds later (he has been pulled out of position)."""
    out, last = [], {}
    for s in attempts:
        prev = last.get(s["team_id"])
        gap = s["time_sec"] - prev[0] if prev and prev[1] == s["period"] else None
        after_save = prev is not None and prev[2] == "shot" and gap is not None and gap >= 0
        out.append((bool(after_save and gap <= REBOUND_SECONDS), bool(after_save and gap <= QUICK_SECONDS)))
        last[s["team_id"]] = (s["time_sec"], s["period"], s["kind"])
    return out
GOAL_X = 89.0  # goal line, in feet from center ice


def _clock(period, mmss):
    m, s = mmss.split(":")
    return (period - 1) * 1200 + int(m) * 60 + int(s)


def extract_shots(pbp):
    """One dict per shot attempt, in game order. Coordinates are None when the feed has none."""
    home_id = pbp["homeTeam"]["id"]
    out = []
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
            "strength": strength, "empty_net": empty_net, "rebound": False, "quick_follow": False, "situation": sit,
        })
    for s, (rebound, quick) in zip(out, follow_flags(out)):
        s["rebound"], s["quick_follow"] = rebound, quick
    return out


def extract_goal_assists(pbp):
    """[(event_id, scorer_id, assist1_id, assist2_id)] for every goal scored in play, in game order. An unassisted goal has None for both
    assisters. Shootout goals are left out: they have no assists."""
    out = []
    for p in sorted(pbp["plays"], key=lambda p: p.get("sortOrder", 0)):
        if p["typeDescKey"] != "goal" or p["periodDescriptor"]["periodType"] == "SO":
            continue
        d = p.get("details", {})
        out.append((p.get("eventId"), d.get("scoringPlayerId"), d.get("assist1PlayerId"), d.get("assist2PlayerId")))
    return out


SHOT_EVENTS = ("goal", "shot-on-goal", "missed-shot")


def extract_special_shots(pbp):
    """Shootout attempts and penalty shots, in game order: [{kind, event_id, period, team_id, shooter_id, goalie_id, scored, on_goal}]
    with kind 'shootout' or 'penalty_shot' (a goalie only faces the ones on goal). A penalty shot is the shot event that follows a penalty of type PS at the same moment on the clock."""
    plays = sorted(pbp["plays"], key=lambda p: p.get("sortOrder", 0))

    def attempt(play, kind):
        d = play.get("details") or {}
        return {"kind": kind, "event_id": play.get("eventId"), "period": play["periodDescriptor"]["number"], "team_id": d.get("eventOwnerTeamId"),
                "shooter_id": d.get("scoringPlayerId") or d.get("shootingPlayerId"), "goalie_id": d.get("goalieInNetId"),
                "scored": play["typeDescKey"] == "goal", "on_goal": play["typeDescKey"] != "missed-shot"}

    out = []
    for i, p in enumerate(plays):
        if p["periodDescriptor"]["periodType"] == "SO" and p["typeDescKey"] in SHOT_EVENTS:
            out.append(attempt(p, "shootout"))
        elif p["typeDescKey"] == "penalty" and (p.get("details") or {}).get("typeCode") == "PS":
            taken = next((q for q in plays[i + 1:i + 4] if q["typeDescKey"] in SHOT_EVENTS and q["periodDescriptor"] == p["periodDescriptor"]
                          and q["timeInPeriod"] == p["timeInPeriod"]), None)
            if taken:
                out.append(attempt(taken, "penalty_shot"))
    return out


# --- Expected goals -------------------------------------------------------------------------------
import json
import pathlib

TYPES = ["wrist", "snap", "slap", "backhand", "tip-in", "deflected", "wrap-around", "poke", "bat", "between-legs", "cradle"]
FEATURE_NAMES = (
    ["distance", "distance_sq", "angle", "angle_sq", "behind_net", "rebound", "power_play", "short_handed"]
    + [f"type_{t}" for t in TYPES[1:]]  # wrist shot is the baseline
    + ["type_other", "quick_follow"]
)


def features(s):
    """Model inputs for one attempt (must only be called when it has coordinates and a strength)."""
    d, a = s["distance"], s["angle"]
    quick = bool(s.get("quick_follow"))
    v = [d, d * d / 100.0, a, a * a / 100.0, 1.0 if a > 90 else 0.0, 1.0 if s["rebound"] and not quick else 0.0,
         1.0 if s["strength"] == "pp" else 0.0, 1.0 if s["strength"] == "sh" else 0.0]
    st = s.get("shot_type")
    v += [1.0 if st == t else 0.0 for t in TYPES[1:]]
    v.append(1.0 if st not in TYPES and st is not None else 0.0)
    v.append(1.0 if quick else 0.0)
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
