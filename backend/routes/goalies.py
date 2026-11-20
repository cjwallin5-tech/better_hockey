"""Goalie endpoints: the leaderboard, a goalie's page data, shots and zones."""

from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row

import config
import goaliemap
import luck_db
from routes.common import GOALIES_SQL, _context, _goalie_params, _goalie_zone_summary, _shots, _stored_season, ttl_cached

router = APIRouter()


@router.get("/api/goalies")
@ttl_cached(60)
def goalies(season: int | None = None):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        chosen = _stored_season(conn, "goalie_season", season)
        return {
            "season_id": chosen,
            "recent_window": config.RECENT_GOALIE_GAMES,
            "goalies": conn.execute(GOALIES_SQL, {**_goalie_params(), "season": chosen}).fetchall(),
        }


@router.get("/api/goalies/{player_id}")
def goalie(player_id: int):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        everyone = conn.execute(GOALIES_SQL, _goalie_params()).fetchall()
        player = next((g for g in everyone if g["player_id"] == player_id), None)
        if player is None:
            raise HTTPException(404, "Goalie not found")
        games = conn.execute(
            """SELECT game_id, game_date, team, opponent, is_home, started, decision,
                      shots_against, saves, goals_against, toi_sec,
                      ev_goals_against, pp_goals_against, sh_goals_against
               FROM goalie_game WHERE player_id = %s AND season_id = %s
               ORDER BY game_date DESC, game_id DESC""",
            (player_id, config.SEASON_ID),
        ).fetchall()
    return {
        "goalie": player,
        "games": games,
        "league_sv_pct": player["league_sv_pct"],
        "recent_window": config.RECENT_GOALIE_GAMES,
    }


@router.get("/api/goalies/{player_id}/context")
def goalie_context(player_id: int):
    return _context(player_id, goalie=True)


@router.get("/api/goalies/{player_id}/shots")
def goalie_shots(player_id: int):
    """Shots this goalie faced, with goals saved above expected (xG faced minus goals allowed)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = _shots(conn, "s.goalie_id = %(p)s AND s.kind IN ('shot', 'goal')", {"p": player_id})
        summary = conn.execute(
            """SELECT count(*) AS faced, count(*) FILTER (WHERE kind = 'goal') AS goals,
                      count(*) FILTER (WHERE xg IS NOT NULL) AS modeled,
                      count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals,
                      coalesce(sum(xg), 0) AS xga
               FROM shot WHERE season_id = %s AND goalie_id = %s AND kind IN ('shot', 'goal')""",
            (config.SEASON_ID, player_id),
        ).fetchone()
        # An attempt's xG includes the chance of missing the net, so shots on goal alone need scaling up to the
        # league's goal total (see luck_db.GOALIE_CALIBRATION_CTE); each shot's own xG is left as the model made it.
        factor = luck_db.goalie_factor(conn, config.SEASON_ID)
        summary["xga"] = summary["xga"] * factor
    return {"shots": rows, "summary": summary, "xga_factor": factor}


@router.get("/api/goalies/{player_id}/zones")
def goalie_zones(player_id: int, span: str = "all"):
    """Where this goalie is beaten: goals allowed against an average goalie's in nine ice zones, by shot type and by situation
    (see goaliemap.py). span=all pools every season with stored shot locations (this one and the past
    seasons backfilled by `ingest.py backfill-shot-locations`); span=current is this season only."""
    if span not in ("all", "current"):
        raise HTTPException(400, "span must be all or current")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        goalie, out = _goalie_zone_summary(conn, player_id, span)
    if goalie is None:
        raise HTTPException(404, "Goalie not found")
    return {"player_id": player_id, "name": goalie["name"], "catches": goalie["catches"], "span": span,
            "headline": goaliemap.headline(out), "min_zone_shots": goaliemap.MIN_ZONE_SHOTS, "flag_z": goaliemap.FLAG_Z, **out}
