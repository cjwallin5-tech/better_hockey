"""Database side of scorestate.py: the score before every shot, worked out in SQL from each game's own goals.

`shot` holds the current season in full and `shot_hist` the past seasons (see luck_db for why the current table only counts
for seasons not archived yet). Past seasons need ingest.py backfill-shot-times to have run; only timed games are used.
"""
import scorestate as ss

# Every attempt with the shooting team's lead before it. home_before/away_before count the goals ahead of the event in
# (time, event id) order, goals of every kind and strength included, so the filters below don't change the score.
SCORED_CTE = """
shots AS (
    SELECT s.game_id, s.event_id, s.season_id, s.period, s.time_sec, (s.team = g.home) AS is_home, s.team, s.opponent,
           s.kind, s.xg, s.strength, s.empty_net, s.shooter_id
    FROM shot s JOIN game g USING (game_id)
    WHERE s.season_id = ANY(%(seasons)s) AND s.season_id NOT IN (SELECT season_id FROM shot_hist_game)
    UNION ALL
    SELECT h.game_id, h.event_id, h.season_id, h.period, h.time_sec, h.is_home, t.team, t.opponent,
           h.kind, h.xg, h.strength, h.empty_net, h.shooter_id
    FROM shot_hist h
    JOIN shot_hist_game hg ON hg.game_id = h.game_id AND hg.timed
    JOIN team_game_hist t ON t.game_id = h.game_id AND t.is_home = h.is_home
    WHERE h.season_id = ANY(%(seasons)s)
),
scored AS (
    SELECT *, CASE WHEN is_home THEN home_before - away_before ELSE away_before - home_before END AS diff
    FROM (
        SELECT *,
               coalesce(sum(CASE WHEN kind = 'goal' AND is_home THEN 1 ELSE 0 END)
                        OVER w, 0) AS home_before,
               coalesce(sum(CASE WHEN kind = 'goal' AND NOT is_home THEN 1 ELSE 0 END)
                        OVER w, 0) AS away_before
        FROM shots
        WINDOW w AS (PARTITION BY game_id ORDER BY time_sec, event_id ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
    ) x
)
"""

EVEN = "kind IN ('shot', 'miss', 'goal') AND strength = 'ev' AND period <= 3"


def team_tallies(conn, seasons):
    """{team: scorestate.Tally} over the seasons, even strength and regulation, from the team's own point of view."""
    out = {}

    def tally(team):
        return out.setdefault(team, ss.Tally())

    for who, side in (("team", "f"), ("opponent", "a")):
        rows = conn.execute(
            f"""WITH {SCORED_CTE}
                SELECT {who} AS team, least(2, greatest(-2, diff)) AS d, count(*) AS att,
                       count(*) FILTER (WHERE kind = 'goal') AS goals,
                       coalesce(sum(xg) FILTER (WHERE NOT coalesce(empty_net, false)), 0) AS xg
                FROM scored WHERE {EVEN} GROUP BY 1, 2""", {"seasons": list(seasons)}).fetchall()
        for r in rows:
            state = ss.state_of(r["d"])
            if side == "a":                      # the shooter's lead seen from the other side of the ice
                state = ss.MIRROR[state]
            store = getattr(tally(r["team"]), side)
            store["att"][state] += r["att"]
            store["goals"][state] += r["goals"]
            store["xg"][state] += float(r["xg"])
    return out


def player_shots(conn, player_id, seasons):
    """One skater's own attempts with the lead before each (all strengths, regulation and overtime), season by season."""
    return conn.execute(
        f"""WITH {SCORED_CTE}
            SELECT season_id, period, kind, xg, empty_net, strength, diff
            FROM scored WHERE shooter_id = %(p)s AND kind IN ('shot', 'miss', 'goal')""",
        {"seasons": list(seasons), "p": player_id}).fetchall()


def all_player_shots(conn, seasons):
    """Every skater's attempts, for the league-wide checks (backtest and the share of players beyond chance)."""
    return conn.execute(
        f"""WITH {SCORED_CTE}
            SELECT season_id, shooter_id, period, kind, xg, empty_net, strength, diff
            FROM scored WHERE shooter_id IS NOT NULL AND kind IN ('shot', 'miss', 'goal')""",
        {"seasons": list(seasons)}).fetchall()
