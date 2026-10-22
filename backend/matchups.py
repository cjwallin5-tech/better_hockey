"""Matchup quality: how favorable a game is for the players in it, and how soft or tough a week's schedule is.

For a skater, a game is favorable when the opponent gives up a lot of good chances and has a goalie who stops fewer
than he should. For a goalie it is the opposite side of the same coin: the opponent's offense.

Team ratings come from expected goals (xG) from stored shots, not from goals: a backtest on four past seasons found
that a team's early-season goals against predicts the rest of the season worse than simply assuming the league
average (error 0.62 against 0.35 goals a game after 10 games), while its xG against, pulled toward the league average
by TEAM_PRIOR_GAMES games' worth, cut that error by about 10% (0.31). Goalie quality barely repeats: pooling a goalie's
earlier seasons of goals saved above expected predicts the next season only about 2% better than assuming an average goalie
(correlation about 0.16), so it is pulled toward zero by GOALIE_PRIOR_SHOTS shots and moves a matchup by a point or two.

Ratings are ratios to the league average: 1.08 means a team that gives up (or scores) 8% more than average. A game's
ratio for a skater is the opponent's defense ratio times the expected goalie effect; for a goalie it is the opponent's
offense ratio. Over a stretch of games, the opportunity index is the sum of (ratio - 1): +0.2 is worth about a fifth of an
extra average game of chances.

What it does not know: injuries and lineup changes (a hot team that lost its top defenseman), rest and travel,
home-ice advantage, or which goalie actually starts (the expected goalie effect is weighted by this season's starts).
Differences between teams are modest, especially early, so read this as a nudge, not a verdict.
"""
TEAM_PRIOR_GAMES = 20       # games' worth of league-average play blended into a team's rate
GOALIE_PRIOR_SHOTS = 8000   # shots' worth of average goaltending blended into a goalie's record
LABEL_AT = 0.04             # a ratio this far from 1 is called soft or tough, otherwise neutral


def shrunk_rate(total, games, league_rate, prior=TEAM_PRIOR_GAMES):
    """Per-game rate pulled toward the league rate: (total + prior x league) / (games + prior)."""
    return (total + prior * league_rate) / (games + prior)


def team_ratings(rows):
    """Offense and defense ratios for every team.

    rows: [{team, games, xgf, xga}] (xG for and against so far). Returns {team: {games, xgf_pg, xga_pg, off_ratio,
    def_ratio}} and the league's xG per team-game (shots are for one team and against another, so one rate serves
    both). off_ratio above 1 scores more than average; def_ratio above 1 gives up more than average.
    """
    games = sum(r["games"] for r in rows)
    if games == 0:
        return {}, None
    league = sum(r["xgf"] for r in rows) / games
    if league <= 0:
        return {}, None
    out = {}
    for r in rows:
        off = shrunk_rate(r["xgf"], r["games"], league)
        dfn = shrunk_rate(r["xga"], r["games"], league)
        out[r["team"]] = {"games": r["games"], "xgf_pg": r["xgf"] / r["games"] if r["games"] else None,
                          "xga_pg": r["xga"] / r["games"] if r["games"] else None,
                          "off_ratio": off / league, "def_ratio": dfn / league}
    return out, league


def goalie_estimate(gsax, shots, prior=GOALIE_PRIOR_SHOTS):
    """Goals saved above expected per 100 shots we expect from a goalie, pulled hard toward 0 (an average goalie)."""
    return gsax / (shots + prior) * 100


def goalie_multiplier(per_100, shots_pg, goals_pg):
    """The factor on an opponent's goals when this goalie is in net: below 1 stops more than average.
    per_100 goals saved per 100 shots over shots_pg shots a game is per_100/100 x shots_pg goals a game of goals_pg."""
    if not goals_pg:
        return 1.0
    return 1 - per_100 / 100 * shots_pg / goals_pg


def expected_goalie_multiplier(goalies):
    """Start-weighted goalie factor for a team. goalies: [(starts, multiplier)]; 1.0 with no starts yet."""
    total = sum(s for s, _ in goalies)
    return sum(s * m for s, m in goalies) / total if total else 1.0


def skater_ratio(def_ratio, goalie_mult):
    """How favorable a game is for skaters playing this opponent: above 1 is softer than average."""
    return def_ratio * goalie_mult


def label(ratio, at=LABEL_AT):
    """'soft' (favorable), 'tough' or 'neutral' for a ratio where above 1 is favorable."""
    if ratio is None:
        return None
    return "soft" if ratio >= 1 + at else "tough" if ratio <= 1 - at else "neutral"


def schedule_summary(ratios):
    """Games, average ratio and opportunity index (sum of ratio - 1) over a list of per-game ratios."""
    ratios = [r for r in ratios if r is not None]
    if not ratios:
        return {"games": 0, "avg": None, "index": 0.0}
    return {"games": len(ratios), "avg": sum(ratios) / len(ratios), "index": sum(r - 1 for r in ratios)}


MIRROR = {"tired": "edge", "edge": "tired"}   # the opponent's rest situation, seen from the other bench


def rest_shift(gaps, kind):
    """Goals a game a team scores more (+) or fewer (-) than usual in this rest situation; 0 unless tired or edge.
    gaps: {kind: goals-for gap} from fatigue.effects; a missing figure counts as 0."""
    return (gaps or {}).get(kind) or 0.0


def skater_game_ratio(opp_ratio, own_kind, gaps, goals_pg):
    """A skater's game ratio (see skater_ratio) scaled by how rest moves their own team's scoring."""
    if opp_ratio is None or not goals_pg:
        return opp_ratio
    return opp_ratio * (1 + rest_shift(gaps, own_kind) / goals_pg)


def goalie_game_ratio(opp_off_ratio, own_kind, gaps, goals_pg):
    """A goalie's game ratio against an offense of opp_off_ratio, scaled by how rest moves that offense's scoring."""
    if opp_off_ratio is None:
        return None
    if not goals_pg:
        return 2 - opp_off_ratio
    return 2 - opp_off_ratio * (1 + rest_shift(gaps, MIRROR.get(own_kind, own_kind)) / goals_pg)
