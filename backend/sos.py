"""Schedule strength: how hard each team's remaining (and played) games are.

Every game is priced with the same on-paper model as the What to watch page (tonight.matchup: expected-goal ratings, home ice), so
the numbers agree with it. A team's schedule effect is its expected points over the games in question minus what it would expect
against a league-average opponent at the same venues, so a positive figure means a softer schedule than average and a negative one
a harder one; home and road mix is not part of it. Expected points per game are 2p + (1 - p) x OT_RATE (the winner takes 2, and the
loser 1 when the game goes past regulation).

Early in a season the ratings are pulled hard toward average (matchups.team_ratings), and almost every team has most of its schedule
left, so the spread between teams is small; it grows as games are played. Reading it as a ranking of difficulty is the point, not
the points: a few tenths of a point is noise.
"""
import tonight

OT_RATE = 0.23
AVERAGE = {"off_ratio": 1.0, "def_ratio": 1.0}
DONE = ("OFF", "FINAL")


def exp_points(p):
    return 2 * p + (1 - p) * OT_RATE


def _price(team, opp, home, ratings, league):
    """(team's win chance, the same against an average opponent at the same venue), or None when a rating is missing."""
    if team not in ratings or (opp not in ratings):
        return None
    if home:
        p, avg = tonight.matchup(ratings[team], ratings[opp], league)[0], tonight.matchup(ratings[team], AVERAGE, league)[0]
    else:
        p, avg = 1 - tonight.matchup(ratings[opp], ratings[team], league)[0], 1 - tonight.matchup(AVERAGE, ratings[team], league)[0]
    return p, avg


def net(r):
    """A team's expected-goal margin per game from its stored xG for and against."""
    return r["xgf_pg"] - r["xga_pg"]


def _block(games, ratings, league):
    """Totals over a list of (opp, home) games for one team."""
    got = [(g, _price(g["team"], g["opp"], g["home"], ratings, league)) for g in games]
    got = [(g, pr) for g, pr in got if pr]
    if not got:
        return {"games": len(games), "home": sum(1 for g in games if g["home"]), "away": sum(1 for g in games if not g["home"]),
                "opp_net": None, "exp_points": None, "schedule_points": None}
    exp = sum(exp_points(p) for _, (p, _) in got)
    avg = sum(exp_points(a) for _, (_, a) in got)
    return {"games": len(games), "home": sum(1 for g in games if g["home"]), "away": sum(1 for g in games if not g["home"]),
            "opp_net": round(sum(net(ratings[g["opp"]]) for g, _ in got) / len(got), 3),
            "exp_points": round(exp, 2), "schedule_points": round(exp - avg, 2)}


def team_rows(ratings, games, league, next_n=10):
    """One row per team in `ratings` ({abbrev: team_table row}) from every game of the season (dicts with date, home, away, state).

    Each row has played, left and next (the next `next_n` games) blocks (games, home, away, opp_net, exp_points, schedule_points) and
    back_to_backs_left, the remaining games played the night after another game."""
    by_team = {}
    for g in sorted(games, key=lambda g: (g["date"], g["game_id"] if "game_id" in g else 0)):
        done = g["state"] in DONE
        for team, opp, home in ((g["home"], g["away"], True), (g["away"], g["home"], False)):
            by_team.setdefault(team, []).append({"team": team, "opp": opp, "home": home, "date": g["date"], "done": done})
    rows = []
    for team in sorted(ratings):
        mine = by_team.get(team, [])
        left = [g for g in mine if not g["done"]]
        played = [g for g in mine if g["done"]]
        b2b = sum(1 for prev, cur in zip(mine, mine[1:]) if not cur["done"] and (cur["date"] - prev["date"]).days == 1)
        rows.append({"team": team, "played": _block(played, ratings, league), "left": _block(left, ratings, league),
                     "next": _block(left[:next_n], ratings, league), "back_to_backs_left": b2b})
    return rows
