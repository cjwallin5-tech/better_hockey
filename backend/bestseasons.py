"""The best individual seasons in NHL history: every skater-season (back to 1917-18) and goalie-season (from 2005-06, as far back as
goalie seasons are loaded), ranked by any stat, with era-adjusted scoring for skaters. Pure functions over plain dicts; api.py loads
the rows and caches the built board.

Notes that shape the numbers:
- The season in progress is left out (the caller passes `before`): a hot start would top the per-game lists.
- Per-game and percentage stats only count players who played at least half the games of the busiest player of that season
  (`qualifies`), so a handful of games can't top them; Min GP replaces that rule when set.
- Era adjustment is era.py's: goals and assists scaled to today's scoring level, by season and role."""
from collections import defaultdict

import era

QUALIFY_SHARE = 0.5

SKATER_SORTS = {"name", "season_id", "games_played", "goals", "assists", "points", "points_per_game", "adj_goals", "adj_assists",
                "adj_points", "adj_points_per_game", "hits", "blocked_shots", "takeaways", "giveaways"}
GOALIE_SORTS = {"name", "season_id", "games_played", "games_started", "wins", "losses", "ot_losses", "shutouts", "saves", "shots_against",
                "goals_against", "save_pct", "gaa"}
SORTS = {"skater": SKATER_SORTS, "goalie": GOALIE_SORTS}
RATE_SORTS = {"skater": {"points_per_game", "adj_points_per_game"}, "goalie": {"save_pct", "gaa"}}
POSITIONAL = {"name", "season_id"}  # sorts where "tied" means nothing: a place is just the row's position


def last_team(team):
    """A traded player's team is a comma list with the latest last."""
    return (team or "").split(",")[-1].strip() or None


def _qualify(rows):
    """Marks each row `qualifies`: it played at least QUALIFY_SHARE of the games of the busiest player that season."""
    busiest = defaultdict(int)
    for r in rows:
        busiest[r["season_id"]] = max(busiest[r["season_id"]], r["games_played"])
    for r in rows:
        r["qualifies"] = r["games_played"] >= QUALIFY_SHARE * busiest[r["season_id"]]
    return rows


def skater_board(seasons, defense, before):
    """Every skater-season before season `before`. seasons: dicts with player_id, season_id, team, games_played, goals, assists, points,
    name, position, birth_country, hall_of_fame, active_season. defense: {(player_id, season_id): {hits, blocked_shots, takeaways, giveaways}}."""
    everything = [dict(r, role=era.role(r["position"])) for r in seasons]
    rates = era.league_rates(everything)  # measured on every season, including the one in progress, as era-factors does
    fac = era.factors(rates, era.reference_rates(rates, before - 10001))
    rows = []
    for r in everything:
        if r["season_id"] >= before:
            continue
        f = fac.get((r["season_id"], r["role"])) or {}
        gp = r["games_played"]
        adj_g = r["goals"] * f["goals"] if "goals" in f else None
        adj_a = r["assists"] * f["assists"] if "assists" in f else None
        adj_p = adj_g + adj_a if adj_g is not None and adj_a is not None else None
        d = defense.get((r["player_id"], r["season_id"])) or {}
        rows.append({
            "player_id": r["player_id"], "name": r["name"], "position": r["position"], "country": r["birth_country"],
            "team": last_team(r["team"]), "teams": r["team"], "season_id": r["season_id"], "games_played": gp,
            "goals": r["goals"], "assists": r["assists"], "points": r["points"],
            "points_per_game": round(r["points"] / gp, 3) if gp else None,
            "adj_goals": round(adj_g, 1) if adj_g is not None else None, "adj_assists": round(adj_a, 1) if adj_a is not None else None,
            "adj_points": round(adj_p, 1) if adj_p is not None else None,
            "adj_points_per_game": round(adj_p / gp, 3) if adj_p is not None and gp else None,
            "hits": d.get("hits"), "blocked_shots": d.get("blocked_shots"), "takeaways": d.get("takeaways"), "giveaways": d.get("giveaways"),
            "hall_of_fame": r["hall_of_fame"], "active": r["active_season"] is not None,
        })
    return _qualify(rows)


GOALIE_FIELDS = ("games_played", "games_started", "wins", "losses", "ot_losses", "shutouts", "saves", "shots_against", "goals_against",
                 "save_pct", "gaa")


def goalie_board(seasons, before):
    """Every goalie-season before season `before`. seasons: goalie_season rows joined with the goalie's name, birth_country, hall_of_fame
    and active_season."""
    rows = [{"player_id": r["player_id"], "name": r["name"], "position": "G", "country": r["birth_country"], "team": last_team(r["team"]),
             "teams": r["team"], "season_id": r["season_id"], **{k: r[k] for k in GOALIE_FIELDS},
             "hall_of_fame": r["hall_of_fame"], "active": r["active_season"] is not None}
            for r in seasons if r["season_id"] < before and r["games_played"]]
    return _qualify(rows)


def places(rows, key):
    """[(place, tied)] for rows already sorted by `key`: equal values share the first place and are all tied (1, 2, 2, 4). One pass."""
    out = []
    i = 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1][key] == rows[i][key]:
            j += 1
        out.extend([(i + 1, j > i)] * (j - i + 1))
        i = j + 1
    return out


def query(board, kind, *, sort, direction="desc", q="", position="", season_from=None, season_to=None, min_gp=None,
          active=False, hof=False, offset=0, limit=None):
    """The board filtered, sorted and numbered. Returns (rows, total): `total` counts every match, `rows` is the slice from `offset` (up to
    `limit`, or to the end) with `place` and `tied` added to each (as new dicts, so the cached board is never changed).
    season_from / season_to are start years: 1980 means 1980-81. Rows with no value for the sorted stat (the tracked stats before 2005-06,
    say) can't be ranked and are left out."""
    if sort not in SORTS[kind]:
        raise ValueError(f"Can't sort by {sort}")
    needle = q.strip().lower()
    rate = sort in RATE_SORTS[kind]

    def keep(r):
        return ((not needle or needle in r["name"].lower())
                and (kind != "skater" or not position or (r["position"] != "D" if position == "F" else r["position"] == position))
                and (season_from is None or r["season_id"] >= season_from * 10000 + season_from + 1)
                and (season_to is None or r["season_id"] <= season_to * 10000 + season_to + 1)
                and (r["games_played"] >= min_gp if min_gp else (r["qualifies"] or not rate))
                and (not active or r["active"]) and (not hof or r["hall_of_fame"] == "Y")
                and r[sort] is not None)

    rows = [r for r in board if keep(r)]
    # A lower GAA is better, so "best first" for it is ascending; the caller sends the direction it wants, so nothing is flipped here.
    rows.sort(key=lambda r: (r["name"].lower(), r["season_id"]))
    rows.sort(key=lambda r: r[sort].lower() if sort == "name" else r[sort], reverse=direction == "desc")
    if sort in POSITIONAL:
        nums = [(i + 1, False) for i in range(len(rows))]
    else:
        nums = places(rows, sort)
    end = None if limit is None else offset + limit
    return [dict(r, place=p, tied=t) for r, (p, t) in zip(rows[offset:end], nums[offset:end])], len(rows)
