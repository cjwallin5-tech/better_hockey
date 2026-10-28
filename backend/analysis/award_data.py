"""Historical data for the award-odds backtest (analysis/backtest_award_odds.py): who won and who was a finalist for the Hart, Norris,
Calder, Selke and Vezina each season, with every plausible candidate's season line.

Run from backend/ to (re)download: .venv/bin/python -I analysis/award_data.py
Awards come from the NHL records site (winner, runner-up and finalist per season); skater and goalie lines from the NHL stats API;
team points from backend/data/playoff_backtest.json (built by backtest_playoff_odds.py); rookies and ages from the career tables.
Everything is cached in backend/data/award_backtest.json (a season is named by the year it ends in), so the backtest runs offline.
"""
import json
import sys
import time
from pathlib import Path

import psycopg
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config
import oldgames

DATA = Path(__file__).resolve().parent.parent / "data"
CACHE = DATA / "award_backtest.json"
TROPHIES = {"hart": 8, "norris": 11, "calder": 4, "vezina": 18, "selke": 17}
FIRST, LAST = 2006, 2025
STATS = "https://api.nhle.com/stats/rest/en"
RECORDS = "https://records.nhl.com/site/api"


def get(url, **params):
    for wait in (2, 10, 30):
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        time.sleep(wait)
    raise SystemExit(f"{url}: HTTP {r.status_code}")


def fetch():
    out = {"awards": {}, "skaters": {}, "goalies": {}}
    for name, tid in TROPHIES.items():
        rows = get(f"{RECORDS}/award-details", cayenneExp=f"trophyId={tid}")["data"]
        by_season = {}
        for r in rows:
            if r.get("playerId") is None:
                continue
            by_season.setdefault(str(r["seasonId"] % 10000), {})[str(r["playerId"])] = r["status"]
        out["awards"][name] = by_season
        time.sleep(1)
    for year in range(FIRST, LAST + 1):
        sid = (year - 1) * 10000 + year
        cay = f"seasonId={sid} and gameTypeId=2"
        sk = get(f"{STATS}/skater/summary", limit=-1, sort='[{"property":"points","direction":"DESC"}]', cayenneExp=cay)["data"]
        extra = {}
        for table, fields in (("realtime", ("hits", "blockedShots", "takeaways", "giveaways")),
                              ("timeonice", ("evTimeOnIcePerGame", "shTimeOnIcePerGame", "ppTimeOnIcePerGame")),
                              ("faceoffpercentages", ("faceoffWinPct", "totalFaceoffs")),
                              ("puckPossessions", ("satPct", "defensiveZoneStartPct"))):
            for r in get(f"{STATS}/skater/{table}", limit=-1, cayenneExp=cay)["data"]:
                extra.setdefault(r["playerId"], {}).update({f: r.get(f) for f in fields})
            time.sleep(1)
        out["skaters"][str(year)] = [
            {"id": r["playerId"], "name": r["skaterFullName"], "pos": r["positionCode"], "team": r["teamAbbrevs"], "gp": r["gamesPlayed"],
             "goals": r["goals"], "assists": r["assists"], "points": r["points"], "plus_minus": r.get("plusMinus"),
             "toi_pg": r.get("timeOnIcePerGame"), "pp_points": r.get("ppPoints"), **extra.get(r["playerId"], {})} for r in sk if r["points"] >= 15 or r["positionCode"] == "D" and r["points"] >= 8]
        gl = get(f"{STATS}/goalie/summary", limit=-1, cayenneExp=cay)["data"]
        out["goalies"][str(year)] = [
            {"id": r["playerId"], "name": r["goalieFullName"], "team": r["teamAbbrevs"], "gp": r["gamesPlayed"], "wins": r["wins"],
             "saves": r["saves"], "shots_against": r["shotsAgainst"], "goals_against": r["goalsAgainst"], "shutouts": r["shutouts"],
             "sv_pct": r["savePct"]} for r in gl if r["gamesPlayed"] >= 10]
        print(year, len(out["skaters"][str(year)]), len(out["goalies"][str(year)]))
        time.sleep(1)
    teams = json.loads((DATA / "playoff_backtest.json").read_text())
    out["teams"] = {y: {t["abbrev"]: {"points": t["points"], "gp": t["games_played"]} for t in d["standings"]["end"]} for y, d in teams.items()}
    with psycopg.connect(config.DATABASE_URL) as conn:
        rows = conn.execute("SELECT player_id, first_season, birth_date FROM career_skater WHERE game_type = 2").fetchall()
    out["bio"] = {str(p): {"first": f, "born": str(b) if b else None} for p, f, b in rows}
    CACHE.write_text(json.dumps(out))
    return out


def load():
    return json.loads(CACHE.read_text()) if CACHE.exists() else fetch()


if __name__ == "__main__":
    fetch()
