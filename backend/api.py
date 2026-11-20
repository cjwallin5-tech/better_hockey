"""Read-only JSON API over the ingested stats. Run: uvicorn api:app --reload

The endpoints live in routes/, one module per area; this file builds the app and wires them together."""
import threading

import psycopg
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from psycopg.rows import dict_row

import auth
import bestseasons
import config
import leagues
import predictions
import previews
from routes import analytics, awards, fantasy, games, goalies, history, league, players, skaters, teams
from routes.common import _season_board
from routes.games import tonight_endpoint

app = FastAPI(title="Faceoff")
# Responses like /api/skaters are over a megabyte of repetitive JSON; compressing them is the cheapest speed-up there is.
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)  # level 9 (the default) costs twice the CPU for ~8% fewer bytes
app.include_router(auth.router)
app.include_router(leagues.router)
app.include_router(previews.router)
for module in (skaters, players, goalies, teams, games, fantasy, awards, history, analytics, league):
    app.include_router(module.router)


@app.on_event("startup")
def _init_accounts():
    auth.init_db()
    leagues.init_db()   # after auth: its tables refer to app_user
    predictions.init_db()
    threading.Thread(target=_warm_season_boards, daemon=True).start()  # so the first visit to Best seasons doesn't wait for the build


def _warm_season_boards():
    try:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            for kind in bestseasons.SORTS:
                _season_board(conn, kind)
        tonight_endpoint()
    except Exception:  # only a head start: the page builds the board itself if this didn't
        pass
