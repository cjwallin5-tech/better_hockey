"""Database side of specialteams.py: team special-teams sums and each skater's share of their team's power-play and
penalty-kill time. Functions take an open psycopg connection that returns dict rows. `last` limits everything to each
team's most recent N games (0 = the whole season so far)."""
import specialteams

_SELECTED = """
    tg AS (SELECT game_id, team, row_number() OVER (PARTITION BY team ORDER BY game_date DESC, game_id DESC) AS rn
           FROM (SELECT DISTINCT game_id, team, game_date FROM skater_game_toi WHERE season_id = %(season)s) x),
    sel AS (SELECT game_id, team FROM tg WHERE %(last)s = 0 OR rn <= %(last)s)"""


def team_rows(conn, season, last=0):
    """[{team, games, ...specialteams.team_line figures}] for every team with stored ice time."""
    rows = conn.execute(
        f"""WITH {_SELECTED},
            tt AS (SELECT t.team, count(DISTINCT t.game_id) AS games, sum(t.pp_sec) / 5.0 AS pp_sec, sum(t.sh_sec) / 4.0 AS sh_sec
                   FROM skater_game_toi t JOIN sel USING (game_id, team) WHERE t.season_id = %(season)s GROUP BY t.team),
            pp AS (SELECT s.team, coalesce(sum(s.xg), 0)::float AS xg, count(*) FILTER (WHERE s.kind = 'goal') AS goals,
                          count(*) FILTER (WHERE s.kind IN ('shot', 'goal')) AS shots
                   FROM shot s JOIN sel ON sel.game_id = s.game_id AND sel.team = s.team
                   WHERE s.season_id = %(season)s AND s.strength = 'pp' GROUP BY s.team),
            pk AS (SELECT s.opponent AS team, coalesce(sum(s.xg), 0)::float AS xg, count(*) FILTER (WHERE s.kind = 'goal') AS goals,
                          count(*) FILTER (WHERE s.kind IN ('shot', 'goal')) AS shots
                   FROM shot s JOIN sel ON sel.game_id = s.game_id AND sel.team = s.opponent
                   WHERE s.season_id = %(season)s AND s.strength = 'pp' GROUP BY s.opponent)
            SELECT tt.team, tt.games, tt.pp_sec::float, tt.sh_sec::float,
                   coalesce(pp.xg, 0) AS pp_xg, coalesce(pp.goals, 0) AS pp_goals, coalesce(pp.shots, 0) AS pp_shots,
                   coalesce(pk.xg, 0) AS pk_xg, coalesce(pk.goals, 0) AS pk_goals, coalesce(pk.shots, 0) AS pk_shots
            FROM tt LEFT JOIN pp ON pp.team = tt.team LEFT JOIN pk ON pk.team = tt.team""",
        {"season": season, "last": last}).fetchall()
    return [{"team": r["team"], **specialteams.team_line(r)} for r in rows]


def team_players(conn, season, team, last=0):
    """Each skater who played for the team in the window: share of its power-play and penalty-kill time, games, and the
    season's power-play goals and points."""
    return conn.execute(
        f"""WITH {_SELECTED},
            tt AS (SELECT t.game_id, sum(t.pp_sec) / 5.0 AS pp, sum(t.sh_sec) / 4.0 AS sh
                   FROM skater_game_toi t JOIN sel USING (game_id, team)
                   WHERE t.season_id = %(season)s AND t.team = %(team)s GROUP BY t.game_id)
            SELECT t.player_id, s.name, coalesce(s.position, max(t.position)) AS position, count(*) AS games,
                   sum(t.pp_sec) AS pp_sec, sum(t.sh_sec) AS sh_sec,
                   (sum(t.pp_sec) / nullif(sum(tt.pp), 0))::float AS pp_share,
                   (sum(t.sh_sec) / nullif(sum(tt.sh), 0))::float AS pk_share,
                   s.pp_goals, s.pp_points
            FROM skater_game_toi t JOIN sel USING (game_id, team) JOIN tt USING (game_id)
                 LEFT JOIN skater_season s ON s.player_id = t.player_id AND s.season_id = %(season)s
            WHERE t.season_id = %(season)s AND t.team = %(team)s
            GROUP BY t.player_id, s.name, s.position, s.pp_goals, s.pp_points""",
        {"season": season, "team": team, "last": last}).fetchall()
