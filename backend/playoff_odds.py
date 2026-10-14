"""Monte Carlo playoff odds: play out every remaining regular-season game many times.

Model (deliberately simple, and the page says so):
- Each team's strength is its goal differential per game, shrunk toward league average while the
  sample is small (as if it also had PRIOR_GAMES average games), so a hot week doesn't read as destiny.
- A game's win probability is logistic in the strength gap, plus a small home-ice edge.
- A share of games (OT_RATE) go past regulation: the winner takes 2 points and the loser 1.
- NHL format: the top 3 in each division plus 2 wild cards per conference (16 teams) make the playoffs.
  Ties break on points, then regulation wins, then goal differential, then a coin flip.
"""
import numpy as np

SIMS = 4000
PRIOR_GAMES = 25     # games of league-average results blended into every team's rating
LOGIT_SCALE = 0.9    # win-probability steepness per goal of strength gap
HOME_EDGE = 0.15     # goals of strength credited to the home team
OT_RATE = 0.23       # share of games decided after regulation
DIVISION_SPOTS, WILD_CARDS = 3, 2


def team_ratings(teams):
    """Goal differential per game, shrunk toward 0 (league average) for small samples."""
    return {t["abbrev"]: (t["goal_diff"] or 0) / (t["games_played"] + PRIOR_GAMES) for t in teams}


def simulate(teams, remaining, sims=SIMS, seed=0):
    """teams: standings rows. remaining: [(home_abbrev, away_abbrev)] for unplayed games.
    Returns {abbrev: {...odds...}}."""
    rng = np.random.default_rng(seed)
    abbrevs = [t["abbrev"] for t in teams]
    idx = {a: i for i, a in enumerate(abbrevs)}
    n = len(teams)
    rating = team_ratings(teams)
    r = np.array([rating[a] for a in abbrevs])

    points = np.tile(np.array([t["points"] or 0 for t in teams], dtype=np.float64), (sims, 1))
    reg_wins = np.tile(np.array([t["reg_wins"] or 0 for t in teams], dtype=np.float64), (sims, 1))

    if remaining:
        home = np.array([idx[h] for h, _ in remaining])
        away = np.array([idx[a] for _, a in remaining])
        p_home = 1 / (1 + np.exp(-LOGIT_SCALE * (r[home] - r[away] + HOME_EDGE)))
        shape = (sims, len(remaining))
        home_wins = rng.random(shape) < p_home
        overtime = rng.random(shape) < OT_RATE
        winner = np.where(home_wins, home, away)      # (sims, games) team indices
        loser = np.where(home_wins, away, home)
        rows = np.arange(sims)[:, None]
        np.add.at(points, (np.broadcast_to(rows, shape), winner), 2)
        np.add.at(points, (np.broadcast_to(rows, shape), loser), overtime.astype(np.float64))
        np.add.at(reg_wins, (np.broadcast_to(rows, shape), winner), (~overtime).astype(np.float64))

    gd = np.array([t["goal_diff"] or 0 for t in teams], dtype=np.float64)
    # points >> regulation wins >> goal differential >> coin flip, packed into one sortable number.
    key = points * 1e7 + reg_wins * 1e4 + (gd + 500) + rng.random((sims, n)) * 0.5

    make = np.zeros((sims, n), dtype=bool)
    division_win = np.zeros((sims, n), dtype=bool)
    for conf in {t["conference"] for t in teams}:
        conf_idx = [i for i, t in enumerate(teams) if t["conference"] == conf]
        qualified = np.zeros((sims, n), dtype=bool)
        for div in {teams[i]["division"] for i in conf_idx}:
            members = np.array([i for i in conf_idx if teams[i]["division"] == div])
            order = np.argsort(-key[:, members], axis=1)
            rows = np.arange(sims)[:, None]
            top = members[order[:, :DIVISION_SPOTS]]
            qualified[rows, top] = True
            division_win[np.arange(sims), members[order[:, 0]]] = True
        rest = np.array(conf_idx)
        masked = np.where(qualified[:, rest], -np.inf, key[:, rest])
        wc = rest[np.argsort(-masked, axis=1)[:, :WILD_CARDS]]
        qualified[np.arange(sims)[:, None], wc] = True
        make |= qualified

    best = np.zeros((sims, n), dtype=bool)
    best[np.arange(sims), np.argmax(key, axis=1)] = True

    out = {}
    for i, a in enumerate(abbrevs):
        out[a] = {
            "make_playoffs": float(make[:, i].mean()),
            "win_division": float(division_win[:, i].mean()),
            "best_record": float(best[:, i].mean()),
            "exp_points": float(points[:, i].mean()),
            "p10_points": float(np.percentile(points[:, i], 10)),
            "p90_points": float(np.percentile(points[:, i], 90)),
            "rating": float(r[i]),
        }
    return out
