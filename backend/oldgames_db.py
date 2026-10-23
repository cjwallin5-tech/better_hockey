"""Fetches and stores one player's older games (see oldgames.py): the first time head-to-head is asked about a player,
their NHL game logs from 2005-06 up to the seasons we store game by game are pulled from the NHL and kept, because
those seasons never change. Takes an open psycopg connection; raises requests.RequestException if the NHL can't be
reached, leaving nothing marked as fetched so the next request tries again."""
from concurrent.futures import ThreadPoolExecutor

import requests

import config
import oldgames

WORKERS = 4


def _get(url):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def first_stored_season():
    """The oldest season whose games we hold game by game (older ones come from here)."""
    return config.SEASON_ID - 40004


def ensure_player(conn, player_id, goalie):
    """Makes sure the player's older games are in player_game_old. Returns how many games were just fetched (0 if already there)."""
    if conn.execute("SELECT 1 FROM player_game_old_fetched WHERE player_id = %s", (player_id,)).fetchone():
        return 0
    landing = _get(f"{config.WEB_API}/player/{player_id}/landing")
    seasons = oldgames.nhl_seasons(landing, first_stored_season())

    def log(season):
        return oldgames.parse_game_log(_get(f"{config.WEB_API}/player/{player_id}/game-log/{season}/2"), season, goalie)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rows = [row for part in pool.map(log, seasons) for row in part]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO player_game_old (player_id, game_id, season_id, game_date, opponent, goals, assists, shots_against, goals_against)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            [(player_id, r["game_id"], r["season_id"], r["game_date"], r["opponent"], r["goals"], r["assists"],
              r["shots_against"], r["goals_against"]) for r in rows])
        cur.execute("INSERT INTO player_game_old_fetched (player_id) VALUES (%s) ON CONFLICT DO NOTHING", (player_id,))
    conn.commit()
    return len(rows)
