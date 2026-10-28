"""Goal timelines for four past seasons, for the in-game win probability model (analysis/backtest_winprob.py).

Run from backend/ to (re)download: .venv/bin/python -I analysis/winprob_data.py
One request per game day to the NHL's scoreboard (/score/{date}), which lists every game's goals with period, clock, team and strength, plus the final
score and how the game ended (REG, OT or SO). Cached as backend/data/game_goals.json.gz: [{id, date, home, away, hs, as, end, goals: [[second, home?]]}],
regular-season games from 2022-23 to 2025-26. `second` counts from puck drop (regulation 0-3600, overtime after); shootout goals are not listed, the final
score carries them.
"""
import gzip
import json
import sys
import time
from pathlib import Path

import psycopg
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config
import oldgames

CACHE = Path(__file__).resolve().parent.parent / "data" / "game_goals.json.gz"
SEASONS = (20222023, 20232024, 20242025, 20252026)


def get(url):
    for wait in (2, 10, 30):
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            return r.json()
        time.sleep(wait)
    raise SystemExit(f"HTTP {r.status_code} for {url}")


def second(goal):
    period = goal["period"]
    m, s = goal["timeInPeriod"].split(":")
    return (min(period, 4) - 1) * 1200 + int(m) * 60 + int(s)


def fetch():
    with psycopg.connect(config.DATABASE_URL) as conn:
        days = [d for (d,) in conn.execute("SELECT DISTINCT game_date FROM team_game_hist WHERE season_id = ANY(%s) ORDER BY 1", (list(SEASONS),))]
    games = {}
    for i, day in enumerate(days):
        for g in get(f"{config.WEB_API}/score/{day}")["games"]:
            if g["gameType"] != 2 or g["gameState"] not in ("OFF", "FINAL") or g["id"] in games:
                continue
            home, away = g["homeTeam"], g["awayTeam"]
            h = oldgames.current_code(home["abbrev"])
            games[g["id"]] = {
                "id": g["id"], "date": g["gameDate"], "home": h, "away": oldgames.current_code(away["abbrev"]), "hs": home["score"], "as": away["score"],
                "end": (g.get("gameOutcome") or {}).get("lastPeriodType", "REG"),
                "goals": [[second(x), 1 if oldgames.current_code(x["teamAbbrev"]) == h else 0] for x in g.get("goals", []) if x["period"] <= 4]}
        if i % 20 == 0:
            print(i, "of", len(days), "days", len(games), "games", flush=True)
        time.sleep(0.6)
    rows = sorted(games.values(), key=lambda r: (r["date"], r["id"]))
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
