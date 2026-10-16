"""NHL EDGE tracking stats: shot speed, skating speed, distance, zone time, shot locations.

The NHL publishes these per player and season (since 2021-22) through api-web.nhle.com/v1/edge. Skaters need
three responses (detail, skating-speed-detail, shot-speed-detail) and goalies one. This module only turns
those responses into flat rows; fetching and storing live in ingest.py. Speeds are in mph, distances in
miles, and every *_pctile is the NHL's own 0-1 percentile among tracked players.
"""
import re

SKATER_COLUMNS = [
    ("top_shot_mph", "REAL"), ("top_shot_pctile", "REAL"), ("top_shot_date", "DATE"), ("top_shot_game_id", "BIGINT"),
    ("avg_shot_mph", "REAL"), ("avg_shot_pctile", "REAL"),
    # shot ATTEMPTS (on goal, missed or blocked) by speed band; the column names keep the old "shots" wording
    ("shots_100_plus", "INTEGER"), ("shots_90_100", "INTEGER"), ("shots_80_90", "INTEGER"), ("shots_70_80", "INTEGER"),
    ("top_speed_mph", "REAL"), ("top_speed_pctile", "REAL"), ("top_speed_date", "DATE"), ("top_speed_game_id", "BIGINT"),
    ("bursts_22_plus", "INTEGER"), ("bursts_22_pctile", "REAL"), ("bursts_20_22", "INTEGER"), ("bursts_18_20", "INTEGER"),
    ("distance_miles", "REAL"), ("distance_pctile", "REAL"), ("distance_max_game_miles", "REAL"),
    ("oz_pct", "REAL"), ("oz_pctile", "REAL"), ("oz_ev_pct", "REAL"), ("nz_pct", "REAL"), ("dz_pct", "REAL"), ("dz_pctile", "REAL"),
    ("sog", "INTEGER"), ("sog_goals", "INTEGER"), ("hd_sog", "INTEGER"), ("hd_goals", "INTEGER"),
]
GOALIE_COLUMNS = [
    ("ga_avg", "REAL"), ("ga_avg_pctile", "REAL"), ("games_above_900", "REAL"), ("games_above_900_pctile", "REAL"),
    ("goal_diff_per60", "REAL"), ("goal_support_avg", "REAL"), ("point_pctg", "REAL"),
    ("sv_all", "REAL"), ("sv_high", "REAL"), ("sv_mid", "REAL"), ("sv_long", "REAL"),
    ("sv_high_pctile", "REAL"), ("sv_mid_pctile", "REAL"), ("sv_long_pctile", "REAL"),
    ("saves_high", "INTEGER"), ("ga_high", "INTEGER"), ("saves_mid", "INTEGER"), ("ga_mid", "INTEGER"),
    ("saves_long", "INTEGER"), ("ga_long", "INTEGER"),
]


def _get(obj, *path):
    for key in path:
        if obj is None:
            return None
        obj = obj.get(key) if isinstance(obj, dict) else obj[key] if isinstance(obj, list) and key < len(obj) else None
    return obj


def _game_id(link):
    """The NHL game id at the end of a gamecenter link, e.g. /gamecenter/edm-vs-cbj/2025/11/13/2025020274."""
    m = re.search(r"/(\d{10})$", link or "")
    return int(m.group(1)) if m else None


def _first(*values):
    return next((v for v in values if v is not None), None)


def parse_skater(detail, skating, shot):
    """Flat dict of SKATER_COLUMNS from the three EDGE responses (each may be None). The dedicated speed
    responses win over the summary when both carry a figure, since they have more decimals."""
    detail, skating, shot = detail or {}, skating or {}, shot or {}
    shots_by_area = {s.get("locationCode"): s for s in detail.get("sogSummary") or []}
    zone = detail.get("zoneTimeDetails") or {}
    top_shot = _get(shot, "shotSpeedDetails", "topShotSpeed")
    top_speed = _get(skating, "skatingSpeedDetails", "maxSkatingSpeed")
    hardest = _get(shot, "hardestShots", 0)
    fastest = _get(skating, "topSkatingSpeeds", 0)
    bursts = skating.get("skatingSpeedDetails") or {}
    speeds = shot.get("shotSpeedDetails") or {}
    row = {
        "top_shot_mph": _first(_get(top_shot, "imperial"), _get(detail, "topShotSpeed", "imperial")),
        "top_shot_pctile": _first(_get(top_shot, "percentile"), _get(detail, "topShotSpeed", "percentile")),
        "top_shot_date": _first(_get(hardest, "gameDate"), _get(detail, "topShotSpeed", "overlay", "gameDate")),
        "top_shot_game_id": _game_id(_get(hardest, "gameCenterLink")),
        "avg_shot_mph": _get(speeds, "avgShotSpeed", "imperial"),
        "avg_shot_pctile": _get(speeds, "avgShotSpeed", "percentile"),
        "shots_100_plus": _get(speeds, "shotAttemptsOver100", "value"),
        "shots_90_100": _get(speeds, "shotAttempts90To100", "value"),
        "shots_80_90": _get(speeds, "shotAttempts80To90", "value"),
        "shots_70_80": _get(speeds, "shotAttempts70To80", "value"),
        "top_speed_mph": _first(_get(top_speed, "imperial"), _get(detail, "skatingSpeed", "speedMax", "imperial")),
        "top_speed_pctile": _first(_get(top_speed, "percentile"), _get(detail, "skatingSpeed", "speedMax", "percentile")),
        "top_speed_date": _first(_get(fastest, "gameDate"), _get(detail, "skatingSpeed", "speedMax", "overlay", "gameDate")),
        "top_speed_game_id": _game_id(_get(fastest, "gameCenterLink")),
        "bursts_22_plus": _get(bursts, "burstsOver22", "value"),
        "bursts_22_pctile": _get(bursts, "burstsOver22", "percentile"),
        "bursts_20_22": _get(bursts, "bursts20To22", "value"),
        "bursts_18_20": _get(bursts, "bursts18To20", "value"),
        "distance_miles": _get(detail, "totalDistanceSkated", "imperial"),
        "distance_pctile": _get(detail, "totalDistanceSkated", "percentile"),
        "distance_max_game_miles": _get(detail, "distanceMaxGame", "imperial"),
        "oz_pct": zone.get("offensiveZonePctg"), "oz_pctile": zone.get("offensiveZonePercentile"),
        "oz_ev_pct": zone.get("offensiveZoneEvPctg"),
        "nz_pct": zone.get("neutralZonePctg"),
        "dz_pct": zone.get("defensiveZonePctg"), "dz_pctile": zone.get("defensiveZonePercentile"),
        "sog": _get(shots_by_area.get("all"), "shots"), "sog_goals": _get(shots_by_area.get("all"), "goals"),
        "hd_sog": _get(shots_by_area.get("high"), "shots"), "hd_goals": _get(shots_by_area.get("high"), "goals"),
    }
    # The NHL reports 0 mph for a player it tracked no shot from; that means "no data", not a record low.
    if not row["top_shot_mph"]:
        for col in ("top_shot_mph", "top_shot_pctile", "top_shot_date", "top_shot_game_id"):
            row[col] = None
    if not row["avg_shot_mph"]:
        row["avg_shot_mph"] = row["avg_shot_pctile"] = None
    return row


def parse_goalie(detail):
    """Flat dict of GOALIE_COLUMNS from a goalie-detail response (None gives all-None)."""
    detail = detail or {}
    stats = detail.get("stats") or {}
    by_area = {s.get("locationCode"): s for s in detail.get("shotLocationSummary") or []}
    out = {
        "ga_avg": _get(stats, "goalsAgainstAvg", "value"), "ga_avg_pctile": _get(stats, "goalsAgainstAvg", "percentile"),
        "games_above_900": _get(stats, "gamesAbove900", "value"), "games_above_900_pctile": _get(stats, "gamesAbove900", "percentile"),
        "goal_diff_per60": _get(stats, "goalDifferentialPer60", "value"),
        "goal_support_avg": _get(stats, "goalSupportAvg", "value"),
        "point_pctg": _get(stats, "pointPctg", "value"),
        "sv_all": _get(by_area.get("all"), "savePctg"),
    }
    for loc in ("high", "mid", "long"):
        out[f"sv_{loc}"] = _get(by_area.get(loc), "savePctg")
        out[f"sv_{loc}_pctile"] = _get(by_area.get(loc), "savePctgPercentile")
        out[f"saves_{loc}"] = _get(by_area.get(loc), "saves")
        out[f"ga_{loc}"] = _get(by_area.get(loc), "goalsAgainst")
    return out
