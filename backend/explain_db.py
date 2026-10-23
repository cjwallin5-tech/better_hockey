"""Database side of explain.py: gathers one skater's facts from the stored season, shot, ice-time and line data.
Functions take an open psycopg connection that returns dict rows."""
import config
import explain
import luck_db
import roles_db

ROLE_WINDOW = 5
LINEMATES_SHOWN = 3


def _last_season_shots(conn, player_id, season):
    """Last season's shot attempts (not counting blocked ones) and their expected goals, from the stored shots."""
    r = conn.execute(
        """SELECT count(*) FILTER (WHERE kind <> 'block') AS attempts,
                  coalesce(sum(xg) FILTER (WHERE kind <> 'block'), 0)::float AS ixg
           FROM shot_hist WHERE season_id = %s AND shooter_id = %s""", (season, player_id)).fetchone()
    return r["attempts"], r["ixg"]


def _linemates(conn, player_id, team, position):
    """The player's most common 5v5 partners this season and over their last few games: forward lines for forwards,
    the defense pair for defensemen. Each is {id, name, share (of their 5v5 time), ppg}."""
    table, cols = ("pair_game", ("p1", "p2")) if position == "D" else ("line_game", ("p1", "p2", "p3"))
    arr = ", ".join(cols)
    recent_games = [r["game_id"] for r in conn.execute(
        "SELECT game_id FROM skater_game WHERE player_id = %s AND season_id = %s ORDER BY game_date DESC, game_id DESC LIMIT %s",
        (player_id, config.SEASON_ID, ROLE_WINDOW))]

    def top(game_ids):
        rows = conn.execute(
            f"""SELECT x AS partner, sum(toi_sec) AS toi FROM {table} l, unnest(ARRAY[{arr}]) x
                WHERE %(p)s IN ({arr}) AND x <> %(p)s AND l.team = %(team)s
                  AND (%(games)s::bigint[] IS NULL OR l.game_id = ANY(%(games)s))
                  AND l.game_id IN (SELECT game_id FROM game WHERE season_id = %(season)s)
                GROUP BY x ORDER BY toi DESC LIMIT %(n)s""",
            {"p": player_id, "team": team, "games": game_ids, "season": config.SEASON_ID, "n": LINEMATES_SHOWN}).fetchall()
        if not rows:
            return []
        info = {r["player_id"]: r for r in conn.execute(
            "SELECT player_id, name, games_played, points FROM skater_season WHERE season_id = %s AND player_id = ANY(%s)",
            (config.SEASON_ID, [r["partner"] for r in rows]))}
        total = sum(r["toi"] for r in rows)
        return [{"id": r["partner"], "name": info[r["partner"]]["name"] if r["partner"] in info else str(r["partner"]),
                 "share": r["toi"] / total if total else None,
                 "ppg": info[r["partner"]]["points"] / info[r["partner"]]["games_played"] if r["partner"] in info and info[r["partner"]]["games_played"] else None}
                for r in rows]

    season = top(None)
    if not season:
        return None
    return {"season": season, "recent": top(recent_games) if recent_games else [], "recent_games": len(recent_games)}


def facts(conn, player_id):
    """The facts explain.explain needs for one skater, or None when they have no stored games this season."""
    me = conn.execute("SELECT * FROM skater_season WHERE season_id = %s AND player_id = %s", (config.SEASON_ID, player_id)).fetchone()
    if not me or not me["games_played"]:
        return None
    games = config.GAMES_PER_SEASON
    lucks = luck_db.skater_rows(conn, config.SEASON_ID, games, ids=[player_id])
    lk = lucks[0] if lucks else None
    prev = config.SEASON_ID - 10001
    cs = conn.execute("SELECT team, games_played, goals, assists, points FROM career_season WHERE player_id = %s AND season_id = %s",
                      (player_id, prev)).fetchone()
    last = None
    if cs:
        attempts, ixg = _last_season_shots(conn, player_id, prev)
        toi = conn.execute("SELECT toi_per_game_sec FROM defense_season WHERE player_id = %s AND season_id = %s", (player_id, prev)).fetchone()
        last = {"gp": cs["games_played"], "goals": cs["goals"], "assists": cs["assists"], "points": cs["points"], "team": cs["team"],
                "toi_sec": toi["toi_per_game_sec"] if toi else None, "attempts": attempts, "ixg": ixg}
    team = (me["team"] or "").split(",")[-1]
    role = roles_db.player_lines(conn, config.SEASON_ID, ROLE_WINDOW, ids=[player_id]).get(player_id)
    return {
        "name": me["name"], "team": team, "position": me["position"], "gp": me["games_played"], "goals": me["goals"],
        "assists": me["assists"], "points": me["points"], "games": games, "last": last,
        "now": {"toi_sec": me["toi_per_game_sec"], "attempts": lk["attempts"] if lk else None, "ixg": lk["ixg"] if lk else None},
        "luck": {"enough": lk["enough"], "diff_adj": lk["diff_adj"], "goals": lk["goals"], "ixg": lk["ixg"], "skill": lk["skill"],
                 "assist_luck": lk["assist_luck"]} if lk else None,
        "role": role, "pp_points_per60": me["pp_points_per60"],
        "linemates": _linemates(conn, player_id, team, me["position"]),
    }


def explanation(conn, player_id):
    """explain.explain for one skater, with the facts it was built from (so the page can show its sources), or None."""
    f = facts(conn, player_id)
    return None if f is None else {**explain.explain(f), "facts": {"last": f["last"], "now": f["now"]}}
