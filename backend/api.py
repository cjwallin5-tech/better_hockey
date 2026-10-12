"""Read-only JSON API over the ingested stats. Run: uvicorn api:app --reload"""
import psycopg
from fastapi import FastAPI
from psycopg.rows import dict_row

import config

app = FastAPI(title="Hockey Stats")

SKATERS_SQL = """
WITH ranked AS (
    SELECT player_id, points,
           row_number() OVER (PARTITION BY player_id ORDER BY game_date DESC) AS rn
    FROM skater_game WHERE season_id = %(season)s
),
recent AS (
    SELECT player_id, count(*) AS games, sum(points) AS points
    FROM ranked WHERE rn <= %(window)s GROUP BY player_id
)
SELECT s.player_id, s.name, s.team, s.position, s.games_played, s.goals, s.assists,
       s.points, s.plus_minus, s.shots, s.toi_per_game_sec,
       s.hits, s.blocked_shots, s.takeaways, s.giveaways,
       s.hits_per60, s.blocks_per60, s.takeaways_per60, s.giveaways_per60,
       round(s.points::numeric / s.games_played * %(games)s, 1)::float AS point_pace,
       r.games AS recent_games, r.points AS recent_points,
       round(r.points::numeric / r.games * %(games)s, 1)::float AS recent_pace
FROM skater_season s
LEFT JOIN recent r USING (player_id)
WHERE s.season_id = %(season)s AND s.games_played > 0
ORDER BY s.points DESC, s.games_played ASC
"""


@app.get("/api/meta")
def meta():
    return {
        "season_id": config.SEASON_ID,
        "games_per_season": config.GAMES_PER_SEASON,
        "recent_window": config.RECENT_WINDOW,
    }


@app.get("/api/skaters")
def skaters():
    params = {
        "season": config.SEASON_ID,
        "window": config.RECENT_WINDOW,
        "games": config.GAMES_PER_SEASON,
    }
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(SKATERS_SQL, params).fetchall()
