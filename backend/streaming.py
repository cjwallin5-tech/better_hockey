"""What a goalie start is worth in a given game, for the streaming finder.

The starter model (probable_goalies.py) says how likely a goalie is to start each game. This module says what a start is
worth: a structural model built from the two teams' ratings (matchups.py), not from the goalie's own record, because
goaltending results barely repeat from year to year (a goalie's past goals saved above expected predicts the next season only
about 2% better than assuming an average goalie) while team strength does persist.

For a game between `own` and `opp` (each with an offense ratio and a defense ratio relative to the league, where above 1
scores or allows more than average):
  - expected goals for  = league goals per team-game x own offense x opponent defense
  - expected goals against = league goals x opponent offense x own defense x the goalie's small effect
  - win chance from the standard hockey rule that win odds go with the square of the goals ratio (Pythagorean, exponent 2)
  - shots against: league shots per team-game scaled by the square root of the opponent-offense x own-defense ratio (the
    ratio mixes shot volume and shot quality; half of it is assumed to be volume), and saves = shots - goals against
  - shutout chance = the Poisson chance of no goals, exp(-goals against)
  - the rest of the non-wins are split into regulation and overtime losses at the league's overtime-loss share

What it does not know: home-ice advantage, rest, injuries, the actual starter (that is the start probability's job), or that
a goalie who starts a lot of games may be better than his record says. The 50/50 volume-quality split and the Pythagorean exponent are
standard assumptions, not fitted here. Treat the output as a ranking aid.
"""
import math

import matchups

PYTHAG_EXPONENT = 2.0


def expected_line(own, opp, league_goals, league_shots, goalie_mult=1.0, otl_share=0.23):
    """Expected stat line for one start: win/loss/otl chances (sum to 1), saves, shots, goals against and for, shutout chance.

    own, opp: dicts with off_ratio and def_ratio. goalie_mult below 1 stops more than average (matchups.goalie_multiplier).
    """
    gf = league_goals * own["off_ratio"] * opp["def_ratio"]
    pressure = opp["off_ratio"] * own["def_ratio"]            # how much the opponent's attack is up against this defense
    ga = league_goals * pressure * goalie_mult
    p_win = gf ** PYTHAG_EXPONENT / (gf ** PYTHAG_EXPONENT + ga ** PYTHAG_EXPONENT)
    shots = league_shots * math.sqrt(pressure)
    non_win = 1 - p_win
    return {"win": p_win, "loss": non_win * (1 - otl_share), "otl": non_win * otl_share,
            "shots": shots, "saves": max(0.0, shots - ga), "ga": ga, "gf": gf, "shutout": math.exp(-ga)}


def goalie_game(own, opp, goalie_estimate, league, otl_share):
    """expected_line for one goalie's start: league = {goals_pg, shots_pg}; goalie_estimate = goals saved above expected
    per 100 shots from matchups.goalie_estimate (0 for an unknown goalie)."""
    mult = matchups.goalie_multiplier(goalie_estimate, league["shots_pg"], league["goals_pg"])
    return expected_line(own, opp, league["goals_pg"], league["shots_pg"], mult, otl_share)
