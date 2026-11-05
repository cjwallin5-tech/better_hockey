"""Backtest: how good is the rest-of-season goalie projection (projections.goalie_final / /api/projections/goalies)?

Run from backend/ (needs shot_hist and team_game_hist): .venv/bin/python -I analysis/backtest_goalie_projection.py

Replays the production method on each stored past season at three checkpoints (after 10, 25 and 40 team games), using only what
was known then, and scores it against what the goalies actually did over the rest of the season:
  - starts to come: probable_goalies.next_distribution chained over the team's remaining games (as _goalie_plans does)
  - what a start is worth: streaming.expected_line from matchups.team_ratings (xG for and against so far, pulled to the league)
Past seasons have no goalie_game rows, so goalie games are rebuilt from shot_hist: the goalie to face the team's first shot is the
starter, a start earns the win when the team won, and a shutout needs the team to allow nothing with that goalie alone in net. That
is the same as the NHL's record except for relief wins (rare). Differences from production: the goalie's own small effect
(matchups.goalie_estimate) is left out (it is worth about 2%, see backtest_goalie_persistence.py), the overtime-loss share is fixed
at 0.23 (OT losses are not scored here) and the league rates come from each team's first N games.

Scored by root-mean-square error of the rest-of-season totals per goalie (lower is better), with the mean error (bias: predicted
minus actual). Three comparisons:
  A  starts to come: production chain vs. the goalie's share of starts so far vs. his share of the last 10, times games left
  B  what a start is worth, given the TRUE number of starts: team-rating model vs. league average vs. the goalie's own record
  C  end to end: production vs. share-so-far x league average vs. share-so-far x his own record (pulled toward the league)
"""
from pathlib import Path
import math, sys
from collections import defaultdict

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config, matchups, probable_goalies, streaming

CHECKPOINTS = (10, 25, 40)
OWN_PRIOR_STARTS = 20      # starts' worth of league-average results blended into a goalie's own record (baseline only)
OTL_SHARE = 0.23
START_SHARE_K = 20         # the share of starts so far gets weight n / (n + K) against the chain (see the blend table at the end)
STATS = ("wins", "saves", "ga", "shutouts")

# ---- load ------------------------------------------------------------------------------------------------
with psycopg.connect(config.DATABASE_URL) as conn:
    tg = {}      # (game_id, is_home) -> team game
    for season, gid, date, team, opp, home, gf, ga, win in conn.execute(
            """SELECT season_id, game_id, game_date, team, opponent, is_home, goals_for, goals_against, wins
               FROM team_game_hist WHERE is_home IS NOT NULL AND team IS NOT NULL"""):
        tg[gid, home] = {"season": season, "game_id": gid, "date": date, "team": team, "opp": opp, "home": home,
                         "gf": gf, "ga": ga, "win": win}
    xg_for = defaultdict(float)          # (game_id, shooter is_home) -> expected goals by that side
    for gid, home, x in conn.execute("SELECT game_id, is_home, sum(xg) FROM shot_hist WHERE is_home IS NOT NULL AND xg IS NOT NULL GROUP BY 1, 2"):
        xg_for[gid, home] = float(x)
    ongoal = defaultdict(int)            # (game_id, shooter is_home) -> shots on goal (for the league's shots per game)
    goals_by = defaultdict(int)          # (game_id, shooter is_home) -> goals scored by that side (shot table, no shootout goals)
    for gid, home, sog, goals in conn.execute(
            """SELECT game_id, is_home, count(*) FILTER (WHERE kind IN ('shot', 'goal')), count(*) FILTER (WHERE kind = 'goal')
               FROM shot_hist WHERE is_home IS NOT NULL GROUP BY 1, 2"""):
        ongoal[gid, home], goals_by[gid, home] = sog, goals
    goalie_rows = defaultdict(list)      # (game_id, goalie's is_home) -> [(goalie, shots, goals, first event)]
    for gid, home, goalie, sog, goals, first in conn.execute(
            """SELECT game_id, is_home, goalie_id, count(*) FILTER (WHERE kind IN ('shot', 'goal')),
                      count(*) FILTER (WHERE kind = 'goal'), min(coalesce(period, 1) * 100000 + coalesce(time_sec, 0))
               FROM shot_hist WHERE goalie_id IS NOT NULL AND is_home IS NOT NULL GROUP BY 1, 2, 3"""):
        goalie_rows[gid, not home].append((goalie, sog, goals, first))

# goalie games: goalie -> [dict], and the starter of every team game
ggames = defaultdict(list)
starter = {}
for (gid, home), rows in goalie_rows.items():
    t = tg.get((gid, home))
    if not t:
        continue
    rows.sort(key=lambda r: r[3])
    starter[gid, home] = rows[0][0]
    for goalie, sog, goals, _ in rows:
        started = goalie == rows[0][0]
        ggames[goalie].append({"season": t["season"], "game_id": gid, "date": t["date"], "team": t["team"], "started": started,
                               "wins": 1 if started and t["win"] else 0, "saves": sog - goals, "ga": goals, "shots": sog,
                               "shutouts": 1 if started and len(rows) == 1 and t["ga"] == 0 else 0})

seasons = sorted({t["season"] for t in tg.values()})
team_games = defaultdict(lambda: defaultdict(list))     # season -> team -> [team game] in date order
for t in tg.values():
    team_games[t["season"]][t["team"]].append(t)
for s in team_games.values():
    for lst in s.values():
        lst.sort(key=lambda t: (t["date"], t["game_id"]))


def rmse(errors):
    return math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else float("nan")


def bias(errors):
    return sum(errors) / len(errors) if errors else float("nan")


def goalie_pred(season, n):
    """Yield (goalie, team, our predictions, baselines inputs) for every goalie who played in the first n games of his team."""
    games = team_games[season]
    known = {team: lst[:n] for team, lst in games.items()}
    # team ratings and league rates from the first n games of every team
    rows, league_games, league_shots, league_goals = [], 0, 0, 0
    for team, lst in known.items():
        xgf = sum(xg_for[t["game_id"], t["home"]] for t in lst)
        xga = sum(xg_for[t["game_id"], not t["home"]] for t in lst)
        rows.append({"team": team, "games": len(lst), "xgf": xgf, "xga": xga})
        league_games += len(lst)
        league_shots += sum(ongoal[t["game_id"], t["home"]] for t in lst)
        league_goals += sum(goals_by[t["game_id"], t["home"]] for t in lst)
    ratings, _ = matchups.team_ratings(rows)
    league = {"shots_pg": league_shots / league_games, "goals_pg": league_goals / league_games}
    g_shots = g_goals = 0       # the same, counting only shots a goalie faced (no empty-net goals): what a goalie's stat line counts
    # shots a goalie faced in a game, summed over both teams' goalies, per team-game
    for team, lst in known.items():
        for t in lst:
            for _, sog, goals, _ in goalie_rows.get((t["game_id"], t["home"]), []):
                g_shots += sog
                g_goals += goals
    league_fixed = {"shots_pg": g_shots / league_games, "goals_pg": g_goals / league_games}
    # league repeat rate on back-to-backs, from the known games
    b2b = repeats = 0
    for team, lst in known.items():
        for older, newer in zip(lst, lst[1:]):
            if (newer["date"] - older["date"]).days == 1 and (older["game_id"], older["home"]) in starter and (newer["game_id"], newer["home"]) in starter:
                b2b += 1
                repeats += starter[older["game_id"], older["home"]] == starter[newer["game_id"], newer["home"]]
    p_repeat = probable_goalies.repeat_rate(b2b, repeats)
    # league average per start (baseline)
    starts_all = sum(1 for lst in known.values() for t in lst if (t["game_id"], t["home"]) in starter)
    league_per_start = {"wins": sum(t["win"] for lst in known.values() for t in lst if (t["game_id"], t["home"]) in starter) / starts_all}
    sg = [g for glist in ggames.values() for g in glist if g["season"] == season and g["started"]]
    # (per-start league rates from the known games only)
    cutoff = {team: lst[-1]["date"] for team, lst in known.items()}
    kn = [g for g in sg if g["date"] <= cutoff.get(g["team"], g["date"]) and g["game_id"] in {t["game_id"] for t in known[g["team"]]}]
    for k in ("saves", "ga", "shutouts"):
        league_per_start[k] = sum(g[k] for g in kn) / len(kn)
    league_per_start["wins"] = sum(g["wins"] for g in kn) / len(kn)
    league_starts = {"shots_pg": sum(g["shots"] for g in kn) / len(kn), "goals_pg": league_per_start["ga"]}   # what a STARTER faced

    out = []
    for team, lst in known.items():
        rest = games[team][n:]
        if not rest:
            continue
        recent = [(starter[t["game_id"], t["home"]], "") for t in reversed(lst) if (t["game_id"], t["home"]) in starter]
        if not recent:
            continue
        # chain the starter distribution over the remaining games, as _goalie_plans does
        dist, prepend, prev_date, plan = {recent[0][0]: 1.0}, False, lst[-1]["date"], []
        for g in rest:
            tired = (g["date"] - prev_date).days == 1
            dist = probable_goalies.next_distribution(recent, dist, tired, p_repeat, prepend)
            prepend, prev_date = True, g["date"]
            plan.append((g, dict(dist)))
        # goalies who played for the team so far (production: goalie_season rows with this team)
        mine = {gl for t in lst for gl in [r[0] for r in goalie_rows.get((t["game_id"], t["home"]), [])]}
        for gl in mine:
            games_before = [g for g in ggames[gl] if g["season"] == season and g["game_id"] in {t["game_id"] for t in lst}]
            if not games_before or games_before[-1]["team"] != team:
                continue
            prod = dict.fromkeys(("starts",) + STATS, 0.0)
            true_starts_model = {}
            for g, d in plan:
                p = d.get(gl, 0.0)
                opp = ratings.get(g["opp"])
                own = ratings.get(team)
                if p <= 0 or opp is None or own is None:
                    continue
                line = streaming.expected_line(own, opp, league["goals_pg"], league["shots_pg"], 1.0, OTL_SHARE)
                prod["starts"] += p
                prod["wins"] += p * line["win"]
                prod["saves"] += p * line["saves"]
                prod["ga"] += p * line["ga"]
                prod["shutouts"] += p * line["shutout"]
            # the model's per-start value for this goalie's own remaining games, weighted by his start chances (used in B)
            def per_start(lg):
                vals, ws = {k: 0.0 for k in STATS}, 0.0
                for g, d in plan:
                    p = d.get(gl, 0.0)
                    opp, own = ratings.get(g["opp"]), ratings.get(team)
                    if p <= 0 or opp is None or own is None:
                        continue
                    line = streaming.expected_line(own, opp, lg["goals_pg"], lg["shots_pg"], 1.0, OTL_SHARE)
                    ws += p
                    for k, lk in (("wins", "win"), ("saves", "saves"), ("ga", "ga"), ("shutouts", "shutout")):
                        vals[k] += p * line[lk]
                return {k: vals[k] / ws for k in STATS} if ws else None
            model_per_start, fixed_per_start = per_start(league), per_start(league_fixed)
            norm_per_start = per_start(league_starts)
            # actual rest of the season (any team, after his team's checkpoint date)
            after = [g for g in ggames[gl] if g["season"] == season and g["date"] > lst[-1]["date"]]
            actual = {"starts": sum(g["started"] for g in after), **{k: sum(g[k] for g in after) for k in STATS}}
            mystarts = [g for g in games_before if g["started"]]
            now_all = {k: sum(g[k] for g in games_before) for k in ("saves", "ga")}
            last_ids = {t["game_id"] for t in lst[-10:]}
            last10 = [g for g in games_before if g["started"] and g["game_id"] in last_ids]
            out.append({"goalie": gl, "team": team, "left": len(rest), "n": n, "pred": prod, "actual": actual,
                        "now_all": now_all, "model_per_start": model_per_start, "fixed_per_start": fixed_per_start, "norm_per_start": norm_per_start, "starts_so_far": len(mystarts), "last10": len(last10),
                        "own_totals": {k: sum(g[k] for g in mystarts) for k in STATS}, "league_per_start": league_per_start})
    return out


rows_by_n = defaultdict(list)
for season in seasons:
    for n in CHECKPOINTS:
        rows_by_n[n].extend(goalie_pred(season, n))

for n in CHECKPOINTS:
    rows = rows_by_n[n]
    # only goalies who actually play afterwards or were predicted to (everyone in `rows`), so a goalie who fades out counts
    print(f"\n=== after {n} team games: {len(rows)} goalie-seasons ({len(seasons)} seasons)")

    # A: starts to come
    prod = [r["pred"]["starts"] - r["actual"]["starts"] for r in rows]
    share = [r["left"] * r["starts_so_far"] / n - r["actual"]["starts"] for r in rows]
    l10 = [r["left"] * r["last10"] / min(10, n) - r["actual"]["starts"] for r in rows]
    print("A  starts to come                rmse     bias")
    for name, e in (("production chain", prod), ("share so far", share), ("share of last 10", l10)):
        print(f"   {name:24s} {rmse(e):7.3f} {bias(e):+8.3f}")
    # the same for goalies who will start at least 10 games (the ones fantasy cares about)
    big = [r for r in rows if r["actual"]["starts"] >= 10]
    print(f"   (goalies with 10+ starts to come, n={len(big)}): production {rmse([r['pred']['starts'] - r['actual']['starts'] for r in big]):.3f}, "
          f"share so far {rmse([r['left'] * r['starts_so_far'] / n - r['actual']['starts'] for r in big]):.3f}, "
          f"last 10 {rmse([r['left'] * r['last10'] / min(10, n) - r['actual']['starts'] for r in big]):.3f}")

    # B: what a start is worth, given the true starts
    print("B  value of a start (true starts)  model   fixed   +starts   league  own(k=%d)   <- rmse of the rest-of-season total" % OWN_PRIOR_STARTS)
    usable = [r for r in rows if r["model_per_start"] and r["fixed_per_start"] and r["norm_per_start"] and r["actual"]["starts"] > 0]
    for k in STATS:
        m, fx, nm, lg, ow = [], [], [], [], []
        for r in usable:
            s = r["actual"]["starts"]
            lps = r["league_per_start"][k]
            own_rate = (r["own_totals"][k] + OWN_PRIOR_STARTS * lps) / (r["starts_so_far"] + OWN_PRIOR_STARTS)
            m.append(s * r["model_per_start"][k] - r["actual"][k])
            fx.append(s * r["fixed_per_start"][k] - r["actual"][k])
            nm.append(s * r["norm_per_start"][k] - r["actual"][k])
            lg.append(s * lps - r["actual"][k])
            ow.append(s * own_rate - r["actual"][k])
        print(f"   {k:10s} {rmse(m):12.3f} {rmse(fx):7.3f} {rmse(nm):7.3f} {rmse(lg):8.3f} {rmse(ow):9.3f}   (n={len(usable)}; bias model {bias(m):+.2f}, fixed {bias(fx):+.2f}, +starts {bias(nm):+.2f}, league {bias(lg):+.2f})")

    # C: end to end. "new" = blended starts (a = n / (n + START_SHARE_K) toward the share so far) x the per-start model fed by
    # what starters faced
    print("C  end to end                    production      new   share x league  share x own      <- rmse of the rest-of-season total")
    a = n / (n + START_SHARE_K)
    cand = [r for r in rows if r["norm_per_start"]]
    for k in ("starts",) + STATS:
        p, nw, sl, so = [], [], [], []
        for r in cand:
            share_starts = r["left"] * r["starts_so_far"] / n
            blended = (1 - a) * r["pred"]["starts"] + a * share_starts
            if k == "starts":
                p.append(r["pred"]["starts"] - r["actual"]["starts"])
                nw.append(blended - r["actual"]["starts"])
                sl.append(share_starts - r["actual"]["starts"])
                continue
            lps = r["league_per_start"][k]
            own_rate = (r["own_totals"][k] + OWN_PRIOR_STARTS * lps) / (r["starts_so_far"] + OWN_PRIOR_STARTS)
            p.append(r["pred"][k] - r["actual"][k])
            nw.append(blended * r["norm_per_start"][k] - r["actual"][k])
            sl.append(share_starts * lps - r["actual"][k])
            so.append(share_starts * own_rate - r["actual"][k])
        print(f"   {k:10s} {rmse(p):12.3f} {rmse(nw):8.3f} {rmse(sl):14.3f} {rmse(so) if so else float('nan'):12.3f}   (bias production {bias(p):+.2f}, new {bias(nw):+.2f})")

# ---- diagnostic: average value of one start, predicted vs. what happened (weighted by true rest starts) -----
print("\n=== per-start diagnostic (mean over goalie-seasons, weighted by actual rest starts)")
for n in CHECKPOINTS:
    us = [r for r in rows_by_n[n] if r["model_per_start"] and r["fixed_per_start"] and r["norm_per_start"] and r["actual"]["starts"] > 0]
    w = sum(r["actual"]["starts"] for r in us)
    for k in STATS:
        mp = sum(r["actual"]["starts"] * r["model_per_start"][k] for r in us) / w
        lp = sum(r["actual"]["starts"] * r["league_per_start"][k] for r in us) / w
        fp = sum(r["actual"]["starts"] * r["norm_per_start"][k] for r in us) / w
        ap = sum(r["actual"][k] for r in us) / w
        print(f"n={n:2d} {k:10s} model {mp:7.3f}  fixed+starts {fp:7.3f}  league-so-far {lp:7.3f}  actual {ap:7.3f}")


# ---- starts: how much to lean on the goalie's share of starts so far -------------------------------------------
# blended = (1 - a) x production chain + a x (games left x starts so far / team games so far), a = n / (n + K)
print("\n=== starts blend: rmse of rest-of-season starts, a = n / (n + K)   (K = inf is the chain alone; K = 0 the share alone)")
Ks = (0, 5, 10, 20, 40, 80, float("inf"))
print("      " + "".join(f"K={k:<7}" for k in Ks))
for n in CHECKPOINTS:
    rows = rows_by_n[n]
    line = []
    for K in Ks:
        a = 0.0 if K == float("inf") else (1.0 if K == 0 else n / (n + K))
        e = [(1 - a) * r["pred"]["starts"] + a * r["left"] * r["starts_so_far"] / n - r["actual"]["starts"] for r in rows]
        line.append(f"{rmse(e):<9.3f}")
    print(f"n={n:<3d} " + "".join(line))



# ---- D: an 80% range for the rest of the season, fitted on the new pipeline ----------------------------------
# variance of (actual - predicted) rest total = A x S + B x R^2, S = expected starts to come, R = the predicted total: the first
# part is the noise in each start's result, the second the uncertainty in how many starts and how the goalie's rate runs.
Z80 = 1.2816


def new_pred(r, n):
    a = n / (n + START_SHARE_K)
    S = (1 - a) * r["pred"]["starts"] + a * r["left"] * r["starts_so_far"] / n
    return S, {k: S * r["norm_per_start"][k] for k in STATS}


def fit_ab(points):
    """Non-negative least squares for e2 = A x S + B x R2 over (S, R2, e2) points."""
    sxx = sum(S * S for S, _, _ in points); sxy = sum(S * R2 for S, R2, _ in points); syy = sum(R2 * R2 for _, R2, _ in points)
    sxe = sum(S * e2 for S, _, e2 in points); sye = sum(R2 * e2 for _, R2, e2 in points)
    det = sxx * syy - sxy * sxy
    A, B = (sxe * syy - sye * sxy) / det, (sye * sxx - sxe * sxy) / det
    if A < 0:
        A, B = 0.0, sye / syy
    if B < 0:
        A, B = sxe / sxx, 0.0
    return A, B


print("\n=== D: 80% range for the rest-of-season total: Var = A x S + B x R^2 (fitted on all checkpoints pooled)")
FIT = {}
for k in STATS:
    pts = []
    for n in CHECKPOINTS:
        for r in rows_by_n[n]:
            if not r["norm_per_start"]:
                continue
            S, R = new_pred(r, n)
            pts.append((S, R[k] ** 2, (r["actual"][k] - R[k]) ** 2))
    FIT[k] = fit_ab(pts)
    cov = []
    for n in CHECKPOINTS:
        inside = tot = 0
        for r in rows_by_n[n]:
            if not r["norm_per_start"]:
                continue
            S, R = new_pred(r, n)
            sd = math.sqrt(FIT[k][0] * S + FIT[k][1] * R[k] ** 2)
            tot += 1
            inside += abs(r["actual"][k] - R[k]) <= Z80 * sd
        cov.append(f"{n}: {inside / tot:.0%}")
    print(f"   {k:10s} A={FIT[k][0]:.4f} B={FIT[k][1]:.5f}   coverage of the 80% range by checkpoint: " + ", ".join(cov))
    # coverage among goalies who will start 10+ (the ones that matter)
    inside = tot = 0
    for n in CHECKPOINTS:
        for r in rows_by_n[n]:
            if not r["norm_per_start"] or r["actual"]["starts"] < 10:
                continue
            S, R = new_pred(r, n)
            sd = math.sqrt(FIT[k][0] * S + FIT[k][1] * R[k] ** 2)
            tot += 1
            inside += abs(r["actual"][k] - R[k]) <= Z80 * sd
    print(f"{'':13s}   (10+ starts to come: {inside / tot:.0%} of {tot})")

# ---- E: projected save percentage and goals against per start -------------------------------------------------
print("\n=== E: projected final save % and goals against per start (goalies with 600+ shots / 15+ starts over the season)")
for n in CHECKPOINTS:
    sv = {"projection": [], "to date": [], "league": []}
    ga = {"projection": [], "to date": [], "league": []}
    for r in rows_by_n[n]:
        if not r["norm_per_start"]:
            continue
        S, R = new_pred(r, n)
        ps = r["norm_per_start"]
        now_saves, now_ga = r["now_all"]["saves"], r["now_all"]["ga"]
        fin_saves, fin_ga = now_saves + r["actual"]["saves"], now_ga + r["actual"]["ga"]
        fin_shots = fin_saves + fin_ga
        fin_starts = r["starts_so_far"] + r["actual"]["starts"]
        lps = r["league_per_start"]
        if fin_shots >= 600 and now_saves + now_ga > 0:
            truth = fin_saves / fin_shots
            pred = (now_saves + R["saves"]) / (now_saves + now_ga + S * (ps["saves"] + ps["ga"]))
            sv["projection"].append(pred - truth)
            sv["to date"].append(now_saves / (now_saves + now_ga) - truth)
            sv["league"].append(lps["saves"] / (lps["saves"] + lps["ga"]) - truth)
        if fin_starts >= 15 and r["starts_so_far"] > 0:
            truth = fin_ga / fin_starts
            ga["projection"].append((now_ga + R["ga"]) / (r["starts_so_far"] + S) - truth)
            ga["to date"].append(now_ga / r["starts_so_far"] - truth)
            ga["league"].append(lps["ga"] - truth)
    print(f"n={n:2d} save %    " + "   ".join(f"{k} {rmse(v):.4f} ({bias(v):+.4f})" for k, v in sv.items()) + f"   (n={len(sv['league'])})")
    print(f"     GA/start  " + "   ".join(f"{k} {rmse(v):.3f} ({bias(v):+.3f})" for k, v in ga.items()) + f"   (n={len(ga['league'])})")
