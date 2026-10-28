"""Per-game ice time for four past seasons, for the absence-beneficiaries study (analysis/backtest_absences.py).

Run from backend/ to (re)download: .venv/bin/python -I analysis/absence_data.py
One request per week of the season to the NHL stats API's per-game time-on-ice table (every skater's even-strength, power-play and
shorthanded seconds in every game), joined to the points in skater_game_hist. Cached as backend/data/absence_toi.json.gz: a list of
[game_id, date, team, player_id, position, ev, pp, sh, points] rows, the first four seasons' regular seasons from 2022-23 to 2025-26.
"""
import gzip
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config
import oldgames

CACHE = Path(__file__).resolve().parent.parent / "data" / "absence_toi.json.gz"
SEASONS = (20222023, 20232024, 20242025, 20252026)
URL = f"{config.STATS_API}/skater/timeonice"


def get(params):
    for wait in (2, 10, 30):
        r = requests.get(URL, params=params, timeout=90)
        if r.status_code == 200:
            return r.json()["data"]
        time.sleep(wait)
    raise SystemExit(f"HTTP {r.status_code} for {params}")


def fetch():
    rows = []
    with psycopg.connect(config.DATABASE_URL) as conn:
        points = {(p, g): pts for p, g, pts in conn.execute("SELECT player_id, game_id, points FROM skater_game_hist")}
        spans = {s: conn.execute("SELECT min(game_date), max(game_date) FROM team_game_hist WHERE season_id = %s", (s,)).fetchone() for s in SEASONS}
    for season, (first, last) in spans.items():
        day = first
        got = 0
        while day <= last:
            end = min(day + timedelta(days=6), last)
            data = get({"isGame": "true", "limit": -1, "cayenneExp": f'gameDate>="{day}" and gameDate<="{end}" and gameTypeId=2'})
            for r in data:
                rows.append([r["gameId"], r["gameDate"], oldgames.current_code(r["teamAbbrev"]), r["playerId"], r["positionCode"],
                             r["evTimeOnIce"], r["ppTimeOnIce"], r["shTimeOnIce"], points.get((r["playerId"], r["gameId"]))])
            got += len(data)
            day = end + timedelta(days=1)
            time.sleep(0.7)
        print(season, got)
    with gzip.open(CACHE, "wt") as f:
        json.dump(rows, f)
    return rows


def load():
    if CACHE.exists():
        with gzip.open(CACHE, "rt") as f:
            return json.load(f)
    return fetch()


if __name__ == "__main__":
    fetch()
