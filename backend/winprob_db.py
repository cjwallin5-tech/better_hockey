"""Database side of winprob.py: team ratings going into a game, from the finished games before it."""
import winprob


def gap_before(conn, season, date, home, away):
    """The home team's rating minus the away team's from games finished before `date` this season (0 for a team with no games yet)."""
    rows = conn.execute(
        """SELECT home, away, home_score, away_score FROM game
           WHERE season_id = %s AND game_date < %s AND state IN ('OFF', 'FINAL') AND home_score IS NOT NULL
             AND (home = ANY(%s) OR away = ANY(%s))""", (season, date, [home, away], [home, away])).fetchall()
    # ratings() pulls each team toward zero by its own games only, so the other teams in those games are harmless; restrict to the two teams' lines
    rate = winprob.ratings([(r["home"], r["away"], r["home_score"], r["away_score"]) for r in rows])
    return rate.get(home, 0.0) - rate.get(away, 0.0)
