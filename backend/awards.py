"""Win chances for the Hart, Norris, Calder, Selke and Vezina trophies, from the season's numbers.

These awards are voted (writers for the first three, general managers for the Vezina), so the model learns what voters have rewarded
rather than computing a "best player". For each award a short list of candidates is picked from the stats (top scorers, top defensemen,
top rookies, top goalies), each gets a few unitless features, and a conditional logit (softmax across the candidates) turns them into
win chances. The weights were fitted on the 20 seasons from 2005-06 to 2024-25 by analysis/backtest_award_odds.py, which also scores how
well that did on seasons it had not seen (see its docstring). The features:

  hart    points relative to the leader, points per game relative to the best rate, and the team's points percentage
  norris  points, ice time and penalty-kill time per game relative to the best candidate, and shot-attempt share (the defensive side)
  calder  points and points per game relative to the best rookie, and the team's points percentage
  selke   points, shot-attempt share, penalty-kill time, faceoff share (centers) and takeaways per game
  vezina  goals saved above average and wins relative to the best candidate, and the team's points percentage

Early in a season the candidates' final numbers are not known, so `odds` is fed many plausible final lines per candidate (a draw around the
projected finish, see `draw_finals`) and averages the win chances over them: a player leading by a few points after ten games gets a modest
chance, not a certain one. What this cannot see: the narrative voters follow (a player's story, injuries to rivals), defense for the Norris,
playoffs, goalies for the Hart and goalies for the Calder (both rarely win; the candidates here are skaters). The Norris and Selke use shot-attempt
share, which the NHL only has from 2009-10, so they were fitted on 16 seasons; early in a season those rates are pulled toward average (the
shrinkage in api.py is a guess, not fitted).
"""
import math
import random

AWARDS = ("hart", "norris", "calder", "selke", "vezina")
POOL = {"hart": 10, "norris": 8, "calder": 8, "selke": 20, "vezina": 8}   # candidates per award
MIN_FORWARD_GAMES_SHARE = 0.5   # a Selke candidate has played at least this share of the busiest skater's games (40 of 82 in the backtest)
MIN_FACEOFFS = 300              # faceoffs for a center's faceoff percentage to count
MIN_GOALIE_GAMES_SHARE = 0.4   # a Vezina candidate has played at least this share of the busiest goalie's games
ROOKIE_MAX_AGE = 25            # age on Feb 1 of the season's end year (the Calder's own age rule)

FEATURES = {
    "hart": ("pts_rel", "ppg_rel", "team"),
    "norris": ("pts_rel", "toi_rel", "sh_rel", "sat"),
    "calder": ("pts_rel", "ppg_rel", "team"),
    "selke": ("pts_rel", "sat", "sh_rel", "fo", "tk_rel"),
    "vezina": ("gsaa_rel", "wins_rel", "team"),
}
# Fitted by analysis/backtest_award_odds.py on 2005-06 to 2024-25 (the script prints these lines).
WEIGHTS = {
    "hart": {"pts_rel": 11.64, "ppg_rel": 7.08, "team": 0.6},
    "norris": {"pts_rel": 11.86, "toi_rel": 2.31, "sh_rel": 2.06, "sat": 3.34},
    "calder": {"pts_rel": 10.52, "ppg_rel": 0.58, "team": 0.08},
    "selke": {"pts_rel": 7.45, "sat": 3.83, "sh_rel": 3.39, "fo": 4.82, "tk_rel": 2.92},
    "vezina": {"gsaa_rel": 8.54, "wins_rel": 8.08, "team": 7.49},
}
# What the leave-one-season-out backtest found (seasons scored, average chance given to the winner, the top pick's average chance and how
# often it won, and the winner in the top three), for the page's text.
BACKTEST = {
    "hart": {"seasons": 18, "winner_chance": 0.50, "top_chance": 0.63, "top_won": 0.61, "top3": 15},
    "norris": {"seasons": 15, "winner_chance": 0.38, "top_chance": 0.56, "top_won": 0.47, "top3": 13},
    "calder": {"seasons": 16, "winner_chance": 0.58, "top_chance": 0.69, "top_won": 0.69, "top3": 16},
    "selke": {"seasons": 16, "winner_chance": 0.40, "top_chance": 0.58, "top_won": 0.56, "top3": 15},
    "vezina": {"seasons": 20, "winner_chance": 0.70, "top_chance": 0.80, "top_won": 0.75, "top3": 20},
}


def team_pct(points, games):
    """A team's points percentage (0.5 is average), or 0.5 when unknown."""
    return points / (2 * games) if games else 0.5


def _rel(value, best):
    return value / best if best and best > 0 else 0.0


def pool(award, skaters, goalies):
    """The candidates for an award, best first, each a copy of its row. skaters: {id, name, pos, team, gp, goals, points, toi_pg, team_pct,
    rookie, age, and for the Norris and Selke sat (shot-attempt share, 0-1), sh (penalty-kill seconds a game), fo and fo_n (faceoff share and
    faceoffs taken), takeaways}; goalies: {id, name, team, gp, wins, saves, shots_against, team_pct}."""
    if award == "hart":
        rows = [dict(r) for r in skaters]
        key = lambda r: (-r["points"], -r["goals"], r["id"])
    elif award == "norris":
        rows = [dict(r) for r in skaters if r["pos"] == "D"]
        key = lambda r: (-r["points"], -r["goals"], r["id"])
    elif award == "calder":
        rows = [dict(r) for r in skaters if r.get("rookie") and (r.get("age") or 99) <= ROOKIE_MAX_AGE]
        key = lambda r: (-r["points"], -r["goals"], r["id"])
    elif award == "selke":
        # Selke winners are not the top scorers or the busiest forwards, so the short list is the forwards who rank best on points, shot-attempt
        # share and penalty-kill time taken together (the three ranks added up): that holds every winner of the 20 seasons tested.
        busiest = max((r["gp"] for r in skaters), default=0)
        rows = [dict(r) for r in skaters if r["pos"] in ("C", "L", "R") and r["gp"] >= MIN_FORWARD_GAMES_SHARE * busiest]
        ranks = {r["id"]: 0 for r in rows}
        for stat in (lambda r: r["points"], lambda r: r.get("sat") or 0, lambda r: r.get("sh") or 0):
            for place, r in enumerate(sorted(rows, key=lambda r: (-stat(r), r["id"]))):
                ranks[r["id"]] += place
        key = lambda r: (ranks[r["id"]], r["id"])
    else:
        busiest = max((g["gp"] for g in goalies), default=0)
        rows = [dict(g) for g in goalies if g["gp"] >= MIN_GOALIE_GAMES_SHARE * busiest]
        saves, shots = sum(g["saves"] for g in goalies if "saves" in g), sum(g["shots_against"] for g in goalies if "saves" in g)
        league_sv = saves / shots if shots else 0.9
        for r in rows:
            if "gsaa" not in r:           # a live row brings its own (the draws in odds() build theirs)
                r["gsaa"] = r["saves"] - league_sv * r["shots_against"]
        key = lambda r: (-r["gsaa"], r["id"])
    return sorted(rows, key=key)[:POOL[award]]


def _per_game(r, field):
    return (r.get(field) or 0) / r["gp"] if r["gp"] else 0.0


def features(award, rows):
    """[feature vector per candidate] in FEATURES[award]'s order. Most are relative to the best candidate, so seasons are comparable;
    sat and fo are the shot-attempt and faceoff shares above 50%, times ten (a center needs MIN_FACEOFFS faceoffs for fo to count)."""
    best = lambda f: max((f(r) for r in rows), default=0)
    if award == "vezina":
        best_gsaa, best_wins = best(lambda r: r["gsaa"]), best(lambda r: r["wins"])
        return [[_rel(r["gsaa"], best_gsaa), _rel(r["wins"], best_wins), r["team_pct"] - 0.5] for r in rows]
    best_pts, best_ppg = best(lambda r: r["points"]), best(lambda r: _per_game(r, "points"))
    best_toi, best_sh, best_tk = best(lambda r: r.get("toi_pg") or 0), best(lambda r: r.get("sh") or 0), best(lambda r: _per_game(r, "takeaways"))
    table = lambda r: {
        "pts_rel": _rel(r["points"], best_pts), "ppg_rel": _rel(_per_game(r, "points"), best_ppg), "toi_rel": _rel(r.get("toi_pg") or 0, best_toi),
        "sh_rel": _rel(r.get("sh") or 0, best_sh), "tk_rel": _rel(_per_game(r, "takeaways"), best_tk), "team": r["team_pct"] - 0.5,
        "sat": ((r.get("sat") or 0.5) - 0.5) * 10,
        "fo": ((r.get("fo") or 0.5) - 0.5) * 10 if r["pos"] == "C" and (r.get("fo_n") or 0) >= MIN_FACEOFFS else 0.0}
    return [[table(r)[name] for name in FEATURES[award]] for r in rows]


def softmax(scores):
    top = max(scores, default=0)
    exps = [math.exp(s - top) for s in scores]
    total = sum(exps)
    return [e / total for e in exps] if total else [1 / len(scores)] * len(scores)


def win_probs(award, rows, weights=None):
    """Each candidate's win chance, from their features and the award's weights (rows from pool())."""
    w = weights or WEIGHTS[award]
    ws = [w[name] for name in FEATURES[award]]
    return softmax([sum(a * b for a, b in zip(ws, v)) for v in features(award, rows)])


# --- Odds before the season is over ----------------------------------------------------------------------------

DRAWS = 400
# Injuries are not in the projections, and a long absence is the main way a leader falls back, so each draw has a MISS_CHANCE that the
# candidate misses between MISS_SHARE of what is left of the season. These two numbers are guesses, not fitted to anything.
MISS_CHANCE = 0.12
MISS_SHARE = (0.15, 0.5)
GAMES = 84      # a full season, for a team's points percentage (api.py passes config.GAMES_PER_SEASON)


def draw_finals(award, cands, teams, rng, games=GAMES):
    """One plausible finish for every candidate, as rows in pool()'s shape.

    cands: skaters {id, name, pos, team, games_played, points, goals, toi_pg, rookie, age, final_gp, final_points, sd_points} or goalies
    {id, name, team, games_played, wins, gsaa, final_gp, final_wins, sd_wins, final_gsaa, sd_gsaa}: where he is now, the projected
    finish and how far off it might be.
    teams: {team: (expected final points, sd)}. Each team's finish is drawn once per draw, so teammates share it. A finish never falls
    below what the candidate already has (points, wins). In a MISS_CHANCE share of draws a candidate misses part of the rest of the season."""
    pct = {team: team_pct(max(0.0, rng.gauss(mean, sd)), games) for team, (mean, sd) in teams.items()}
    out = []
    for c in cands:
        # the share of the rest of the season he plays in this draw
        played = 1 - rng.uniform(*MISS_SHARE) if rng.random() < MISS_CHANCE else 1.0
        at = lambda now, final: now + (final - now) * played
        base = {"id": c["id"], "name": c["name"], "team": c["team"], "gp": at(c["games_played"], c["final_gp"]), "team_pct": pct.get(c["team"], 0.5)}
        if award == "vezina":
            out.append({**base, "wins": max(c["wins"], rng.gauss(at(c["wins"], c["final_wins"]), c["sd_wins"])),
                        "gsaa": rng.gauss(at(c["gsaa"], c["final_gsaa"]), c["sd_gsaa"])})
        else:
            out.append({**base, "pos": c["pos"], "points": max(c["points"], rng.gauss(at(c["points"], c["final_points"]), c["sd_points"])),
                        "goals": c.get("goals", 0), "toi_pg": c.get("toi_pg"), "rookie": c.get("rookie"), "age": c.get("age"),
                        "sat": c.get("sat"), "sh": c.get("sh"), "fo": c.get("fo"), "fo_n": c.get("fo_n"),
                        "takeaways": max(c.get("takeaways") or 0, at(c.get("takeaways") or 0, c.get("final_takeaways") or 0))})
    return out


def odds(award, cands, teams, draws=DRAWS, seed=0, games=GAMES):
    """{id: chance of winning} averaged over `draws` plausible finishes (see draw_finals). A candidate who misses a draw's short list gets
    0 in that draw."""
    rng = random.Random(seed)
    totals = {}
    for _ in range(draws):
        rows = draw_finals(award, cands, teams, rng, games)
        short = pool(award, rows, rows)
        for row, p in zip(short, win_probs(award, short)):
            totals[row["id"]] = totals.get(row["id"], 0.0) + p / draws
    return totals
