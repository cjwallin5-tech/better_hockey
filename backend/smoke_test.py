"""Hit every API endpoint against the running server and check the basics.

Usage: .venv/bin/python smoke_test.py [base_url]   (default http://localhost:8000)
Picks real ids from the API itself, so it keeps working as the season changes.
"""
import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
failures = []


def get(path, expect=200):
    r = requests.get(BASE + path, timeout=60)
    ok = r.status_code == expect
    print(f"{'ok ' if ok else 'FAIL'} {r.status_code} {path}")
    if not ok:
        failures.append((path, r.status_code, r.text[:200]))
    return r.json() if ok and r.headers.get("content-type", "").startswith("application/json") else None


meta = get("/api/meta")
skaters = get("/api/skaters") or []
goalies = (get("/api/goalies") or {}).get("goalies", [])
teams = get("/api/teams") or []
sk, go, tm = skaters[0]["player_id"], goalies[0]["player_id"], teams[0]["abbrev"]
home = get("/api/home") or {}
game = (home.get("games") or [{}])[0].get("game_id")

for path in (
    f"/api/skaters/{sk}", f"/api/skaters/{sk}/similar", f"/api/skaters/{sk}/context", f"/api/skaters/{sk}/shots",
    f"/api/skaters/{sk}/linemates", f"/api/skaters/{sk}/pace-history", f"/api/skaters/{sk}/pace-history?stat=goals",
    f"/api/goalies/{go}", f"/api/goalies/{go}/context", f"/api/goalies/{go}/shots",
    f"/api/players/{sk}/career", f"/api/players/{sk}/comparables", f"/api/players/{sk}/defense", f"/api/players/{sk}/profile", f"/api/players/{go}/profile",
    f"/api/teams/{tm}", f"/api/teams/{tm}/lines", f"/api/teams/{tm}/shots", f"/api/teams/{tm}/schedule",
    f"/api/teams/{tm}/pace-history", "/api/milestones", "/api/records",
    "/api/playoff-odds", "/api/schedule-grid", "/api/probable-goalies", "/api/trophies", "/api/trophy-races", "/api/live",
    f"/api/fantasy/week?ids={sk},{go}", f"/api/players/{sk}/rankings",
    "/api/alltime/skater?limit=5", "/api/alltime/goalie?limit=5&game_type=3", "/api/alltime/skater/countries",
    "/api/alltime/skater?sort=points_per_game&min_gp=300&position=D&active=true&limit=3",
):
    get(path)
if game:
    get(f"/api/games/{game}")
# error handling: unknown ids are 404/400, never 500
get("/api/skaters/1", expect=404)
get("/api/teams/ZZZ", expect=404)
get(f"/api/players/{go}/comparables", expect=404)
get(f"/api/players/{go}/defense", expect=404)
get("/api/probable-goalies?date=nope", expect=400)
get("/api/alltime/skater?sort=name;drop", expect=400)

print(f"\n{len(failures)} failure(s)")
for f in failures:
    print("  ", f)
sys.exit(1 if failures else 0)
