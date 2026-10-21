"""Role changes: who has moved up or down the power-play units, and who is playing more or less.

For each skater we compare their last `window` games with their earlier games this season, using the ice time the
NHL reports by situation (even strength, power play, shorthanded).

Power-play unit: a player's share of their team's power-play time in each game (their power-play seconds over the
team's total power-play time per skater slot, so teams that draw more or fewer penalties compare fairly), averaged
over the games in question. A top-unit player is on the ice for roughly 60% of the team's power play, a second-unit
player for about a quarter. At PP1_SHARE or more they are on PP1, at PP2_SHARE or more on PP2, otherwise off the
power play. A change counts only when the unit changed AND the share moved by at least MIN_SHARE_CHANGE, so
someone hovering near a cut-off isn't reported as promoted and demoted every other week.

Even strength: average even-strength seconds per game, with overtime taken out (3-on-3 minutes say nothing
about a player's role). Flagged when the recent average differs by EV_CHANGE_SEC or more.

What it does not know: why (injuries to teammates, a coach's whim, a line shuffle, a blowout that cut a game short),
or what comes next. Early in the season the baseline is only a few games, so read the first few weeks lightly.
"""
PP1_SHARE = 0.45
PP2_SHARE = 0.15
MIN_SHARE_CHANGE = 0.12
EV_CHANGE_SEC = 90
MIN_BASE_GAMES = 3   # earlier games a player needs before there is anything to compare against
UNIT_RANK = {None: 0, "PP2": 1, "PP1": 2}


def unit(share):
    """'PP1', 'PP2' or None for a share of the team's power-play time."""
    if share is None:
        return None
    if share >= PP1_SHARE:
        return "PP1"
    if share >= PP2_SHARE:
        return "PP2"
    return None


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _regulation_ev(g):
    return max(0, g["ev_sec"] - g.get("ot_sec", 0))


def averages(games):
    """Per-game averages over a list of game dicts (ev_sec, ot_sec, pp_sec, sh_sec, total_sec, pp_share)."""
    return {
        "ev": _mean([_regulation_ev(g) for g in games]),
        "pp": _mean([g["pp_sec"] for g in games]),
        "sh": _mean([g["sh_sec"] for g in games]),
        "total": _mean([g["total_sec"] for g in games]),
        "pp_share": _mean([g.get("pp_share") for g in games]) or 0.0,
    }


def pp_change(base_unit, recent_unit, share_delta):
    """('up' | 'down' | None, label) for a move between power-play units."""
    if UNIT_RANK[recent_unit] == UNIT_RANK[base_unit] or abs(share_delta) < MIN_SHARE_CHANGE:
        return None, None
    if UNIT_RANK[recent_unit] > UNIT_RANK[base_unit]:
        return "up", "Promoted to PP1" if recent_unit == "PP1" else "Moved onto the power play (PP2)"
    if recent_unit is None:
        return "down", "Lost power-play time" if base_unit == "PP2" else "Off the power play"
    return "down", "Dropped to PP2"


def role_line(games, window):
    """Recent vs earlier role for one player, or None without enough games.

    games: the player's games this season, oldest first. Each is a dict with ev_sec, ot_sec, pp_sec, sh_sec,
    total_sec and pp_share (None when the team had no power play that game).
    """
    if window < 1 or len(games) < window + MIN_BASE_GAMES:
        return None
    base, recent = games[:-window], games[-window:]
    b, r = averages(base), averages(recent)
    base_unit, recent_unit = unit(b["pp_share"]), unit(r["pp_share"])
    share_delta = r["pp_share"] - b["pp_share"]
    pp_dir, pp_label = pp_change(base_unit, recent_unit, share_delta)
    ev_delta = r["ev"] - b["ev"]
    return {
        "window": window, "recent_games": len(recent), "base_games": len(base),
        "ev": r["ev"], "ev_base": b["ev"], "ev_delta": ev_delta,
        "pp": r["pp"], "pp_base": b["pp"], "pp_delta": r["pp"] - b["pp"],
        "pp_share": r["pp_share"], "pp_share_base": b["pp_share"], "pp_share_delta": share_delta,
        "total": r["total"], "total_base": b["total"], "total_delta": r["total"] - b["total"],
        "unit": recent_unit, "unit_base": base_unit,
        "pp_change": pp_dir, "pp_label": pp_label,
        "ev_change": "up" if ev_delta >= EV_CHANGE_SEC else "down" if ev_delta <= -EV_CHANGE_SEC else None,
    }


def direction(line):
    """'up' or 'down' when the role moved one way (a PP move counts for more than a change in even-strength time);
    'mixed' when the two disagree; None when nothing changed."""
    moves = {line["pp_change"], line["ev_change"]} - {None}
    if not moves:
        return None
    if len(moves) == 2:
        return line["pp_change"] if line["pp_change"] else "mixed"
    return moves.pop()
