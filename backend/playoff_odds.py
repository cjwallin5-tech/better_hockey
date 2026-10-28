"""Monte Carlo playoff odds: play out every remaining regular-season game many times.

Model (deliberately simple, and the page says so):
- Each team's strength is its goal differential per game, shrunk toward league average while the
  sample is small (as if it also had PRIOR_GAMES average games), so a hot week doesn't read as destiny.
- A game's win probability is logistic in the strength gap, plus a small home-ice edge.
- A share of games (OT_RATE) go past regulation: the winner takes 2 points and the loser 1.
- NHL format: the top 3 in each division plus 2 wild cards per conference (16 teams) make the playoffs.
  Ties break on points, then regulation wins, then goal differential, then a coin flip.
- Then the playoffs are played out from each simulated field: in a conference the better division winner (by points) meets the
  lower wild card and the other division winner the higher wild card, second against third inside each division, and each
  division's bracket side meets in round two. A series is a best of seven with the better seed at home in games 1, 2, 5 and 7, each game
  won with the same strength-gap logistic (and home edge) as the regular season, with no overtime-points wrinkle.
  The strength scale was backtested on 300 past series and the odds of making the playoffs from a quarter and half of the way through
  the season: 0.9 was overconfident, 0.6 is calibrated on average (analysis/backtest_playoff_odds.py). Rather than
  sampling the series, each simulated field is advanced exactly (the chance each team wins each series given who it can meet),
  which gives smooth Cup odds from the same number of simulations. Playoff hockey is not the regular season (a hot goalie, shorter
  benches), so the series are close to coin flips and a strong team's Cup odds stay modest: that is the model's honest answer.
"""
import numpy as np

SIMS = 4000
PRIOR_GAMES = 25     # games of league-average results blended into every team's rating
LOGIT_SCALE = 0.6    # win-probability steepness per goal of strength gap (backtested: 0.9 was overconfident, see analysis/backtest_playoff_odds.py)
HOME_EDGE = 0.15     # goals of strength credited to the home team
OT_RATE = 0.23       # share of games decided after regulation
DIVISION_SPOTS, WILD_CARDS = 3, 2
SERIES_HOME_GAMES = (0, 1, 4, 6)   # games (of 7) the better seed hosts


def team_ratings(teams):
    """Goal differential per game, shrunk toward 0 (league average) for small samples."""
    return {t["abbrev"]: (t["goal_diff"] or 0) / (t["games_played"] + PRIOR_GAMES) for t in teams}


def series_matrix(r):
    """S[i, j]: the chance team i wins a best-of-seven against j when i has home ice, from the strength ratings r."""
    r = np.asarray(r, dtype=float)
    gap = r[:, None] - r[None, :]
    p_home = 1 / (1 + np.exp(-LOGIT_SCALE * (gap + HOME_EDGE)))
    p_away = 1 / (1 + np.exp(-LOGIT_SCALE * (gap - HOME_EDGE)))
    state = {(0, 0): np.ones_like(gap)}              # (wins for i, wins for j) -> chance of being there
    won = np.zeros_like(gap)
    for game in range(7):
        p = p_home if game in SERIES_HOME_GAMES else p_away
        nxt = {}
        for (a, b), prob in state.items():
            for (da, db, pr) in ((1, 0, p), (0, 1, 1 - p)):
                key = (a + da, b + db)
                if key[0] == 4:
                    won += prob * pr
                elif key[1] < 4:
                    nxt[key] = nxt.get(key, 0) + prob * pr
        state = nxt
    return won


def _meet(a, b, S, key):
    """Advance two sets of possible teams ({team: chance of being there}) through a series: {team: chance of winning it}."""
    out = {}
    for i, pi in a.items():
        for j, pj in b.items():
            p = S[i, j] if key[i] >= key[j] else 1 - S[j, i]      # the team with more points is at home
            out[i] = out.get(i, 0.0) + pi * pj * p
            out[j] = out.get(j, 0.0) + pi * pj * (1 - p)
    return out


def _bracket(divs, wc, S, key, reach):
    """One conference's playoffs from one simulated field: divs {name: [1st, 2nd, 3rd]}, wc [higher, lower] wild card.
    Adds each team's chance of reaching round 2 (reach[0]) and the conference final (reach[1]) to reach, and returns the conference champion's distribution."""
    (na, a), (nb, b) = sorted(divs.items())
    top_is_a = key[a[0]] >= key[b[0]]
    a_foe, b_foe = (wc[1], wc[0]) if top_is_a else (wc[0], wc[1])
    sides = []
    for first, foe, (second, third) in ((a[0], a_foe, a[1:]), (b[0], b_foe, b[1:])):
        one = _meet({first: 1.0}, {foe: 1.0}, S, key)
        two = _meet({second: 1.0}, {third: 1.0}, S, key)
        for t, p in {**one, **two}.items():
            reach[0][t] += p
        sides.append(_meet(one, two, S, key))
    for side in sides:
        for t, p in side.items():
            reach[1][t] += p
    return _meet(sides[0], sides[1], S, key)


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
    fields = {}                    # conference -> ({division: (sims, 3) top-three indices}, (sims, 2) wild cards, best first)
    division_win = np.zeros((sims, n), dtype=bool)
    for conf in {t["conference"] for t in teams}:
        conf_idx = [i for i, t in enumerate(teams) if t["conference"] == conf]
        qualified = np.zeros((sims, n), dtype=bool)
        tops = {}
        for div in {teams[i]["division"] for i in conf_idx}:
            members = np.array([i for i in conf_idx if teams[i]["division"] == div])
            order = np.argsort(-key[:, members], axis=1)
            rows = np.arange(sims)[:, None]
            top = members[order[:, :DIVISION_SPOTS]]
            qualified[rows, top] = True
            tops[div] = top
            division_win[np.arange(sims), members[order[:, 0]]] = True
        rest = np.array(conf_idx)
        masked = np.where(qualified[:, rest], -np.inf, key[:, rest])
        wc = rest[np.argsort(-masked, axis=1)[:, :WILD_CARDS]]
        qualified[np.arange(sims)[:, None], wc] = True
        make |= qualified
        fields[conf] = (tops, wc)

    reach = [np.zeros(n) for _ in range(4)]          # round 2, conference final, final, Cup
    if len(fields) == 2 and all(len(tops) == 2 for tops, _ in fields.values()):
        S = series_matrix(r)
        for s in range(sims):
            champs = []
            for conf in sorted(fields):
                tops, wc = fields[conf]
                champs.append(_bracket({d: [int(x) for x in t[s]] for d, t in tops.items()}, [int(x) for x in wc[s]], S, key[s], reach))
            for dist in champs:
                for t, p in dist.items():
                    reach[2][t] += p
            for t, p in _meet(champs[0], champs[1], S, key[s]).items():
                reach[3][t] += p
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
            "round2": float(reach[0][i] / sims),
            "conf_final": float(reach[1][i] / sims),
            "final": float(reach[2][i] / sims),
            "cup": float(reach[3][i] / sims),
            "rating": float(r[i]),
        }
    return out
