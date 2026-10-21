"""Database side of luck.py: aggregate the stored shots and on-ice numbers into one row per player.

Shared by the API and the morning email so both use the same figures. Every function takes an open psycopg
connection that returns dict rows.
"""
import luck


# `shot` holds the current season in full; `shot_hist` holds past seasons (see ingest.py backfill-shots). After a season ends and
# has been backfilled it is in both, so wherever the two are combined the current table counts only for seasons that are not
# archived yet; otherwise that season would be counted twice. shot_hist_game is the small list of archived games.
NOT_ARCHIVED = "(SELECT season_id FROM shot_hist_game)"


# Our xG model runs a few percent under (or over) the real goal total in some seasons. Past seasons' xG is scaled so each
# season's xG sums to that season's goals, so a league-wide drift isn't mistaken for every player's finishing skill.
CALIBRATION_CTE = """cal AS (
    SELECT season_id, CASE WHEN sum(xg) > 0 THEN count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL)::float / sum(xg)
                           ELSE 1 END AS f
    FROM shot_hist GROUP BY season_id)"""


# Goalies are different: they only face shots on goal, but the model's xG for an attempt already includes the chance of
# missing the net, so adding it up over on-goal shots alone comes to about two-thirds of the real goals (a factor of
# 1.3 to 1.5 each season). Scaling each season's goalie xG so the league total matches the league's goals fixes the
# level, so an average goalie sits near zero instead of every goalie looking unlucky. Covers the current season too.
GOALIE_CALIBRATION_CTE = """gcal AS (
    SELECT season_id, count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL)::float / sum(xg) AS f
    FROM (SELECT season_id, kind, xg FROM shot_hist WHERE goalie_id IS NOT NULL
          UNION ALL SELECT season_id, kind, xg FROM shot WHERE goalie_id IS NOT NULL
            AND season_id NOT IN (SELECT season_id FROM shot_hist_game)) t
    WHERE kind IN ('shot', 'goal') GROUP BY season_id HAVING sum(xg) > 0)"""
GOALIE_XG = "least(0.99, xg * f)"  # one shot's calibrated chance of beating the goalie


def goalie_factor(conn, season):
    """The scale factor above for one season (1.0 when there is nothing to calibrate against)."""
    row = conn.execute(f"WITH {GOALIE_CALIBRATION_CTE} SELECT f FROM gcal WHERE season_id = %s", (season,)).fetchone()
    return row["f"] if row else 1.0


def skater_rows(conn, season, games, position="", min_attempts=0, ids=None):
    """Luck figures for skaters with shots this season. Rows can have a None z when a player has no variance
    to measure (no shots that count); each carries `enough`, whether the shot sample meets luck.MIN_ATTEMPTS.
    ids limits it to those player ids."""
    where, params = ["a.attempts >= %(min_attempts)s"], {"season": season, "min_attempts": max(0, min_attempts)}
    if position == "F":
        where.append("p.position <> 'D'")
    elif position in ("C", "L", "R", "D"):
        where.append("p.position = %(position)s")
        params["position"] = position
    if ids is not None:
        where.append("a.player_id = ANY(%(ids)s)")
        params["ids"] = list(ids)
    rows = conn.execute(
        f"""WITH a AS (
                SELECT shooter_id AS player_id,
                       count(*) FILTER (WHERE kind <> 'block') AS attempts,
                       count(*) FILTER (WHERE kind IN ('shot', 'goal')) AS shots_on_goal,
                       count(*) FILTER (WHERE kind = 'goal') AS goals,
                       count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals,
                       coalesce(sum(xg), 0) AS ixg,
                       coalesce(sum(xg * (1 - xg)), 0) AS variance,
                       count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL AND strength = 'ev') AS ev_model_goals,
                       coalesce(sum(xg) FILTER (WHERE strength = 'ev'), 0) AS ev_ixg
                FROM shot WHERE season_id = %(season)s AND shooter_id IS NOT NULL GROUP BY shooter_id),
            o AS (
                SELECT player_id, sum(gf) AS gf, sum(ga) AS ga, sum(xgf) AS xgf, sum(xga) AS xga
                FROM skater_game_onice WHERE season_id = %(season)s AND xgf IS NOT NULL GROUP BY player_id)
            SELECT a.*, p.name, p.team, p.position, p.games_played, p.pdo_5v5 AS pdo, p.points,
                   p.goals AS season_goals, p.pp_goals, p.ev_points, p.ev_goals_for, o.gf, o.ga, o.xgf, o.xga
            FROM a JOIN skater_season p ON p.player_id = a.player_id AND p.season_id = %(season)s
                   LEFT JOIN o ON o.player_id = a.player_id
            WHERE {' AND '.join(where)}""", params).fetchall()
    # Earlier seasons from the stored history, summed per player (see luck.finishing_skill).
    prior = {r["player_id"]: r for r in conn.execute(
        f"""WITH {CALIBRATION_CTE}
           SELECT shooter_id AS player_id, count(DISTINCT h.season_id) AS seasons,
                  count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals,
                  coalesce(sum(xg * f), 0) AS ixg, coalesce(sum(xg * (1 - xg)), 0) AS variance
           FROM shot_hist h JOIN cal USING (season_id)
           WHERE h.season_id < %s AND shooter_id IS NOT NULL
             AND (%s::int[] IS NULL OR shooter_id = ANY(%s::int[]))
           GROUP BY shooter_id""", (season, params.get("ids"), params.get("ids")))}
    # League assists per teammate even-strength goal, forwards and defensemen apart: the baseline each
    # player's own rate is pulled toward (see luck.assist_rate).
    baseline = {r["role"]: r["assists"] / r["mates"] for r in conn.execute(
        """SELECT CASE WHEN position = 'D' THEN 'D' ELSE 'F' END AS role,
                  sum(greatest(0, ev_points - (goals - pp_goals)))::float AS assists,
                  sum(greatest(0, ev_goals_for - (goals - pp_goals)))::float AS mates
           FROM skater_season WHERE season_id = %s AND ev_points IS NOT NULL AND ev_goals_for IS NOT NULL
           GROUP BY 1 HAVING sum(greatest(0, ev_goals_for - (goals - pp_goals))) > 0""", (season,))}
    out = []
    for r in rows:
        line = luck.skater_line(r, games, baseline.get("D" if r["position"] == "D" else "F"), prior.get(r["player_id"]))
        out.append({"player_id": r["player_id"], "name": r["name"], "team": r["team"], "position": r["position"],
                    "games_played": r["games_played"], "attempts": r["attempts"], "shots_on_goal": r["shots_on_goal"],
                    "goals": r["goals"], "ixg": r["ixg"], "pdo": r["pdo"],
                    "onice_gf": r["gf"], "onice_ga": r["ga"], "onice_xgf": r["xgf"], "onice_xga": r["xga"],
                    "enough": r["attempts"] >= luck.MIN_ATTEMPTS, **line})
    return out


def goalie_rows(conn, season, min_faced=0, ids=None):
    """Luck figures for goalies who have faced shots this season; `enough` marks luck.MIN_FACED or more."""
    where, params = ["f.faced >= %(min_faced)s"], {"season": season, "min_faced": max(0, min_faced)}
    if ids is not None:
        where.append("f.player_id = ANY(%(ids)s)")
        params["ids"] = list(ids)
    rows = conn.execute(
        f"""WITH {GOALIE_CALIBRATION_CTE}
            SELECT f.*, g.name, g.team, g.games_played FROM (
                SELECT goalie_id AS player_id, count(*) AS faced, count(*) FILTER (WHERE kind = 'goal') AS goals,
                       count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals,
                       coalesce(sum({GOALIE_XG}), 0) AS xga,
                       coalesce(sum({GOALIE_XG} * (1 - {GOALIE_XG})), 0) AS variance
                FROM shot JOIN gcal USING (season_id)
                WHERE season_id = %(season)s AND goalie_id IS NOT NULL AND kind IN ('shot', 'goal')
                GROUP BY goalie_id) f
            JOIN goalie_season g ON g.player_id = f.player_id AND g.season_id = %(season)s
            WHERE {' AND '.join(where)}""", params).fetchall()
    return [{"player_id": r["player_id"], "name": r["name"], "team": r["team"], "games_played": r["games_played"],
             "faced": r["faced"], "goals": r["goals"], "xga": r["xga"], "enough": r["faced"] >= luck.MIN_FACED,
             **luck.goalie_line(r)} for r in rows]


def _seasons_sql(who, kinds, goalie=False):
    """Per-season shot totals for one player (`who` is shooter_id or goalie_id), past seasons and this one together,
    each calibrated as described above (skater and goalie calibration differ)."""
    if goalie:
        cal = GOALIE_CALIBRATION_CTE
        source = f"""SELECT season_id, {who}, kind, {GOALIE_XG} AS xg FROM shot_hist JOIN gcal USING (season_id)
                     UNION ALL SELECT season_id, {who}, kind, {GOALIE_XG} AS xg FROM shot JOIN gcal USING (season_id)
                     WHERE shot.season_id NOT IN {NOT_ARCHIVED}"""
    else:
        cal = CALIBRATION_CTE
        source = f"""SELECT h.season_id, {who}, kind, xg * f AS xg FROM shot_hist h JOIN cal USING (season_id)
                     UNION ALL SELECT season_id, {who}, kind, xg FROM shot WHERE season_id NOT IN {NOT_ARCHIVED}"""
    return f"""WITH {cal}
               SELECT season_id, count(*) FILTER (WHERE kind <> 'block') AS attempts,
                      count(*) FILTER (WHERE kind IN ('shot', 'goal')) AS shots_on_goal,
                      count(*) FILTER (WHERE kind = 'goal') AS goals,
                      count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals,
                      coalesce(sum(xg), 0) AS xg, coalesce(sum(xg * (1 - xg)), 0) AS variance
               FROM ({source}) t
               WHERE {who} = %s AND kind IN ({kinds}) GROUP BY season_id ORDER BY season_id"""


def skater_history(conn, player_id):
    """Season-by-season finishing for a skater: goals against the xG of their shots, with a z-score for each season
    and for all of them together. Empty when the player has no stored shots."""
    rows = conn.execute(_seasons_sql("shooter_id", "'shot', 'miss', 'goal'"), (player_id,)).fetchall()
    out = []
    for r in rows:
        out.append({"season_id": r["season_id"], "attempts": r["attempts"], "goals": r["goals"], "xg": r["xg"],
                    "diff": r["model_goals"] - r["xg"], "z": luck.z_score(r["model_goals"], r["xg"], r["variance"])})
    total = {k: sum(r[k] for r in rows) for k in ("attempts", "goals", "model_goals", "xg", "variance")}
    career = None
    if rows:
        career = {"attempts": total["attempts"], "goals": total["goals"], "xg": total["xg"],
                  "diff": total["model_goals"] - total["xg"],
                  "z": luck.z_score(total["model_goals"], total["xg"], total["variance"])}
    return {"seasons": out, "career": career}


def goalie_history(conn, player_id):
    """Season-by-season goals saved above expected for a goalie, with a z-score for each season and all together."""
    rows = conn.execute(_seasons_sql("goalie_id", "'shot', 'goal'", goalie=True), (player_id,)).fetchall()
    out = []
    for r in rows:
        z = luck.z_score(r["model_goals"], r["xg"], r["variance"])
        out.append({"season_id": r["season_id"], "faced": r["shots_on_goal"], "goals": r["goals"], "xga": r["xg"],
                    "gsax": r["xg"] - r["model_goals"], "z": None if z is None else -z})
    total = {k: sum(r[k] for r in rows) for k in ("shots_on_goal", "goals", "model_goals", "xg", "variance")}
    career = None
    if rows:
        z = luck.z_score(total["model_goals"], total["xg"], total["variance"])
        career = {"faced": total["shots_on_goal"], "goals": total["goals"], "xga": total["xg"],
                  "gsax": total["xg"] - total["model_goals"], "z": None if z is None else -z}
    return {"seasons": out, "career": career}


def persistence(conn):
    """How much of a season's finishing (or goaltending) carries into the next: the correlation, across players with
    big enough samples in both seasons, between one season's gap to xG and the next season's. Uses the stored past
    seasons only, so partial current-season samples don't muddy it. Near 0 means mostly luck, near 1 mostly skill."""
    def pairs(rows, rate):
        by = {(r["player_id"], r["season_id"]): rate(r) for r in rows}
        found = [(v, by[(p, s + 10001)]) for (p, s), v in by.items() if (p, s + 10001) in by]
        return {"r": luck.pearson([a for a, _ in found], [b for _, b in found]), "n": len(found)}

    skaters = conn.execute(
        f"""WITH {CALIBRATION_CTE}
           SELECT shooter_id AS player_id, season_id, count(*) FILTER (WHERE kind <> 'block') AS attempts,
                  count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals, coalesce(sum(xg * f), 0) AS xg
           FROM shot_hist h JOIN cal USING (season_id) WHERE shooter_id IS NOT NULL GROUP BY shooter_id, season_id
           HAVING count(*) FILTER (WHERE kind <> 'block') >= %s""", (luck.MIN_PERSIST_ATTEMPTS,)).fetchall()
    goalies = conn.execute(
        f"""WITH {GOALIE_CALIBRATION_CTE}
           SELECT goalie_id AS player_id, season_id, count(*) AS faced,
                  count(*) FILTER (WHERE kind = 'goal' AND xg IS NOT NULL) AS model_goals, coalesce(sum({GOALIE_XG}), 0) AS xg
           FROM shot_hist JOIN gcal USING (season_id) WHERE goalie_id IS NOT NULL AND kind IN ('shot', 'goal')
           GROUP BY goalie_id, season_id
           HAVING count(*) >= %s""", (luck.MIN_PERSIST_FACED,)).fetchall()
    return {
        "skaters": pairs(skaters, lambda r: (r["model_goals"] - r["xg"]) / r["attempts"] * 100),
        "goalies": pairs(goalies, lambda r: (r["xg"] - r["model_goals"]) / r["faced"] * 100),
    }
