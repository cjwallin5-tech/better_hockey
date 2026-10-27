"""How well do the site's predictions actually do? Walk-forward replays of this season, scored against what happened.

A prediction is only fair to grade if it uses what was known at the time. So each replay goes through the season in date order and,
before each day's games, rebuilds the model from only the games played before that day (no peeking at later results or at ratings
that include the game being predicted). Two models are replayed:

- Game win chance: the "on paper" chance shown on the Tonight page (team ratings from expected goals, turned into a win chance with
  tonight.matchup). It is compared with three simple baselines: a coin flip, the home team's win rate so far, and the same
  strength-from-the-record idea using goals instead of expected goals (so it says whether expected goals beat plain results).
- Probable goalie: who the starter model says will play (probable_goalies.predict, with the day's back-to-back rule) against who
  did, compared with "the same goalie as last time" and "the goalie who has started most".

Scores: Brier (the mean squared miss of the win chance; a coin flip scores 0.25, lower is better), log loss (same idea, punishing
confident misses harder), and accuracy (picked the winner; a toss-up pick of exactly 50% counts as half). Differences between the model
and a baseline come with a 95% interval from the paired per-game differences: when the interval includes zero, the data can't tell
them apart yet. Hockey has a lot of luck in single games, so a good model is only a little better than a coin flip, and a season so
far is a small sample.

What it does not cover: past seasons (expected goals are stored per game only for this season), the skater projections, or the
lineup optimizer; the Projections page documents the backtest behind the skater model.
"""
import math

import matchups
import probable_goalies
import tonight

MIN_GAMES = 4            # games a team needs behind it before its game is predicted
HOME_PRIOR_GAMES = 50    # games' worth of the typical home win rate blended into the home-ice baseline
TYPICAL_HOME_WIN = 0.54
PRIOR_GAMES = matchups.TEAM_PRIOR_GAMES
EPS = 0.02               # a win chance is kept at least this far from 0 and 1 when scoring log loss
Z95 = 1.96
CAL_EDGES = (0.0, 0.40, 0.45, 0.50, 0.55, 0.60, 1.0)


# --- Scores ------------------------------------------------------------------------------------------------

def brier(p, y):
    return (p - y) ** 2


def log_loss(p, y):
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def pick_credit(p, y):
    """1 when the side picked (p above 0.5) won, 0.5 for exactly 50%, else 0."""
    if p == 0.5:
        return 0.5
    return 1.0 if (p > 0.5) == bool(y) else 0.0


def summarize(preds):
    """[(p, y)] -> {n, brier, log_loss, accuracy, mean_p, rate}; None for the figures when there are no predictions."""
    n = len(preds)
    if n == 0:
        return {"n": 0, "brier": None, "log_loss": None, "accuracy": None, "mean_p": None, "rate": None}
    return {"n": n, "brier": sum(brier(p, y) for p, y in preds) / n, "log_loss": sum(log_loss(p, y) for p, y in preds) / n,
            "accuracy": sum(pick_credit(p, y) for p, y in preds) / n, "mean_p": sum(p for p, _ in preds) / n,
            "rate": sum(1 for _, y in preds if y) / n}


def paired(a, b):
    """Mean and 95% interval of a - b over paired per-game losses (lower is better, so a negative mean favors a).
    Returns {mean, low, high, n}, or None with fewer than 2 pairs."""
    diffs = [x - y for x, y in zip(a, b)]
    n = len(diffs)
    if n < 2:
        return None
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    return {"mean": mean, "low": mean - Z95 * se, "high": mean + Z95 * se, "n": n}


def calibration(preds, edges=CAL_EDGES):
    """Bins of predicted win chance with how often the event happened: [{lo, hi, n, mean_p, rate}], empty bins left out."""
    out = []
    for lo, hi in zip(edges, edges[1:]):
        rows = [(p, y) for p, y in preds if lo <= p < hi or (hi == edges[-1] and p == hi)]
        if rows:
            out.append({"lo": lo, "hi": hi, "n": len(rows), "mean_p": sum(p for p, _ in rows) / len(rows),
                        "rate": sum(1 for _, y in rows if y) / len(rows)})
    return out


# --- Game win chance ----------------------------------------------------------------------------------------

def _log5(a, b):
    """Chance a side with strength a beats one with strength b (both between 0 and 1, 0.5 average)."""
    den = a * (1 - b) + (1 - a) * b
    return a * (1 - b) / den if den > 0 else 0.5


def _goal_strength(gf, ga, games, league_goals):
    """Pythagorean strength from goals so far, pulled toward the league average like the xG ratings are."""
    f = (gf + PRIOR_GAMES * league_goals) / (games + PRIOR_GAMES)
    a = (ga + PRIOR_GAMES * league_goals) / (games + PRIOR_GAMES)
    return f * f / (f * f + a * a) if f + a > 0 else 0.5


def win_replay(games, shots, min_games=MIN_GAMES):
    """Walk-forward win chances for every finished game with enough history, with baselines.

    games: [{game_id, date, home, away, home_score, away_score}] finished games. shots: {(game_id, team): {xgf, xga}} plus
    {(game_id, None): {goals, sog}} for the game's totals (goals and shots on goal, both teams). Returns a list of rows
    {game_id, date, home, away, home_win, model, coin, home_ice, goals_model} (None for a model that couldn't be built).
    """
    out = []
    team = {}                       # team -> {games, xgf, xga, gf, ga}
    league = {"team_games": 0, "goals": 0.0, "sog": 0.0, "home_games": 0, "home_wins": 0}
    by_date = {}
    for g in sorted(games, key=lambda g: (g["date"], g["game_id"])):
        by_date.setdefault(g["date"], []).append(g)
    for date in sorted(by_date):
        todays = by_date[date]
        rows = [{"team": t, "games": s["games"], "xgf": s["xgf"], "xga": s["xga"]} for t, s in team.items() if s["games"]]
        ratings, _ = matchups.team_ratings(rows)
        pg = {"goals_pg": league["goals"] / league["team_games"], "shots_pg": league["sog"] / league["team_games"]} if league["team_games"] else None
        home_rate = (league["home_wins"] + HOME_PRIOR_GAMES * TYPICAL_HOME_WIN) / (league["home_games"] + HOME_PRIOR_GAMES)
        for g in todays:
            h, a = team.get(g["home"]), team.get(g["away"])
            if not h or not a or h["games"] < min_games or a["games"] < min_games or not pg or not pg["goals_pg"]:
                continue
            p_model, _ = tonight.matchup(ratings.get(g["home"]), ratings.get(g["away"]), pg)
            p_goals = _log5(_goal_strength(h["gf"], h["ga"], h["games"], pg["goals_pg"]),
                            _goal_strength(a["gf"], a["ga"], a["games"], pg["goals_pg"]))
            if p_model is None:
                continue
            out.append({"game_id": g["game_id"], "date": date, "home": g["home"], "away": g["away"],
                        "home_win": 1 if g["home_score"] > g["away_score"] else 0, "model": p_model, "coin": 0.5,
                        "home_ice": home_rate, "goals_model": p_goals})
        for g in todays:                                  # only now do the day's results count
            tot = shots.get((g["game_id"], None))
            for side, opp, gf, ga in ((g["home"], g["away"], g["home_score"], g["away_score"]),
                                      (g["away"], g["home"], g["away_score"], g["home_score"])):
                s = shots.get((g["game_id"], side))
                if s is None or tot is None:
                    continue
                t = team.setdefault(side, {"games": 0, "xgf": 0.0, "xga": 0.0, "gf": 0, "ga": 0})
                t["games"] += 1
                t["xgf"] += s["xgf"]
                t["xga"] += s["xga"]
                t["gf"] += gf
                t["ga"] += ga
            if tot is not None and (g["game_id"], g["home"]) in shots and (g["game_id"], g["away"]) in shots:
                league["team_games"] += 2
                league["goals"] += tot["goals"]
                league["sog"] += tot["sog"]
                league["home_games"] += 1
                league["home_wins"] += g["home_score"] > g["away_score"]
    return out


def win_report(rows):
    """The numbers the Accuracy page shows for the win-chance replay."""
    out = {"games": len(rows), "from": rows[0]["date"] if rows else None, "to": rows[-1]["date"] if rows else None}
    models = {"model": "Expected-goals ratings (the Tonight page)", "coin": "Coin flip", "home_ice": "Home team's win rate so far",
              "goals_model": "Same idea using goals instead of expected goals"}
    out["models"] = {k: {"label": label, **summarize([(r[k], r["home_win"]) for r in rows])} for k, label in models.items()}
    ys = [r["home_win"] for r in rows]
    losses = {k: [brier(r[k], r["home_win"]) for r in rows] for k in models}
    out["vs"] = {k: paired(losses["model"], losses[k]) for k in models if k != "model"}
    out["calibration"] = calibration([(r["model"], r["home_win"]) for r in rows])
    out["home_win_rate"] = sum(ys) / len(ys) if ys else None
    return out


# --- Probable goalie ----------------------------------------------------------------------------------------

def goalie_replay(team_games, min_history=3):
    """Walk-forward starter predictions.

    team_games: [{game_id, date, team, starter}] one per team and finished game with a known starting goalie. Walks the season in
    date order; before each game the model sees only the team's earlier starts (and the league's repeat rate so far). Returns rows
    {game_id, date, team, starter, top, top_p, p_actual, tired, same_as_last, most_started_hit}.
    """
    out = []
    history = {}                   # team -> [(date, starter)] oldest first
    counts = {}                    # team -> {starter: starts}
    b2b = repeats = 0
    by_date = {}
    for g in sorted(team_games, key=lambda g: (g["date"], g["game_id"])):
        by_date.setdefault(g["date"], []).append(g)
    for date in sorted(by_date):
        p_repeat = probable_goalies.repeat_rate(b2b, repeats)
        for g in by_date[date]:
            hist = history.get(g["team"], [])
            if len(hist) < min_history:
                continue
            tired = (date - hist[-1][0]).days == 1
            recent = [(pid, "") for _, pid in reversed(hist)]
            cands = probable_goalies.predict(recent, tired, p_repeat)
            probs = {c["player_id"]: c["probability"] for c in cands}
            top = cands[0] if cands else None
            if not top:
                continue
            most = max(counts[g["team"]], key=counts[g["team"]].get)
            out.append({"game_id": g["game_id"], "date": date, "team": g["team"], "starter": g["starter"], "top": top["player_id"],
                        "top_p": top["probability"], "p_actual": probs.get(g["starter"], 0.0), "tired": tired,
                        "same_as_last": hist[-1][1] == g["starter"], "most_started_hit": most == g["starter"]})
        for g in by_date[date]:                             # the day's starts count for tomorrow
            hist = history.setdefault(g["team"], [])
            if hist and (date - hist[-1][0]).days == 1:
                b2b += 1
                repeats += hist[-1][1] == g["starter"]
            hist.append((date, g["starter"]))
            counts.setdefault(g["team"], {})
            counts[g["team"]][g["starter"]] = counts[g["team"]].get(g["starter"], 0) + 1
    return out


def goalie_report(rows):
    """The numbers the Accuracy page shows for the starter replay."""
    def part(rs):
        n = len(rs)
        if n == 0:
            return {"n": 0, "top_correct": None, "mean_p_actual": None, "log_loss": None, "same_as_last": None, "most_started": None}
        return {"n": n, "top_correct": sum(r["top"] == r["starter"] for r in rs) / n,
                "mean_p_actual": sum(r["p_actual"] for r in rs) / n,
                "log_loss": sum(-math.log(max(r["p_actual"], EPS)) for r in rs) / n,
                "same_as_last": sum(r["same_as_last"] for r in rs) / n, "most_started": sum(r["most_started_hit"] for r in rs) / n}
    tired = [r for r in rows if r["tired"]]
    rested = [r for r in rows if not r["tired"]]
    cal = calibration([(r["top_p"], r["top"] == r["starter"]) for r in rows], edges=(0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01))
    return {"games": len(rows), "from": rows[0]["date"] if rows else None, "to": rows[-1]["date"] if rows else None,
            "all": part(rows), "back_to_back": part(tired), "rested": part(rested), "calibration": cal}
