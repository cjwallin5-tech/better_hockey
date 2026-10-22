"""Career-trajectory comparables: retired players whose age curve looked like this player's.

Method (deliberately simple, and the page says so):
- A season counts when the player had MIN_GP games. Its value is points per game divided by the
  league's points per game that season for the same role (forwards vs defensemen), so 1.5 means
  "50% more scoring than a typical regular", whatever the era. That is why a 1980s star can be a
  fair match for a modern one.
- Players are placed on an age axis (age on Feb 1 of the season's second year).
- Distance is the weighted RMS gap in that value across ages both players have played. Recent
  seasons weigh more, and short seasons (lockouts, injuries) weigh less.
- A match must overlap at least OVERLAP_SHARE of the target's seasons, and a retired player is
  only a candidate for a target of the same role.
- For an active target, what each match did afterwards is scaled to today's scoring level, so a
  1985 point total isn't compared with a 2025 one.
"""
import math
import statistics
from collections import defaultdict

MIN_GP = 20
MIN_SEASONS = 2         # target needs this many qualifying seasons
OVERLAP_SHARE = 0.6
FULL_SEASON = 82
SIMILARITY_SCALE = 4.0  # similarity = 100 / (1 + SIMILARITY_SCALE * rms): rms 0.25 scores 50


def role(position):
    return "D" if position == "D" else "F"


def age_in(season_id, birth):
    """Age on Feb 1 of the season's second calendar year."""
    return season_id % 10000 - birth.year - (1 if (birth.month, birth.day) > (2, 1) else 0)


def baselines(rows):
    """{(season_id, role): league points per game}. rows: (season_id, role, games_played, points),
    counting only players with MIN_GP so call-ups don't drag the average down."""
    gp, pts = defaultdict(int), defaultdict(int)
    for season, r, g, p in rows:
        if g >= MIN_GP:
            gp[season, r] += g
            pts[season, r] += p
    return {k: pts[k] / gp[k] for k in gp if gp[k]}


def curve(seasons, birth, r, base):
    """{age: (games, relative scoring)} for qualifying seasons. seasons: [(season_id, gp, points)]."""
    out = {}
    for season, g, p in seasons:
        b = base.get((season, r))
        if g >= MIN_GP and b:
            out[age_in(season, birth)] = (g, (p / g) / b)
    return out


def distance(target, cand):
    """(rms gap, seasons compared), or None when they overlap too little to say."""
    ages = sorted(set(target) & set(cand))
    need = max(MIN_SEASONS, math.ceil(OVERLAP_SHARE * len(target)))
    if len(ages) < need:
        return None
    num = den = 0.0
    for i, a in enumerate(ages):
        w = (1 + 0.5 * i / max(len(ages) - 1, 1)) * max(0.25, min(1.0, min(target[a][0], cand[a][0]) / FULL_SEASON))
        num += w * (target[a][1] - cand[a][1]) ** 2
        den += w
    return math.sqrt(num / den), len(ages)


def similarity(rms):
    return round(100 / (1 + SIMILARITY_SCALE * rms))


def projection(afters):
    """Spread of what the best matches scored after the target's current age (scaled to today)."""
    if len(afters) < 3:
        return None
    s = sorted(afters)
    q = statistics.quantiles(s, n=4, method="inclusive")
    return {"median": round(statistics.median(s)), "low": round(q[0]), "high": round(q[2]), "matches": len(s)}
