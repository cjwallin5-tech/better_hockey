"""Goalie matchup fit: how a team's shot zones line up with a goalie's weak and strong zones.

For a goalie, each of the nine zones (goaliemap.py) has a record of goals saved above an average goalie's per shot. Those rates are
shrunk toward zero by K pseudo-shots, because a goalie's zone record is thin; K = 300 is what a backtest on four seasons picked
(analysis/backtest_goalie_zones.py: from earlier seasons only, the shrunk zone detail predicted the goals he allowed later with a coefficient of
about 1.0, standard error 0.4, on top of his overall record at 0.9 +- 0.2).

For a team shooting at him, its expected shots on goal per game N and its shot diet (the share of its shots from each zone) give, from
the shooting team's side (positive = more goals for the shooting team):
  goalie_goals: what the goalie alone is worth against an average team, -N x his shrunk overall rate (positive = a leaky goalie);
  fit_goals:    what the team's diet adds on top, -N x sum(share_z x (rate_z - overall rate)); positive means the team's shots come from
                the zones where he leaks more than his average, negative means they come from zones where he is stronger than usual.
The fit is about 0.14 goals a game at one standard deviation, so it is a nudge, not a forecast.
"""
import goaliemap as gm

K = 300            # shrinkage, in pseudo-shots
MIN_FACED = 200    # a goalie with fewer located shots than this gets no tip
MIN_TEAM_SHOTS = 150
PRIOR_SHOTS = 300  # weight, in shots, of last season's diet when blending with this season's
NOTABLE = 0.10     # goals per game
LEAGUE_SHOTS_PER_GAME = 28.0


def goalie_rates(summary, k=K):
    """{(range, lane): rate} and the overall rate, in goals saved above average per shot, from goaliemap.summarize output."""
    rates = {(z["range"], z["lane"]): z["gsax"] / (z["shots"] + k) for z in summary["zones"]}
    t = summary["total"]
    return rates, t["gsax"] / (t["shots"] + k)


def lane_for(side, catches):
    """Glove or blocker for a rink side ('pos' is positive rink y, the shooter's left; 'neg' the other), or middle."""
    if side == "middle":
        return "middle"
    glove_is_pos = catches == "R"                 # an unknown hand is treated as the common left catch, as in the goalie map
    return "glove" if (side == "pos") == glove_is_pos else "blocker"


def diet(current, prior=None, prior_shots=PRIOR_SHOTS):
    """Zone shares for a team from {(range, side): shots} this season, blended with last season's. Returns (shares, total shots)."""
    prior = prior or {}
    n_cur, n_prior = sum(current.values()), sum(prior.values())
    w = prior_shots / n_prior if n_prior else 0.0
    mix = {z: current.get(z, 0) + w * prior.get(z, 0) for z in set(current) | set(prior)}
    total = sum(mix.values())
    return ({z: v / total for z, v in mix.items()} if total else {}), n_cur + (prior_shots if n_prior else 0)


def fit(shares, shots_per_game, rates, overall, catches, league_shares=None):
    """The matchup for one team shooting at one goalie. shares are {(range, side): share}; league_shares the same for the league (optional,
    only used to report how far the team's diet is from usual)."""
    by_zone = {}
    for (rng, side), s in shares.items():
        z = (rng, lane_for(side, catches))
        by_zone[z] = by_zone.get(z, 0.0) + s
    parts = []
    for z, share in by_zone.items():
        rate = rates.get(z, 0.0)
        parts.append({"range": z[0], "lane": z[1], "share": round(share, 4), "rate_per_100": round(-rate * 100, 2),
                      "goals": round(-shots_per_game * share * (rate - overall), 3)})
    parts.sort(key=lambda p: -abs(p["goals"]))
    if league_shares:
        league = {}
        for (rng, side), s in league_shares.items():
            z = (rng, lane_for(side, catches))
            league[z] = league.get(z, 0.0) + s
        for p in parts:
            p["league_share"] = round(league.get((p["range"], p["lane"]), 0.0), 4)
    return {
        "fit_goals": round(sum(p["goals"] for p in parts), 3),
        "goalie_goals": round(-shots_per_game * overall, 3),
        "shots_per_game": round(shots_per_game, 1),
        "zones": parts[:3],
        "notable": abs(sum(p["goals"] for p in parts)) >= NOTABLE,
    }


# --- Wording (the What to watch page says the same in frontend/src/matchupTip.js) ---------------------------
RANGE_WORDS = {"close": "close range", "mid": "mid-range", "long": "long range"}
LANE_WORDS = {"glove": "glove side", "middle": "the middle", "blocker": "blocker side"}


def zone_label(z):
    return f"{RANGE_WORDS[z['range']]}, {LANE_WORDS[z['lane']]}".replace(", the middle", " through the middle")


def _signed(v, digits=1):
    return f"{'+' if v > 0 else ''}{v:.{digits}f}"


def _pct(v):
    return f"{int(v * 100 + 0.5)}%"


def _where(f):
    z = f["zones"][0]
    share = f" ({_pct(z['share'])} of their shots, {_pct(z['league_share'])} league-wide)" if z.get("league_share") is not None else ""
    return z, f"{zone_label(z)}{share}"


def _overall_per_100(f):
    return (f["goalie_goals"] / f["shots_per_game"]) * 100 if f.get("shots_per_game") else 0.0


def sentence(f, who=None):
    """The matchup from the shooting team's side, as the What to watch page words it. `who` replaces the goalie's name in the
    sentence (the digest passes "He" because its line already names him)."""
    z, where = _where(f)
    goalie = who or f["goalie"]["name"]
    overall = _overall_per_100(f)
    if f["fit_goals"] > 0:
        body = f"{goalie} gives up {_signed(z['rate_per_100'])} goals per 100 shots from {where}, against {_signed(overall)} overall."
    else:
        body = (f"{goalie} is better than his average from {where}: {_signed(z['rate_per_100'])} goals per 100 shots there, "
                f"against {_signed(overall)} overall.")
    return f"{body} Worth about {_signed(f['fit_goals'], 2)} goals to {f['team']}."


def goalie_sentence(f, who=None):
    """The same matchup from the defending goalie's side: how many more or fewer goals against than his usual the shot mix is worth."""
    z, where = _where(f)
    g = who or f["goalie"]["name"]
    more = f["fit_goals"] > 0
    return (f"{f['team']}'s shots come from {where}, where {g} {'gives up' if more else 'is stronger than usual:'} "
            f"{_signed(z['rate_per_100'])} goals per 100 shots; about {abs(f['fit_goals']):.2f} {'more' if more else 'fewer'} goals against than his usual.")


def start_note(goalie):
    """A short note on whether the goalie is confirmed or only likely to start."""
    if goalie.get("confirmed"):
        return "confirmed starter"
    p = goalie.get("probability")
    return f"likely starter, {_pct(p)}" if p is not None else "starter unclear"
