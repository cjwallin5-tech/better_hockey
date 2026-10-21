"""Database side of matchups.py: team ratings from this season's stored shots, and the goalie effect from every stored
season, joined into one row per team. Functions take an open psycopg connection that returns dict rows."""
import luck_db
import matchups


def team_inputs(conn, season):
    """[{team, games, xgf, xga}] from this season's stored shots (xG for and against, and games with shots stored)."""
    return conn.execute(
        """SELECT t AS team, count(DISTINCT game_id) AS games,
                  coalesce(sum(xg) FILTER (WHERE side = 'f'), 0)::float AS xgf,
                  coalesce(sum(xg) FILTER (WHERE side = 'a'), 0)::float AS xga
           FROM (SELECT team AS t, game_id, xg, 'f' AS side FROM shot WHERE season_id = %(s)s
                 UNION ALL SELECT opponent, game_id, xg, 'a' FROM shot WHERE season_id = %(s)s) x
           GROUP BY t""", {"s": season}).fetchall()


def league_rates(conn, season):
    """(on-goal shots, goals) per team-game this season, for turning a goalie's saved goals into a share of scoring."""
    r = conn.execute(
        """SELECT count(DISTINCT game_id) AS games, count(*) FILTER (WHERE kind IN ('shot', 'goal')) AS on_goal,
                  count(*) FILTER (WHERE kind = 'goal') AS goals FROM shot WHERE season_id = %s""", (season,)).fetchone()
    team_games = 2 * r["games"]
    return (r["on_goal"] / team_games, r["goals"] / team_games) if team_games else (None, None)


def goalie_effects(conn, season, shots_pg, goals_pg):
    """{team: expected goalie factor} weighted by this season's starts, plus {goalie_id: per-100 estimate}."""
    pooled = conn.execute(
        f"""WITH {luck_db.GOALIE_CALIBRATION_CTE}
            SELECT goalie_id, count(*) AS shots,
                   sum({luck_db.GOALIE_XG})::float - count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS gsax
            FROM (SELECT season_id, goalie_id, kind, xg FROM shot_hist UNION ALL SELECT season_id, goalie_id, kind, xg FROM shot
                  WHERE season_id NOT IN (SELECT season_id FROM shot_hist_game)) t
            JOIN gcal USING (season_id) WHERE goalie_id IS NOT NULL AND kind IN ('shot', 'goal') GROUP BY goalie_id""").fetchall()
    estimate = {r["goalie_id"]: matchups.goalie_estimate(r["gsax"], r["shots"]) for r in pooled}
    by_team = {}
    for r in conn.execute(
            """SELECT team, player_id, count(*) FILTER (WHERE started) AS starts FROM goalie_game
               WHERE season_id = %s GROUP BY team, player_id""", (season,)):
        mult = matchups.goalie_multiplier(estimate.get(r["player_id"], 0.0), shots_pg, goals_pg) if shots_pg else 1.0
        by_team.setdefault(r["team"], []).append((r["starts"], mult))
    return {t: matchups.expected_goalie_multiplier(g) for t, g in by_team.items()}, estimate


def team_table(conn, season):
    """One row per team with its offense and defense ratios, goalie factor and the ratios for skaters and goalies facing
    it (above 1 is favorable to the player). Empty before any shots are stored. Also returns the league figures."""
    ratings, league_xg = matchups.team_ratings(team_inputs(conn, season))
    if not ratings:
        return [], {}
    shots_pg, goals_pg = league_rates(conn, season)
    goalie_mult, _ = goalie_effects(conn, season, shots_pg, goals_pg)
    names = {r["abbrev"]: r for r in conn.execute(
        "SELECT abbrev, name, common_name, logo_url, logo_dark_url FROM team_season WHERE season_id = %s", (season,))}
    rows = []
    for team, r in ratings.items():
        gm = goalie_mult.get(team, 1.0)
        skater = matchups.skater_ratio(r["def_ratio"], gm)
        goalie = 2 - r["off_ratio"]
        rows.append({"team": team, "name": names.get(team, {}).get("common_name") or names.get(team, {}).get("name") or team,
                     "logo_url": names.get(team, {}).get("logo_url"), "logo_dark_url": names.get(team, {}).get("logo_dark_url"),
                     **r, "goalie_mult": gm, "skater_ratio": skater, "goalie_ratio": goalie,
                     "skater_label": matchups.label(skater), "goalie_label": matchups.label(goalie)})
    rows.sort(key=lambda r: r["team"])
    return rows, {"xg_pg": league_xg, "shots_pg": shots_pg, "goals_pg": goals_pg}
