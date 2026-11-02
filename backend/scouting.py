"""Scouting card: where a skater ranks among same-role peers on nine measures of how they play.

Forwards and defensemen are ranked separately (the same nine axes, different peer groups), among skaters with at
least half the games of the busiest skater. Every axis is a percentile, 0-100, where higher is better; for the
defense axis that means fewer expected goals against. Scoring and shooting results carry finishing luck, so the
card marks them (see AXES); the rest are rates or usage that hold up better from year to year.
"""

MIN_PEERS = 10
STRONG, WEAK = 80, 20  # percentile cutoffs for the strengths and weaknesses lists


def role(position):
    return "D" if position == "D" else "F"


def _per60(count, seconds):
    return count / seconds * 3600 if count is not None and seconds else None


def _toi_sec(r):
    return (r["games_played"] or 0) * (r["toi_per_game_sec"] or 0)


def _toi_5v5_sec(r):
    return (r["games_played"] or 0) * (r.get("toi_5v5_per_game") or 0)


# key, label, value(row) -> number or None, higher is better, unit shown next to the value, note
AXES = [
    ("scoring", "Scoring", lambda r: _per60(r["points"], _toi_sec(r)), True, "points/60",
     "Includes finishing luck and teammates' shooting."),
    ("shooting", "Shot quality", lambda r: _per60(r.get("ixg"), _toi_sec(r)), True, "ixG/60",
     "Expected goals from the player's own shots; no finishing luck."),
    ("possession", "Possession", lambda r: r.get("xgf_pct"), True, "xGF%",
     "Share of expected goals while on the ice at 5v5."),
    ("defense", "Defense", lambda r: _per60(r.get("xga"), _toi_5v5_sec(r)), False, "xGA/60",
     "Expected goals against per 60 at 5v5 (fewer is better); depends on teammates."),
    ("powerplay", "Power play", lambda r: r.get("pp_points_per60"), True, "PP pts/60",
     "Points per 60 minutes of power-play time."),
    ("icetime", "Ice time", lambda r: r.get("toi_per_game_sec"), True, "TOI/G",
     "Coaches' trust: minutes per game."),
    ("hits", "Hits", lambda r: r.get("hits_per60"), True, "hits/60",
     "A style measure, not a quality one."),
    ("blocks", "Shot blocking", lambda r: r.get("blocks_per60"), True, "blocks/60",
     "A style measure, not a quality one."),
    ("speed", "Speed", lambda r: r.get("top_speed_mph"), True, "top mph",
     "NHL EDGE top skating speed, ranked among same-role skaters."),
]
LUCKY = {"scoring"}  # the axes whose size mostly reflects results rather than process


def percentile(value, peers, higher_is_better=True):
    """Share of peers the value is at least as good as, 0-100, or None without a value or peers."""
    peers = [p for p in peers if p is not None]
    if value is None or not peers:
        return None
    beaten = sum(1 for p in peers if (p <= value if higher_is_better else p >= value))
    return round(100 * beaten / len(peers))


def peer_group(rows, player):
    """Same-role skaters with half the games of the busiest skater, plus the player themselves."""
    min_gp = max(1, -(-max(r["games_played"] for r in rows) // 2))
    peers = [r for r in rows if role(r["position"]) == role(player["position"]) and r["games_played"] >= min_gp]
    if player["player_id"] not in {p["player_id"] for p in peers}:
        peers.append(player)
    return peers, min_gp


def card(rows, player):
    """The player's scouting card from every skater's season row (with ixg, xgf_pct, xga and EDGE columns merged in).

    Returns axes in a fixed order, each {key, label, value, unit, percentile, note, luck}; a percentile is None
    where the player has no figure. strengths and weaknesses name the axes at or beyond the cutoffs, leaving out
    the style-only ones (hits, shot blocking), which say how a player plays and not how well.
    """
    peers, min_gp = peer_group(rows, player)
    axes = []
    for key, label, value, better, unit, note in AXES:
        mine = value(player)
        pct = percentile(mine, [value(p) for p in peers], better) if len(peers) >= MIN_PEERS else None
        axes.append({"key": key, "label": label, "value": None if mine is None else round(mine, 3), "unit": unit,
                     "percentile": pct, "note": note, "luck": key in LUCKY})
    graded = [a for a in axes if a["percentile"] is not None and a["key"] not in ("hits", "blocks")]
    return {
        "axes": axes,
        "strengths": [a["label"] for a in sorted(graded, key=lambda a: -a["percentile"]) if a["percentile"] >= STRONG],
        "weaknesses": [a["label"] for a in sorted(graded, key=lambda a: a["percentile"]) if a["percentile"] <= WEAK],
        "peer_group": "defensemen" if role(player["position"]) == "D" else "forwards",
        "peer_count": len(peers),
        "min_gp": min_gp,
        "small_sample": player["games_played"] < min_gp,
    }
