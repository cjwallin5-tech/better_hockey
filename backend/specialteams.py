"""Power-play and penalty-kill units, and how well each team's special teams are doing.

Units are inferred, not read from a lineup sheet: the NHL doesn't publish who is on which unit, so each skater's share of
their team's power-play (or penalty-kill) time is worked out from the ice time it reports by situation (the same figures
as roles.py), and the unit follows from the share:
- Power play: a skater on the ice for PP1_SHARE or more of the team's power-play time is on PP1 (the top five at most);
  PP2_SHARE or more, on PP2 (the next five at most). A top unit plays roughly 60-75% of the time, a second unit about a
  quarter to a half.
- Penalty kill: two forwards and two defensemen on the ice at a time, so each position group is ranked on its own: the
  top PK_PER_UNIT of the group (with at least PK1_SHARE) are PK1, the next PK_PER_UNIT (PK2_SHARE) PK2.
A player with fewer than MIN_GAMES games in the window is left out, so a call-up doesn't take a unit slot.

Team figures are per 60 minutes of special-teams time, from expected goals (xG) of the shots in each situation, so a
team's power play can be judged by the chances it makes, not only by whether they went in.
"""
PP1_SHARE = 0.45
PP2_SHARE = 0.15
PP_UNIT_SIZE = 5
PK1_SHARE = 0.20
PK2_SHARE = 0.10
PK_PER_UNIT = 2
MIN_GAMES = 2


def per60(amount, seconds):
    """A per-60-minutes rate, or None when there was no time."""
    return None if not seconds else amount / seconds * 3600


def power_play_units(players):
    """players: dicts with pp_share (share of the team's power-play time), games and anything else to carry along.
    Returns [{unit: 'PP1', players: [...]}, {unit: 'PP2', players: [...]}], each sorted by share, highest first;
    a unit with nobody in it is left out."""
    ranked = sorted((p for p in players if p["games"] >= MIN_GAMES and p.get("pp_share")),
                    key=lambda p: (-p["pp_share"], p.get("name", "")))
    pp1 = [p for p in ranked if p["pp_share"] >= PP1_SHARE][:PP_UNIT_SIZE]
    rest = [p for p in ranked if p not in pp1]
    pp2 = [p for p in rest if p["pp_share"] >= PP2_SHARE][:PP_UNIT_SIZE]
    return [u for u in ({"unit": "PP1", "players": pp1}, {"unit": "PP2", "players": pp2}) if u["players"]]


def penalty_kill_units(players):
    """Same as power_play_units for the penalty kill, with forwards and defensemen ranked separately (see the module
    docstring). Each unit's players are listed forwards first."""
    eligible = [p for p in players if p["games"] >= MIN_GAMES and p.get("pk_share")]
    groups = {
        "F": sorted((p for p in eligible if p["position"] != "D"), key=lambda p: (-p["pk_share"], p.get("name", ""))),
        "D": sorted((p for p in eligible if p["position"] == "D"), key=lambda p: (-p["pk_share"], p.get("name", ""))),
    }
    units = []
    for name, floor, lo in (("PK1", PK1_SHARE, 0), ("PK2", PK2_SHARE, PK_PER_UNIT)):
        members = []
        for g in ("F", "D"):
            members += [p for p in groups[g][lo:lo + PK_PER_UNIT] if p["pk_share"] >= floor]
        if members:
            units.append({"unit": name, "players": members})
    return units


def rank_by(rows, key, high_is_good=True):
    """Adds `<key>_rank` (1 = best) to each row with a value for `key`; rows without one get None."""
    have = sorted((r for r in rows if r.get(key) is not None), key=lambda r: -r[key] if high_is_good else r[key])
    for i, r in enumerate(have, 1):
        r[f"{key}_rank"] = i
    for r in rows:
        r.setdefault(f"{key}_rank", None)
    return rows


def team_line(row):
    """Per-game and per-60 special-teams figures from one team's sums. row: games, pp_sec, sh_sec (the team's power-play
    and shorthanded time), pp_xg, pp_goals, pp_shots (its power-play chances) and pk_xg, pk_goals, pk_shots (the
    chances it faced shorthanded)."""
    g = row["games"]
    return {
        "games": g,
        "pp_toi_pg": row["pp_sec"] / g if g else None, "pk_toi_pg": row["sh_sec"] / g if g else None,
        "pp_xgf60": per60(row["pp_xg"], row["pp_sec"]), "pp_gf60": per60(row["pp_goals"], row["pp_sec"]),
        "pp_shots60": per60(row["pp_shots"], row["pp_sec"]),
        "pk_xga60": per60(row["pk_xg"], row["sh_sec"]), "pk_ga60": per60(row["pk_goals"], row["sh_sec"]),
        "pk_shots60": per60(row["pk_shots"], row["sh_sec"]),
    }
