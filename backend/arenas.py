"""Where each team plays: arena latitude and longitude (city level is plenty) and time zone, for travel distances.

The games we store don't carry a location, so a game is taken to be played at the home team's arena. Coyotes games
(ARI) are Utah's. Distances are great-circle kilometres between the arenas of consecutive games, which ignores
that a team can fly home between games on a long road trip.
"""
import math
from datetime import datetime
from zoneinfo import ZoneInfo

ARENAS = {
    "ANA": (33.8078, -117.8765, "America/Los_Angeles"), "BOS": (42.3662, -71.0621, "America/New_York"),
    "BUF": (42.8750, -78.8764, "America/New_York"), "CGY": (51.0374, -114.0519, "America/Edmonton"),
    "CAR": (35.8033, -78.7219, "America/New_York"), "CHI": (41.8807, -87.6742, "America/Chicago"),
    "COL": (39.7487, -105.0077, "America/Denver"), "CBJ": (39.9693, -83.0061, "America/New_York"),
    "DAL": (32.7905, -96.8103, "America/Chicago"), "DET": (42.3411, -83.0553, "America/New_York"),
    "EDM": (53.5469, -113.4979, "America/Edmonton"), "FLA": (26.1584, -80.3256, "America/New_York"),
    "LAK": (34.0430, -118.2673, "America/Los_Angeles"), "MIN": (44.9448, -93.1011, "America/Chicago"),
    "MTL": (45.4961, -73.5693, "America/New_York"), "NSH": (36.1592, -86.7785, "America/Chicago"),
    "NJD": (40.7336, -74.1711, "America/New_York"), "NYI": (40.7233, -73.5906, "America/New_York"),
    "NYR": (40.7505, -73.9934, "America/New_York"), "OTT": (45.2969, -75.9272, "America/New_York"),
    "PHI": (39.9012, -75.1720, "America/New_York"), "PIT": (40.4395, -79.9892, "America/New_York"),
    "SJS": (37.3327, -121.9010, "America/Los_Angeles"), "SEA": (47.6221, -122.3540, "America/Los_Angeles"),
    "STL": (38.6268, -90.2026, "America/Chicago"), "TBL": (27.9427, -82.4519, "America/New_York"),
    "TOR": (43.6435, -79.3791, "America/New_York"), "UTA": (40.7683, -111.9011, "America/Denver"),
    "VAN": (49.2778, -123.1089, "America/Vancouver"), "VGK": (36.1029, -115.1785, "America/Los_Angeles"),
    "WSH": (38.8981, -77.0209, "America/New_York"), "WPG": (49.8928, -97.1436, "America/Winnipeg"),
}
ARENAS["ARI"] = ARENAS["UTA"]
EARTH_KM = 6371.0


def distance_km(a, b):
    """Great-circle distance between two teams' arenas."""
    (la1, lo1, _), (la2, lo2, _) = ARENAS[a], ARENAS[b]
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(h))


def utc_offset_hours(team, on):
    """The arena's UTC offset (hours, negative in the Americas) on a date."""
    return datetime(on.year, on.month, on.day, 12, tzinfo=ZoneInfo(ARENAS[team][2])).utcoffset().total_seconds() / 3600
