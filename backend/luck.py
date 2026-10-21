"""Luck and regression: who is scoring (or saving) more or less than the shots they took or faced predict.

Every stored shot has an expected-goals (xG) value from our own model. For a skater, goals minus the sum of
the xG of their shots says whether they are finishing better or worse than shot quality alone suggests. For
a goalie, the xG of the shots faced minus goals allowed (goals saved above expected) says the same about saves.

To tell luck from noise we also need to know how big a gap chance alone can produce. Each shot is a weighted
coin flip, so the variance of the goal total is the sum of xG * (1 - xG) over the shots. The gap divided by
the square root of that variance is a z-score: about 1 is ordinary, 1.5 or more is worth a look, 2 or more is
a real outlier for the sample so far.

Points luck adds an estimate for assists. We don't store who assisted each shot, so assists can't be modeled
shot by shot. Instead: a player collects assists on some share of the goals their teammates score while they
are on the ice (assist_rate, per teammate goal at even strength, pulled toward the league rate for forwards or
defensemen until the player has a real sample). Teammates scoring more than their shots predict while a player
is on the ice is then worth assist_rate assists of luck to that player. Points luck is own finishing luck plus
that assist luck, and its variance adds the two parts (the on-ice part treated as Poisson, variance = xGF).

Past seasons separate skill from luck. The model has no idea who is shooting, so elite finishers beat their xG
year after year. From a player's earlier seasons we estimate that edge (their goals above xG as a share of xG,
shrunk toward zero by PRIOR_XG expected goals so a short history can't claim much) and scale this season's xG by
it. Gaps measured that way (the *_adj figures) say whether a player is hot or cold for *them*, not for an
average shooter. With no history the two are the same.

What it does not know:
- The sample is small early in a season, so treat early flags as hints. Past seasons come from stored shots only
  (the last four plus this one), and skill can change with age, role and linemates.
- Only goals are modeled. The assist figure above is a rough estimate, and power-play assists are left out of it
  (on-ice expected goals are 5v5 only).
- Empty-net goals have no xG, so they are left out of the comparison on both sides.
"""
import math

Z_FLAG = 1.5       # |z| at or above this is flagged hot or cold
MIN_ATTEMPTS = 20  # unblocked shot attempts a skater needs to be listed by default
MIN_FACED = 50     # shots on goal a goalie needs to face to be listed by default
PRIOR_GOALS = 10   # teammate goals' worth of league-average assist rate blended into a player's own
PRIOR_XG = 30      # expected goals of "no edge" blended into a player's finishing history (about one season of a top scorer)
MIN_PERSIST_ATTEMPTS = 100  # shot attempts in both seasons for a skater to count in the year-over-year correlation
MIN_PERSIST_FACED = 300     # shots faced in both seasons for a goalie to count


def z_score(actual, expected, variance):
    """(actual - expected) / sd, or None when there is no variance to measure against."""
    if variance is None or variance <= 0:
        return None
    return (actual - expected) / math.sqrt(variance)


def flag(z):
    """'hot' when well above expectation, 'cold' when well below, else 'steady' (None without a z-score)."""
    if z is None:
        return None
    if z >= Z_FLAG:
        return "hot"
    if z <= -Z_FLAG:
        return "cold"
    return "steady"


def finishing_skill(prior):
    """A player's finishing edge from earlier seasons: goals above xG as a share of xG, pulled toward zero.

    prior: {model_goals, ixg, variance, seasons} summed over the earlier seasons, or None. 0.2 means they have
    scored about 20% more than an average shooter would from the same shots.
    """
    if not prior or not prior.get("seasons"):
        return 0.0
    return (prior["model_goals"] - prior["ixg"]) / (prior["ixg"] + PRIOR_XG)


def pearson(xs, ys):
    """Correlation of two equal-length lists, or None with fewer than 3 pairs or no spread in either."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def pace(total, games_played, games):
    """A season total scaled to a full season; None with no games played."""
    return None if not games_played else total / games_played * games


def assist_rate(ev_assists, teammate_goals, baseline):
    """Assists per teammate goal at even strength, blended with the league baseline until the sample is real."""
    return (ev_assists + PRIOR_GOALS * baseline) / (teammate_goals + PRIOR_GOALS)


def points_luck(r, diff, assist_baseline):
    """Points actual vs expected, or all None when the inputs aren't there.

    r needs points, season_goals, pp_goals, ev_points, ev_goals_for (the NHL's season figures), the player's own
    even-strength ev_model_goals and ev_ixg from the shot table, and the on-ice gf and xgf (5v5).
    """
    needed = ("points", "season_goals", "pp_goals", "ev_points", "ev_goals_for", "ev_model_goals", "ev_ixg", "gf", "xgf")
    empty = {"points": r.get("points"), "xpoints": None, "points_diff": None, "points_z": None, "points_flag": None,
             "assist_luck": None, "assist_rate": None}
    if assist_baseline is None or any(r.get(k) is None for k in needed):
        return empty
    own_ev_goals = max(0, r["season_goals"] - r["pp_goals"])
    ev_assists = max(0, r["ev_points"] - own_ev_goals)
    teammate_goals = max(0, r["ev_goals_for"] - own_ev_goals)
    k = assist_rate(ev_assists, teammate_goals, assist_baseline)
    # Goals the player's own shots account for are already in the finishing luck, so only teammates' goals count here.
    teammate_gap = (r["gf"] - r["ev_model_goals"]) - (r["xgf"] - r["ev_ixg"])
    assist_luck = k * teammate_gap
    total = diff + assist_luck
    variance = r["variance"] + k * k * max(r["xgf"] - r["ev_ixg"], 0)
    z = z_score(total, 0, variance)
    return {"points": r["points"], "xpoints": r["points"] - total, "points_diff": total, "points_z": z,
            "points_flag": flag(z), "assist_luck": assist_luck, "assist_rate": k}


def skater_line(r, games, assist_baseline=None, prior=None):
    """One skater's luck figures from aggregated shot and on-ice numbers.

    r: attempts, shots_on_goal, goals, model_goals, ixg, variance, games_played, and the on-ice totals
    gf, ga, xgf, xga (5v5), plus what points_luck needs. games is the length of a season, for the full-season
    pace. assist_baseline is the league's assists per teammate goal for this player's role (forward or defenseman).
    prior: the player's summed earlier seasons (see finishing_skill); fills the *_adj figures, which equal the
    plain ones when there is no history.
    """
    diff = r["model_goals"] - r["ixg"]
    z = z_score(r["model_goals"], r["ixg"], r["variance"])
    skill = finishing_skill(prior)
    diff_adj = r["model_goals"] - r["ixg"] * (1 + skill)
    z_adj = z_score(r["model_goals"], r["ixg"] * (1 + skill), r["variance"])
    pts, pts_adj = points_luck(r, diff, assist_baseline), points_luck(r, diff_adj, assist_baseline)
    history = {
        "has_history": bool(prior and prior.get("seasons")), "prior_seasons": (prior or {}).get("seasons", 0),
        "prior_diff": None if not prior else prior["model_goals"] - prior["ixg"],
        "prior_z": None if not prior else z_score(prior["model_goals"], prior["ixg"], prior["variance"]),
        "skill": skill,
        "diff_adj": diff_adj, "z_adj": z_adj, "flag_adj": flag(z_adj),
        "points_diff_adj": pts_adj["points_diff"], "points_z_adj": pts_adj["points_z"],
        "points_flag_adj": pts_adj["points_flag"], "xpoints_adj": pts_adj["xpoints"],
    }
    sog = r["shots_on_goal"]
    # Goals only ever come from shots on goal, so expected goals per on-goal shot is the fair comparison for shooting %.
    onice_diff = None
    if None not in (r["gf"], r["ga"], r["xgf"], r["xga"]):
        onice_diff = (r["gf"] - r["ga"]) - (r["xgf"] - r["xga"])
    return {
        "diff": diff, "z": z, "flag": flag(z),
        "sh_pct": r["goals"] / sog if sog else None,
        "xsh_pct": r["ixg"] / sog if sog else None,
        "goals_pace": pace(r["goals"], r["games_played"], games),
        "xg_pace": pace(r["ixg"], r["games_played"], games),
        "onice_diff": onice_diff,
        **pts, **history,
    }


def goalie_line(r):
    """One goalie's luck figures. r: faced, goals, model_goals, xga (xG faced), variance."""
    gsax = r["xga"] - r["model_goals"]
    z = z_score(r["model_goals"], r["xga"], r["variance"])
    z = None if z is None else -z  # fewer goals than expected is the good direction for a goalie
    faced = r["faced"]
    return {
        "gsax": gsax, "z": z, "flag": flag(z),
        "sv_pct": 1 - r["goals"] / faced if faced else None,
        "xsv_pct": 1 - r["xga"] / faced if faced else None,
        "gsax_per_100": gsax / faced * 100 if faced else None,
    }
