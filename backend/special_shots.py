"""A team's shootouts and penalty shots this season, from the play-by-play read by ingest.ingest_play_by_play: its shootout record, who shot
and who made the saves, and every penalty shot it took or faced."""


def team_view(conn, season, abbrev):
    """{shootout: {wins, losses}, shooters: [...], goalies: [...], penalty_shots: [...]}; every list is empty for a team with none."""
    rows = conn.execute(
        """SELECT s.kind, s.team AS shooting_team, s.shooter_id, s.goalie_id, s.scored, s.on_goal, g.game_date,
                  CASE WHEN g.home = s.team THEN g.away ELSE g.home END AS opponent,
                  sk.name AS shooter, gk.name AS goalie
           FROM special_shot s
           JOIN game g ON g.game_id = s.game_id
           LEFT JOIN skater_season sk ON sk.player_id = s.shooter_id AND sk.season_id = s.season_id
           LEFT JOIN goalie_season gk ON gk.player_id = s.goalie_id AND gk.season_id = s.season_id
           WHERE s.season_id = %(season)s AND (g.home = %(abbrev)s OR g.away = %(abbrev)s)
           ORDER BY g.game_date, s.game_id, s.event_id""", {"season": season, "abbrev": abbrev}).fetchall()
    record = conn.execute(
        """SELECT count(*) FILTER (WHERE (home = %(a)s AND home_score > away_score) OR (away = %(a)s AND away_score > home_score)) AS wins,
                  count(*) FILTER (WHERE (home = %(a)s AND home_score < away_score) OR (away = %(a)s AND away_score < home_score)) AS losses
           FROM game WHERE season_id = %(season)s AND last_period = 'SO' AND state IN ('OFF', 'FINAL') AND (home = %(a)s OR away = %(a)s)""",
        {"a": abbrev, "season": season}).fetchone()

    shooters, goalies, penalty = {}, {}, []
    for r in rows:
        mine = r["shooting_team"] == abbrev          # this team shot; otherwise it was in goal
        if r["kind"] == "shootout":
            if mine and r["shooter_id"] is not None:
                e = shooters.setdefault(r["shooter_id"], {"player_id": r["shooter_id"], "name": r["shooter"], "attempts": 0, "goals": 0})
                e["attempts"] += 1
                e["goals"] += r["scored"]
            elif not mine and r["goalie_id"] is not None and r["on_goal"]:
                e = goalies.setdefault(r["goalie_id"], {"player_id": r["goalie_id"], "name": r["goalie"], "faced": 0, "saves": 0})
                e["faced"] += 1
                e["saves"] += not r["scored"]
        else:
            penalty.append({"game_date": r["game_date"], "opponent": r["opponent"], "taken": mine, "scored": r["scored"],
                            "shooter_id": r["shooter_id"], "shooter": r["shooter"], "goalie_id": r["goalie_id"], "goalie": r["goalie"]})
    by_goals = lambda e: (-e.get("goals", 0), -e.get("attempts", 0), e["name"] or "")
    return {"shootout": {"wins": record["wins"], "losses": record["losses"]},
            "shooters": sorted(shooters.values(), key=by_goals),
            "goalies": sorted(goalies.values(), key=lambda e: (-e["saves"], -e["faced"], e["name"] or "")),
            "penalty_shots": penalty}
