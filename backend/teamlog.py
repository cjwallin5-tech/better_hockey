"""A team's season game by game: results next to what the shots said, and a rolling picture of both.

For each finished game we know the score and, from the stored shots, each side's expected goals (xG, our own model),
attempts and power-play chances. The sum of a team's xG against the opponent's is the share of the game's "good chances"
it had (xG share, 50% is an even game); the goal share is the same thing for the goals actually scored. A team whose goal
share is well above its xG share has been winning games it did not control, which tends not to last (see luck.py for the
same idea per player); well below, and results are probably due to improve.

What it does not know: shootout and overtime results are taken from the score (a shootout win shows as a one-goal win and
the shootout itself has no shots stored), empty-net goals have no xG, and a game with no shots stored (a feed gap) is left
out of the shares instead of counting as zero.
"""
GAP = 0.05          # goal share this far from xG share counts as ahead of (or behind) the play
ROLL = 5            # games in the rolling window


def result(us, them, last_period):
    """'W', 'L' or 'OTL' for a finished game from this team's goals and goals against."""
    if us > them:
        return "W"
    return "L" if last_period == "REG" else "OTL"


def share(for_, against):
    """for / (for + against), or None when both are 0 or missing."""
    if for_ is None or against is None or for_ + against <= 0:
        return None
    return for_ / (for_ + against)


def game_row(g, team, s):
    """One game's line. g: a game row (game_id, game_date, home, away, home_score, away_score, last_period).
    s: that game's shot totals for this team or None (xgf, xga, cf, ca, sf, sa, pp_xgf, pk_xga)."""
    home = g["home"] == team
    gf, ga = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
    out = {"game_id": g["game_id"], "date": g["game_date"], "opponent": g["away"] if home else g["home"], "home_game": home,
           "gf": gf, "ga": ga, "result": result(gf, ga, g["last_period"]), "last_period": g["last_period"],
           "has_shots": bool(s), "xgf": None, "xga": None, "xg_share": None, "cf": None, "ca": None, "cf_pct": None,
           "sf": None, "sa": None, "pp_xgf": None, "pk_xga": None}
    if s:
        out.update(xgf=s["xgf"], xga=s["xga"], xg_share=share(s["xgf"], s["xga"]), cf=s["cf"], ca=s["ca"],
                   cf_pct=share(s["cf"], s["ca"]), sf=s["sf"], sa=s["sa"], pp_xgf=s["pp_xgf"], pk_xga=s["pk_xga"])
    return out


def rolling(rows, window=ROLL):
    """For each game from the window-th on: the xG share and goal share over the last `window` games, both over the games
    that have shots stored so the two are comparable. [{n, date, xg_share, goal_share}], n counting from the first game."""
    out = []
    for i in range(window - 1, len(rows)):
        w = rows[i - window + 1:i + 1]
        shots = [r for r in w if r["has_shots"]]
        out.append({"n": i + 1, "date": rows[i]["date"],
                    "xg_share": share(sum(r["xgf"] for r in shots), sum(r["xga"] for r in shots)) if shots else None,
                    "goal_share": share(sum(r["gf"] for r in shots), sum(r["ga"] for r in shots)) if shots else None})
    return out


def summary(rows):
    """Season totals over the games: record, goals and xG, their shares, and whether results are ahead of or behind the play."""
    shots = [r for r in rows if r["has_shots"]]
    wins = sum(r["result"] == "W" for r in rows)
    otl = sum(r["result"] == "OTL" for r in rows)
    xgf, xga = sum(r["xgf"] for r in shots), sum(r["xga"] for r in shots)
    gf, ga = sum(r["gf"] for r in shots), sum(r["ga"] for r in shots)   # the same games as the xG, so the shares compare
    xg_share, goal_share = share(xgf, xga), share(gf, ga)
    verdict = None
    if xg_share is not None and goal_share is not None and len(shots) >= ROLL:
        diff = goal_share - xg_share
        verdict = "ahead" if diff >= GAP else "behind" if diff <= -GAP else "in line"
    return {"games": len(rows), "wins": wins, "losses": len(rows) - wins - otl, "ot_losses": otl,
            "points": 2 * wins + otl, "shot_games": len(shots), "xgf": xgf, "xga": xga, "gf": gf, "ga": ga,
            "xg_share": xg_share, "goal_share": goal_share, "verdict": verdict}


def player_form(row, min_games=3, ratio=1.25):
    """'hot', 'cold' or None for a skater from their last games' point pace against the season's."""
    games, pace, recent = row.get("recent_games") or 0, row.get("point_pace"), row.get("recent_pace")
    if games < min_games or not pace or recent is None:
        return None
    if recent >= ratio * pace:
        return "hot"
    return "cold" if recent <= pace / ratio else None
