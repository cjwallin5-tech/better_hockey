"""Who gets the ice time when a regular is out.

Hockey teams dress 12 forwards and 6 defensemen, so when a regular is out his minutes are spread over the group, not handed to one
player. analysis/backtest_absences.py measured that over four seasons (every game a team played with exactly one regular missing,
compared with each teammate's own average over the previous ten games with both in the lineup):

  - only a top-role absence moves anyone's ice time: with a top-unit power-play forward out, the other forwards gain about 17 seconds a game at
    even strength and 10 on the power play; with a top-unit defenseman out, the other defensemen gain about 53 and 16; when a player with no
    power-play time is out, teammates gain nothing measurable;
  - the gain is spread thinly over the group, not handed to one player;
  - what each player gains is hard to predict: the structure below explains 2-9% of a player's game-to-game change on a season it was not fitted
    on, and points cannot be predicted at all (the change in a player's points was not related to anything we measured). So the figures are what a
    teammate gains on average in his spot, with a lot of game-to-game noise around them.

`expected_change` is that average, from a small regression per position group fitted by the backtest. `observed_change` is what actually
happened this season in the games a player missed, which is the better evidence once a few games have passed.

A "regular" is a player who appeared in at least MIN_PLAYED of his team's previous WINDOW games (fewer early in the season). "Out" means he
missed his team's most recent games: the NHL publishes no injury list, so a scratch, a trade or a call-down looks the same as an injury.
"""
WINDOW = 10          # team games the baseline and the regular test look back over
MIN_PLAYED = 7       # appearances in them to be a regular (scaled down when fewer games are available)
MIN_BASE = 4         # games with both players in the lineup to have a baseline for a teammate
MAX_OUT = 25         # a player gone longer than this is long-term out: his team has already settled into the new lineup

PP1_SECONDS, PP2_SECONDS = 100, 30   # a player averaging this much power-play time a game is on the first / second unit

# Fitted by analysis/backtest_absences.py on four seasons: the average extra (even-strength seconds, power-play seconds) a game for a teammate in the same
# position group, by the absent player's power-play role and the teammate's: MODEL[group][absent role][teammate role]. Cells with few
# games are pulled toward the absent role's overall average (the script prints these lines).
MODEL = {
    "F": {
        "PP1": {"PP1": (20.9, -0.4), "PP2": (11.6, 24.0), "none": (15.7, 13.6)},
        "PP2": {"PP1": (1.4, -4.9), "PP2": (7.7, 9.9), "none": (0.8, 11.1)},
        "none": {"PP1": (-4.9, -3.7), "PP2": (-10.0, 7.8), "none": (-11.6, 5.1)},
    },
    "D": {
        "PP1": {"PP1": (61.8, 4.0), "PP2": (46.3, 41.6), "none": (52.5, 12.3)},
        "PP2": {"PP1": (18.9, 18.2), "PP2": (8.4, 9.2), "none": (13.7, 9.0)},
        "none": {"PP1": (5.0, -12.2), "PP2": (-5.8, 0.6), "none": (3.7, 2.1)},
    },
}


def role(pp_seconds):
    """'PP1', 'PP2' or 'none' from the power-play seconds a game."""
    return "PP1" if pp_seconds >= PP1_SECONDS else "PP2" if pp_seconds >= PP2_SECONDS else "none"


def group(position):
    """'D' for defensemen, 'F' for everyone else (the groups ice time is shared within)."""
    return "D" if position == "D" else "F"


def expected_change(x_group, x, y_group, y):
    """(even-strength seconds, power-play seconds) a game teammate y is expected to gain while x is out; zero across position groups
    (the backtest found nothing there beyond noise). x, y: {pp} baseline power-play seconds a game."""
    if x_group != y_group:
        return 0.0, 0.0
    ev, pp = MODEL.get(x_group, {}).get(role(x["pp"]), {}).get(role(y["pp"]), (0.0, 0.0))
    return ev, pp


def regulars(team_games, game_ids):
    """Players who appeared in at least the scaled MIN_PLAYED of the given recent team games.
    team_games: {game_id: {player_id: row}}; game_ids: those games, oldest first."""
    need = max(1, round(MIN_PLAYED * len(game_ids) / WINDOW))
    count = {}
    for g in game_ids:
        for p in team_games[g]:
            count[p] = count.get(p, 0) + 1
    return {p for p, c in count.items() if c >= need}


def baseline(team_games, game_ids, player, with_player=None):
    """{ev, pp, sh, total, games}: the player's mean seconds a game over the given games he played in (and `with_player` did too), or
    None with fewer than MIN_BASE (scaled when fewer games exist)."""
    gs = [g for g in game_ids if player in team_games[g] and (with_player is None or with_player in team_games[g])]
    need = min(MIN_BASE, max(1, len(game_ids) // 2))
    if len(gs) < need:
        return None
    n = len(gs)
    ev = sum(team_games[g][player]["ev"] for g in gs) / n
    pp = sum(team_games[g][player]["pp"] for g in gs) / n
    sh = sum(team_games[g][player]["sh"] for g in gs) / n
    return {"ev": ev, "pp": pp, "sh": sh, "total": ev + pp + sh, "games": n}


def current_absences(team_games, order):
    """The regulars of one team who missed its latest game(s): [{player, games_out, base_games}] where base_games are the team games before
    the absence began that the baseline is taken over.
    team_games: {game_id: {player_id: {ev, pp, sh, position}}}; order: the team's game ids, oldest first."""
    if len(order) < 3:
        return []
    out = []
    latest = set(team_games[order[-1]])
    seen = {p for g in order for p in team_games[g]}
    for p in seen - latest:
        # appearances: find the last game he played
        played = [i for i, g in enumerate(order) if p in team_games[g]]
        last = played[-1]
        games_out = len(order) - 1 - last
        if games_out < 1 or games_out > MAX_OUT:
            continue
        window = order[max(0, last + 1 - WINDOW):last + 1]
        if p not in regulars(team_games, window):
            continue
        out.append({"player": p, "games_out": games_out, "base_games": window, "absent_games": order[last + 1:]})
    return out


def effect(team_games, absence, y):
    """What teammate y did while the absent player was out, against his own baseline from the games before: {base, during, change, games}
    in seconds a game, or None when y has no baseline or did not play during the absence."""
    x = absence["player"]
    base = baseline(team_games, absence["base_games"], y, with_player=x)
    during = [g for g in absence["absent_games"] if y in team_games[g]]
    if not base or not during:
        return None
    n = len(during)
    mean = lambda k: sum(team_games[g][y][k] for g in during) / n
    now = {"ev": mean("ev"), "pp": mean("pp"), "sh": mean("sh")}
    now["total"] = now["ev"] + now["pp"] + now["sh"]
    return {"base": base, "during": now, "games": n,
            "change": {k: now[k] - base[k] for k in ("ev", "pp", "sh", "total")}}
