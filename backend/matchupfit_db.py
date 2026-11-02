"""Database side of matchupfit.py: every team's shot diet (shots on goal by zone), this season and last."""
import goaliemap as gm

# The zone of a shot on goal: range from the net and the side as a rink y sign, the shooter's left being positive y. Matches
# goaliemap.zone, which needs the goalie's catching hand to turn a side into glove or blocker (see matchupfit.lane_for).
ZONE_SQL = f"""
    CASE WHEN distance < {gm.CLOSE_FT} THEN 'close' WHEN distance < {gm.MID_FT} THEN 'mid' ELSE 'long' END AS range,
    CASE WHEN angle <= {gm.MIDDLE_ANGLE} THEN 'middle' WHEN y > 0 THEN 'pos' ELSE 'neg' END AS side"""
ON_GOAL = "kind IN ('shot', 'goal') AND NOT coalesce(empty_net, false) AND x IS NOT NULL AND distance IS NOT NULL AND angle IS NOT NULL"


def _fold(rows):
    out = {}
    for r in rows:
        out.setdefault(r["team"], {})[(r["range"], r["side"])] = r["n"]
    return out


def team_diets(conn, season):
    """(current, prior, games): {team: {(range, side): shots}} for this season (from `shot`) and for the most recent past season
    (from shot_hist, whose rows carry the shooting side rather than a team name), and {team: games with shots this season}."""
    current = _fold(conn.execute(
        f"SELECT team, {ZONE_SQL}, count(*) AS n FROM shot WHERE season_id = %s AND {ON_GOAL} GROUP BY 1, 2, 3", (season,)).fetchall())
    games = {r["team"]: r["g"] for r in conn.execute(
        "SELECT team, count(DISTINCT game_id) AS g FROM shot WHERE season_id = %s GROUP BY team", (season,)).fetchall()}
    last = conn.execute("SELECT max(season_id) AS s FROM shot_hist_game WHERE timed AND season_id < %s", (season,)).fetchone()["s"]
    prior = {}
    if last:
        prior = _fold(conn.execute(
            f"""SELECT t.team, {ZONE_SQL}, count(*) AS n
                FROM shot_hist h JOIN team_game_hist t ON t.game_id = h.game_id AND t.is_home = h.is_home
                WHERE h.season_id = %s AND {ON_GOAL}
                GROUP BY 1, 2, 3""", (last,)).fetchall())
    return current, prior, games


def league_shares(current):
    """{(range, side): share} over every team's shots on goal this season."""
    total, tot = {}, 0
    for zones in current.values():
        for z, n in zones.items():
            total[z] = total.get(z, 0) + n
            tot += n
    return {z: n / tot for z, n in total.items()} if tot else {}
