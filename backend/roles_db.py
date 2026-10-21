"""Database side of roles.py: each skater's games with their share of the team's power-play time, run through
roles.role_line. Shared by the API and anything else that wants role changes."""
from collections import defaultdict

import roles


def player_lines(conn, season, window, ids=None):
    """{player_id: row} for skaters with enough games (see roles.role_line): name, team, position, the role figures
    and an overall direction. `ids` limits it to those players."""
    where = "AND t.player_id = ANY(%(ids)s)" if ids is not None else ""
    games = defaultdict(list)
    for r in conn.execute(
        f"""SELECT t.player_id, t.team, t.ev_sec, t.ot_sec, t.pp_sec, t.sh_sec, t.total_sec,
                   CASE WHEN tp.team_pp > 0 THEN (t.pp_sec / tp.team_pp)::float END AS pp_share
            FROM skater_game_toi t
            JOIN (SELECT game_id, team, sum(pp_sec) / 5.0 AS team_pp FROM skater_game_toi
                  WHERE season_id = %(season)s GROUP BY game_id, team) tp USING (game_id, team)
            WHERE t.season_id = %(season)s {where}
            ORDER BY t.player_id, t.game_date, t.game_id""",
        {"season": season, "ids": list(ids) if ids is not None else None},
    ).fetchall():
        games[r["player_id"]].append(r)
    names = {r["player_id"]: r for r in conn.execute(
        "SELECT player_id, name, team, position, games_played FROM skater_season WHERE season_id = %s", (season,))}
    out = {}
    for pid, gs in games.items():
        line = roles.role_line(gs, window)
        if line is None or pid not in names:
            continue
        n = names[pid]
        out[pid] = {"player_id": pid, "name": n["name"], "team": gs[-1]["team"], "position": n["position"],
                    "games_played": n["games_played"], "direction": roles.direction(line), **line}
    return out
