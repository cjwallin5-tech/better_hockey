import math
import unittest

import luck


def skater(**kw):
    base = {"attempts": 40, "shots_on_goal": 30, "goals": 10, "model_goals": 10, "ixg": 6.0, "variance": 4.0,
            "games_played": 10, "gf": 12, "ga": 6, "xgf": 9.0, "xga": 8.0,
            "points": 15, "season_goals": 10, "pp_goals": 3, "ev_points": 11, "ev_goals_for": 20,
            "ev_model_goals": 6, "ev_ixg": 4.0}
    return {**base, **kw}


class ZScore(unittest.TestCase):
    def test_gap_in_standard_deviations(self):
        self.assertAlmostEqual(luck.z_score(10, 6, 4), 2.0)
        self.assertAlmostEqual(luck.z_score(3, 6, 9), -1.0)

    def test_no_variance_means_no_score(self):
        self.assertIsNone(luck.z_score(1, 0, 0))
        self.assertIsNone(luck.z_score(1, 0, None))


class Flag(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(luck.flag(1.5), "hot")
        self.assertEqual(luck.flag(-1.5), "cold")
        self.assertEqual(luck.flag(1.49), "steady")
        self.assertEqual(luck.flag(-0.2), "steady")
        self.assertIsNone(luck.flag(None))


class Pace(unittest.TestCase):
    def test_scales_to_a_full_season(self):
        self.assertAlmostEqual(luck.pace(5, 10, 82), 41.0)

    def test_no_games(self):
        self.assertIsNone(luck.pace(5, 0, 82))
        self.assertIsNone(luck.pace(5, None, 82))


class SkaterLine(unittest.TestCase):
    def test_hot_finisher(self):
        out = luck.skater_line(skater(), 82)
        self.assertAlmostEqual(out["diff"], 4.0)
        self.assertAlmostEqual(out["z"], 2.0)
        self.assertEqual(out["flag"], "hot")
        self.assertAlmostEqual(out["sh_pct"], 10 / 30)
        self.assertAlmostEqual(out["xsh_pct"], 6 / 30)
        self.assertAlmostEqual(out["goals_pace"], 82.0)
        self.assertAlmostEqual(out["xg_pace"], 49.2)

    def test_cold_finisher(self):
        out = luck.skater_line(skater(goals=2, model_goals=2, variance=4.0), 82)
        self.assertAlmostEqual(out["z"], -2.0)
        self.assertEqual(out["flag"], "cold")

    def test_onice_luck_is_goal_difference_minus_expected_difference(self):
        # (12 - 6) - (9 - 8) = 5
        self.assertAlmostEqual(luck.skater_line(skater(), 82)["onice_diff"], 5.0)

    def test_missing_onice_data_is_none_not_zero(self):
        self.assertIsNone(luck.skater_line(skater(xgf=None), 82)["onice_diff"])

    def test_no_shots_on_goal(self):
        out = luck.skater_line(skater(shots_on_goal=0, goals=0, model_goals=0, ixg=0.0, variance=0.0), 82)
        self.assertIsNone(out["sh_pct"])
        self.assertIsNone(out["z"])
        self.assertIsNone(out["flag"])


class GoalieLine(unittest.TestCase):
    def test_goalie_saving_more_than_expected_is_hot(self):
        out = luck.goalie_line({"faced": 100, "goals": 5, "model_goals": 5, "xga": 9.0, "variance": 4.0})
        self.assertAlmostEqual(out["gsax"], 4.0)
        self.assertAlmostEqual(out["z"], 2.0)
        self.assertEqual(out["flag"], "hot")
        self.assertAlmostEqual(out["sv_pct"], 0.95)
        self.assertAlmostEqual(out["xsv_pct"], 0.91)
        self.assertAlmostEqual(out["gsax_per_100"], 4.0)

    def test_goalie_letting_in_more_than_expected_is_cold(self):
        out = luck.goalie_line({"faced": 100, "goals": 13, "model_goals": 13, "xga": 9.0, "variance": 4.0})
        self.assertAlmostEqual(out["z"], -2.0)
        self.assertEqual(out["flag"], "cold")

    def test_nothing_faced(self):
        out = luck.goalie_line({"faced": 0, "goals": 0, "model_goals": 0, "xga": 0.0, "variance": 0.0})
        self.assertIsNone(out["sv_pct"])
        self.assertIsNone(out["z"])


class AssistRate(unittest.TestCase):
    def test_no_sample_means_the_league_rate(self):
        self.assertAlmostEqual(luck.assist_rate(0, 0, 0.5), 0.5)

    def test_a_big_sample_dominates_the_baseline(self):
        self.assertAlmostEqual(luck.assist_rate(100, 100, 0.2), (100 + 2) / 110)


class PointsLuck(unittest.TestCase):
    def test_goal_luck_plus_assist_luck(self):
        # own ev goals 10-3=7, ev assists 11-7=4, teammate goals 20-7=13, rate (4+5)/(13+10)=9/23
        # teammate gap (12-6) - (9-4) = 1, so assist luck 9/23 and points luck 4 + 9/23
        out = luck.skater_line(skater(), 82, 0.5)
        k = 9 / 23
        self.assertAlmostEqual(out["assist_rate"], k)
        self.assertAlmostEqual(out["assist_luck"], k)
        self.assertAlmostEqual(out["points_diff"], 4 + k)
        self.assertAlmostEqual(out["xpoints"], 15 - 4 - k)
        self.assertAlmostEqual(out["points_z"], (4 + k) / math.sqrt(4 + k * k * 5))
        self.assertEqual(out["points_flag"], "hot")

    def test_unlucky_teammates_make_a_player_colder(self):
        out = luck.skater_line(skater(gf=3), 82, 0.5)  # teammate gap (3-6) - (9-4) = -8
        self.assertLess(out["assist_luck"], 0)
        self.assertLess(out["points_diff"], out["diff"])

    def test_without_a_baseline_there_is_no_points_luck(self):
        out = luck.skater_line(skater(), 82)
        self.assertIsNone(out["points_z"])
        self.assertIsNone(out["points_diff"])
        self.assertEqual(out["points"], 15)

    def test_missing_nhl_or_onice_figures_give_none_not_zero(self):
        for missing in ("ev_goals_for", "ev_points", "gf", "xgf"):
            out = luck.skater_line(skater(**{missing: None}), 82, 0.5)
            self.assertIsNone(out["points_diff"], missing)

    def test_negative_counts_are_clamped(self):
        # more power-play goals than total goals would give negative even-strength goals
        out = luck.skater_line(skater(season_goals=1, pp_goals=3, ev_points=0), 82, 0.5)
        self.assertGreaterEqual(out["assist_rate"], 0)


PRIOR = {"model_goals": 60, "ixg": 40.0, "variance": 30.0, "seasons": 3}


class FinishingSkill(unittest.TestCase):
    def test_edge_is_goals_above_xg_shrunk_by_the_prior(self):
        self.assertAlmostEqual(luck.finishing_skill(PRIOR), 20 / (40 + luck.PRIOR_XG))

    def test_a_poor_finisher_has_a_negative_edge(self):
        self.assertLess(luck.finishing_skill({**PRIOR, "model_goals": 30}), 0)

    def test_no_history_is_no_edge(self):
        self.assertEqual(luck.finishing_skill(None), 0.0)
        self.assertEqual(luck.finishing_skill({**PRIOR, "seasons": 0}), 0.0)

    def test_a_short_history_claims_little(self):
        small = {"model_goals": 4, "ixg": 1.0, "variance": 1.0, "seasons": 1}  # +3 goals over one hot month
        self.assertLess(luck.finishing_skill(small), 0.1)


class AdjustedForHistory(unittest.TestCase):
    def test_a_proven_finisher_is_judged_against_their_own_norm(self):
        out = luck.skater_line(skater(), 82, 0.5, PRIOR)
        skill = 20 / 70
        # plain: 10 goals vs 6 xG is +4 (z 2.0, hot); against 6 * (1 + skill) it is much less surprising
        self.assertAlmostEqual(out["z"], 2.0)
        self.assertAlmostEqual(out["diff_adj"], 10 - 6 * (1 + skill))
        self.assertAlmostEqual(out["z_adj"], (10 - 6 * (1 + skill)) / 2)
        self.assertEqual(out["flag"], "hot")
        self.assertEqual(out["flag_adj"], "steady")
        self.assertTrue(out["has_history"])
        self.assertEqual(out["prior_seasons"], 3)
        self.assertAlmostEqual(out["prior_diff"], 20.0)
        self.assertAlmostEqual(out["prior_z"], 20 / math.sqrt(30))

    def test_points_luck_uses_the_adjusted_goal_gap_too(self):
        out = luck.skater_line(skater(), 82, 0.5, PRIOR)
        k = 9 / 23
        self.assertAlmostEqual(out["points_diff_adj"], 10 - 6 * (1 + 20 / 70) + k)
        self.assertAlmostEqual(out["points_z_adj"], out["points_diff_adj"] / math.sqrt(4 + k * k * 5))
        self.assertLess(out["points_diff_adj"], out["points_diff"])

    def test_without_history_the_adjusted_figures_match_the_plain_ones(self):
        out = luck.skater_line(skater(), 82, 0.5)
        self.assertFalse(out["has_history"])
        self.assertEqual(out["prior_seasons"], 0)
        self.assertIsNone(out["prior_z"])
        self.assertAlmostEqual(out["z_adj"], out["z"])
        self.assertAlmostEqual(out["diff_adj"], out["diff"])
        self.assertAlmostEqual(out["points_z_adj"], out["points_z"])
        self.assertEqual(out["flag_adj"], out["flag"])

    def test_a_chronic_underperformer_is_less_cold_than_average_suggests(self):
        poor = {"model_goals": 30, "ixg": 40.0, "variance": 30.0, "seasons": 3}
        out = luck.skater_line(skater(goals=2, model_goals=2), 82, 0.5, poor)
        self.assertGreater(out["z_adj"], out["z"])


class Pearson(unittest.TestCase):
    def test_perfect_and_inverse(self):
        self.assertAlmostEqual(luck.pearson([1, 2, 3, 4], [2, 4, 6, 8]), 1.0)
        self.assertAlmostEqual(luck.pearson([1, 2, 3, 4], [8, 6, 4, 2]), -1.0)

    def test_too_few_pairs_or_no_spread(self):
        self.assertIsNone(luck.pearson([1, 2], [1, 2]))
        self.assertIsNone(luck.pearson([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(luck.pearson([1, 2, 3], [1, 2]))


if __name__ == "__main__":
    unittest.main()
