"""Sweater numbers by season and team, from the NHL's team rosters (which go back to 1917), and who wore a number."""


def roster_rows(payload, season_id, team):
    """(player_id, season_id, team, number, name, position) for everyone on a season's roster who has a number."""
    rows = []
    for group in ("forwards", "defensemen", "goalies"):
        for p in payload.get(group) or []:
            if p.get("sweaterNumber") is None:
                continue
            name = f"{p['firstName']['default']} {p['lastName']['default']}"
            rows.append((p["id"], season_id, team, p["sweaterNumber"], name, p.get("positionCode")))
    return rows


def stints(season_teams):
    """[{team, from, to}] from [(season_id, team)]: a run of consecutive seasons with one team is one stint."""
    out = []
    for season, team in sorted(season_teams):
        last = out[-1] if out else None
        if last and last["team"] == team and season - last["to"] == 10001:
            last["to"] = season
        else:
            out.append({"team": team, "from": season, "to": season})
    return out


def wearers(rows):
    """[{player_id, name, position, stints}] from (player_id, season_id, team, name, position) rows of one number, earliest first."""
    by_player = {}
    for pid, season, team, name, position in rows:
        who = by_player.setdefault(pid, {"player_id": pid, "name": name, "position": position, "seasons": []})
        who["seasons"].append((season, team))
    out = [{"player_id": w["player_id"], "name": w["name"], "position": w["position"], "stints": stints(w["seasons"])}
           for w in by_player.values()]
    return sorted(out, key=lambda w: (w["stints"][0]["from"], w["name"]))
