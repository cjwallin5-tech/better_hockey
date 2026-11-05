"""NHL equivalency (NHLe): what a player's scoring in another league is worth in the NHL.

The factors are fitted on our own data: every NHL skater since 2006-07 has his full season-by-season record stored
(player_league_season, loaded by `python ingest.py backfill-leagues`), so a season in league A followed by an NHL season gives
a pair. This module holds the pure parts: reading a player's landing page into rows, and (below) the pairing and factor maths.
"""
import prospects as prospectlib

FIRST_NHL_SEASON = 20062007   # players whose first stored NHL season is this or later have their junior and pro-development years in the data


def landing_rows(landing):
    """(birth_date, position, seasons) from a /player/{id}/landing response. seasons are the regular-season and playoff rows of every
    league the player has played in, as prospects.parse_landing returns them."""
    _, seasons = prospectlib.parse_landing(landing)
    return landing.get("birthDate"), landing.get("position"), seasons


MIN_GAMES_SHOWN = 20   # the factors were fitted on seasons of 20+ games, and a shorter one is too noisy to translate


def nhle_line(line, factors, season_games, age=None, age_mult=None):
    """The NHL-equivalent of one skater season line, or None when it cannot be translated.

    line: a prospect_season-like dict (league, games, points). factors: {league: {factor, lo, hi, pairs}} from nhle_factor. Returns
    {'points': points over `season_games` NHL games, 'low', 'high' (from the factor's 90% interval), 'factor', 'pairs', 'age_mult'}. With an
    age (on the season's September 15) and age_mult ({bucket: multiplier}) the figure is scaled by that age's multiplier. Goalies, leagues
    without a factor, seasons under MIN_GAMES_SHOWN games and lines with no points are None."""
    if not line or line.get("points") is None or (line.get("games") or 0) < MIN_GAMES_SHOWN:
        return None
    f = factors.get(line.get("league"))
    if not f:
        return None
    mult = (age_mult or {}).get(age_bucket(age), 1.0) if age is not None else 1.0
    scale = line["points"] / line["games"] * season_games * mult
    return {"points": scale * f["factor"], "low": scale * f["lo"], "high": scale * f["hi"], "factor": f["factor"], "pairs": f["pairs"],
            "age_mult": mult}


# Age buckets for the multiplier on the factor: (label, lowest age, highest age below). A backtest on later seasons found the plain factor
# too low for young players (they outscore it by about 8%) and far too high for older ones (23 and over score about 22% less).
AGE_BUCKETS = [("under 20", 0, 20), ("20", 20, 21), ("21", 21, 22), ("22", 22, 23), ("23 and over", 23, 99)]


def age_bucket(age):
    """The AGE_BUCKETS label for an age in years."""
    for label, lo, hi in AGE_BUCKETS:
        if lo <= age < hi:
            return label
    return AGE_BUCKETS[-1][0]


def age_on_season(season_id, birth_date):
    """Age in years on September 15 of the season's first year, or None without a birth date (birth_date a date or an ISO string)."""
    if birth_date is None:
        return None
    from datetime import date
    if isinstance(birth_date, str):
        birth_date = date.fromisoformat(birth_date)
    return (date(season_id // 10000, 9, 15) - birth_date).days / 365.25
