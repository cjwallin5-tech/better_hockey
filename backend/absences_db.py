"""Database side of absences.py: this season's regulars who are out, and what their teammates are getting in the games they missed.
Shared by the API and the daily email."""
from collections import defaultdict

import absences

MIN_TOP_SECONDS = {"F": 1080, "D": 1380}   # a player without power-play time still counts as a top-role absence at this ice time (18 / 23 minutes)
SHOWN = 8                                  # teammates listed per absence
SEEN_MIN_GAMES = 2                         # games in the absence before what teammates actually got outranks the average


def _load(conn, season):
    """({team: {game_id: {player_id: {ev, pp, sh, position}}}}, {team: [game ids oldest first]})."""
    games = defaultdict(lambda: defaultdict(dict))
    dates = {}
    for r in conn.execute(
            """SELECT game_id, game_date, team, player_id, position, ev_sec, pp_sec, sh_sec FROM skater_game_toi WHERE season_id = %s""", (season,)):
        games[r["team"]][r["game_id"]][r["player_id"]] = {"ev": r["ev_sec"], "pp": r["pp_sec"], "sh": r["sh_sec"], "position": r["position"]}
        dates[r["game_id"]] = r["game_date"]
    order = {t: sorted(g, key=lambda x: (dates[x], x)) for t, g in games.items()}
    return games, order, dates


def current(conn, season):
    """[{player_id, name, team, position, games_out, last_played, role, base, teammates}] for the regulars who missed their team's latest
    game(s) and are top-role players (see absences), most important first. teammates are the same-position-group players who played while he
    was out: {player_id, name, base_total, base_pp, expected: {ev, pp, total}, seen: None | {games, ev, pp, total}} best first."""
    games, order, dates = _load(conn, season)
    names = {r["player_id"]: r for r in conn.execute(
        "SELECT player_id, name, team, position FROM skater_season WHERE season_id = %s", (season,))}
    out = []
    for team, gm in games.items():
        for ab in absences.current_absences(gm, order[team]):
            x = ab["player"]
            info = names.get(x)
            if not info or (info["team"] or "").split(",")[-1] != team:     # traded or gone: not "out" for this team
                continue
            base = absences.baseline(gm, ab["base_games"], x)
            if not base:
                continue
            g = absences.group(info["position"])
            role = absences.role(base["pp"])
            if role == "none" and base["total"] < MIN_TOP_SECONDS[g]:
                continue
            mates = []
            for y in {p for gid in ab["absent_games"] for p in gm[gid]}:
                yi = names.get(y)
                if y == x or not yi or absences.group(yi["position"]) != g:
                    continue
                eff = absences.effect(gm, ab, y)
                if not eff:
                    continue
                ev, pp = absences.expected_change(g, {"pp": base["pp"]}, g, {"pp": eff["base"]["pp"]})
                seen = {"games": eff["games"], **{k: eff["change"][k] for k in ("ev", "pp", "total")}}
                mates.append({"player_id": y, "name": yi["name"], "base_total": eff["base"]["total"], "base_pp": eff["base"]["pp"],
                              "expected": {"ev": ev, "pp": pp, "total": ev + pp}, "seen": seen})
            key = lambda m: (m["seen"]["total"] if m["seen"]["games"] >= SEEN_MIN_GAMES else m["expected"]["total"], m["name"])
            mates.sort(key=lambda m: (-key(m)[0], m["name"]))
            out.append({"player_id": x, "name": info["name"], "team": team, "position": info["position"], "games_out": ab["games_out"],
                        "last_played": dates[order[team][len(order[team]) - 1 - ab["games_out"]]], "role": role,
                        "base": {k: base[k] for k in ("ev", "pp", "sh", "total")}, "teammates": mates[:SHOWN]})
    out.sort(key=lambda a: (-a["base"]["total"] - 600 * (a["role"] == "PP1") - 300 * (a["role"] == "PP2"), a["name"]))
    return out
