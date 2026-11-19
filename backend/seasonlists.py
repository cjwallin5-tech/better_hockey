"""Season lists: who made their NHL debut in a season, who played their last, and who wore a sweater number."""
import sweaters

# One row per player whose first (or last) NHL season is the one asked for, with that season's team and games and the career totals.
# A player's last season is the latest in any season table we hold; the current season is never final, and neither is anyone still active.
_LAST_SEASONS = """
    SELECT player_id, max(season_id) AS season_id FROM (
        SELECT player_id, season_id FROM career_season
        UNION ALL SELECT player_id, season_id FROM goalie_season
        UNION ALL SELECT player_id, season_id FROM player_number) s GROUP BY player_id"""

_PEOPLE = """
    SELECT player_id, name, position, 'skater' AS kind, first_season, active_season, games_played, points AS career_points, NULL::int AS career_wins
      FROM career_skater WHERE game_type = 2
    UNION ALL
    SELECT player_id, name, 'G', 'goalie', first_season, active_season, games_played, NULL, wins FROM career_goalie WHERE game_type = 2"""

_SEASON_LINE = """
    SELECT player_id, season_id, string_agg(DISTINCT team, ', ') AS team, sum(games_played) AS gp FROM (
        SELECT player_id, season_id, team, games_played FROM career_season
        UNION ALL SELECT player_id, season_id, team, games_played FROM goalie_season) x GROUP BY player_id, season_id"""


def _list(conn, where, season, season_col):
    sql = f"""
        WITH people AS ({_PEOPLE}), last AS ({_LAST_SEASONS}), line AS ({_SEASON_LINE})
        SELECT p.player_id, p.name, p.position, p.kind, p.first_season, p.active_season, l.season_id AS last_season, ln.team, ln.gp,
               p.games_played AS career_gp, p.career_points, p.career_wins
          FROM people p JOIN last l USING (player_id)
          LEFT JOIN line ln ON ln.player_id = p.player_id AND ln.season_id = {season_col}
         WHERE {where}
         ORDER BY p.games_played DESC NULLS LAST, p.name"""
    return conn.execute(sql, {"season": season}).fetchall()


def debuts(conn, season):
    """Players whose first NHL season is `season`, the ones with the longest careers first."""
    return _list(conn, "p.first_season = %(season)s", season, "p.first_season")


def finals(conn, season, current_season):
    """Players whose last NHL season is `season`; none for the season in progress, and anyone still active is left out."""
    if season >= current_season:
        return []
    return _list(conn, "l.season_id = %(season)s AND p.active_season IS NULL", season, "l.season_id")


def numbers(conn):
    """{number: how many players have worn it}."""
    return dict(conn.execute("SELECT number, count(DISTINCT player_id) FROM player_number GROUP BY number").fetchall())


def number_history(conn, number):
    """Everyone who has worn `number`, with the teams and seasons."""
    rows = conn.execute(
        "SELECT player_id, season_id, team, name, position FROM player_number WHERE number = %s", (number,)).fetchall()
    return sweaters.wearers(rows)
