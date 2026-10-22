"""Back-to-backs: how teams do on the second night of one, and which upcoming games have a rest mismatch.

A team's rest before a game is the days since its previous game (1 = it played yesterday). Each game is then one of:
  tired   the team is on the second night of a back-to-back and the opponent is rested (2+ days)
  edge    the team is rested and the opponent is on the second night of a back-to-back
  both    both teams played yesterday
  normal  both rested
The effect of each is the average, over teams, of the gap between a team's results in those games and the SAME
team's results in normal games, so a good team isn't mistaken for a rested one (see analysis/back_to_back_effects.py,
which found a real effect for tired and edge games and none for both, nor for goalies with the data we have).
"""
import math
from collections import defaultdict

import arenas

MIN_GAMES_EACH = 5   # a team needs this many games in both groups to count toward an effect
EFFECT_FIELDS = ("points", "goal_diff", "win_rate", "goals_for", "goals_against")
FIRST_GAME_REST = 9  # rest assumed before a team's first game of a season


def rest_days(games):
    """games: dicts with team, season_id, game_id, game_date. Returns {(team, game_id): days since the team's
    previous game in the same season}, FIRST_GAME_REST for its first."""
    by_team = defaultdict(list)
    for g in games:
        by_team[g["team"], g["season_id"]].append(g)
    out = {}
    for lst in by_team.values():
        prev = None
        for g in sorted(lst, key=lambda g: (g["game_date"], g["game_id"])):
            out[g["team"], g["game_id"]] = (g["game_date"] - prev).days if prev else FIRST_GAME_REST
            prev = g["game_date"]
    return out


def kind(rest, opp_rest):
    """tired / edge / both / normal, from one team's point of view (see the module docstring)."""
    if rest == 1:
        return "both" if opp_rest == 1 else "tired"
    return "edge" if opp_rest == 1 else "normal"


def _mean(xs):
    return sum(xs) / len(xs)


def _se(xs):
    if len(xs) < 2:
        return None
    m = _mean(xs)
    return math.sqrt(sum((v - m) ** 2 for v in xs) / (len(xs) - 1) / len(xs))


def classify(results, rest):
    """results: dicts with team, opponent, game_id, points, wins, goals_for, goals_against for finished games.
    Yields each result with its `kind`; games whose rest isn't known are skipped."""
    for r in results:
        mine, theirs = rest.get((r["team"], r["game_id"])), rest.get((r["opponent"], r["game_id"]))
        if mine is not None and theirs is not None:
            yield {**r, "kind": kind(mine, theirs)}


def effects(classified):
    """{kind: {games, teams, points, goal_diff, win_rate, goals_for, goals_against}} where each figure is {gap, se}: the
    average over teams of (the team's per-game figure in these games) minus (the same in normal games)."""
    per_team = defaultdict(lambda: defaultdict(list))
    for r in classified:
        per_team[r["team"]][r["kind"]].append((r["points"], r["goals_for"] - r["goals_against"], r["wins"], r["goals_for"], r["goals_against"]))
    out = {}
    for k in ("tired", "edge", "both"):
        gaps = defaultdict(list)
        games = 0
        for groups in per_team.values():
            a, b = groups.get(k, []), groups.get("normal", [])
            games += len(a)
            if len(a) < MIN_GAMES_EACH or len(b) < MIN_GAMES_EACH:
                continue
            for i, name in enumerate(EFFECT_FIELDS):
                gaps[name].append(_mean([x[i] for x in a]) - _mean([x[i] for x in b]))
        n = len(gaps["points"])
        out[k] = {"games": games, "teams": n,
                  **{name: {"gap": _mean(gaps[name]) if gaps[name] else None, "se": _se(gaps[name])} for name in EFFECT_FIELDS}}
    return out


def _line(rows):
    gp = len(rows)
    return {"games": gp, "wins": sum(r["wins"] for r in rows),
            "points_pct": sum(r["points"] for r in rows) / (2 * gp) if gp else None,
            "goal_diff_per_game": sum(r["goals_for"] - r["goals_against"] for r in rows) / gp if gp else None}


def team_lines(classified):
    """{team: {kind: line}} with games, wins, points % and goal difference per game for tired, edge and normal games."""
    per = defaultdict(lambda: defaultdict(list))
    for r in classified:
        per[r["team"]][r["kind"]].append(r)
    return {t: {k: _line(per[t][k]) for k in ("tired", "edge", "normal")} for t in per}


def upcoming(fixtures, rest):
    """fixtures: dicts with game_id, game_date, home, away for games still to play. Returns each with both teams'
    rest and `mismatch`: 'home_tired', 'away_tired', 'both' or None."""
    out = []
    for f in fixtures:
        h, a = rest.get((f["home"], f["game_id"])), rest.get((f["away"], f["game_id"]))
        if h is None or a is None:
            continue
        mismatch = None
        if h == 1 and a == 1:
            mismatch = "both"
        elif h == 1:
            mismatch = "home_tired"
        elif a == 1:
            mismatch = "away_tired"
        out.append({**f, "home_rest": h, "away_rest": a, "mismatch": mismatch})
    return out


def travel(games):
    """games: dicts with team, opponent, season_id, game_id, game_date and is_home (True at home). Returns
    {(team, game_id): {km, hours_east, road_game, home_stand}}:
      km          distance from where the team's previous game was played (its own arena before its first game)
      hours_east  time zones crossed to get here, positive eastward (a 7 pm game after flying east is a 4 pm body clock)
      road_game   how many road games in a row this is (0 at home)
      home_stand  how many home games in a row this is (0 on the road)
    A game is taken to be played at the home team's arena (see arenas.py)."""
    by_team = defaultdict(list)
    for g in games:
        by_team[g["team"], g["season_id"]].append(g)
    out = {}
    for (team, _), lst in by_team.items():
        where, road, stand = team, 0, 0
        for g in sorted(lst, key=lambda g: (g["game_date"], g["game_id"])):
            here = team if g["is_home"] else g["opponent"]
            if g["is_home"]:
                road, stand = 0, stand + 1
            else:
                road, stand = road + 1, 0
            out[team, g["game_id"]] = {
                "km": arenas.distance_km(where, here),
                "hours_east": arenas.utc_offset_hours(here, g["game_date"]) - arenas.utc_offset_hours(where, g["game_date"]),
                "road_game": road, "home_stand": stand,
            }
            where = here
    return out
