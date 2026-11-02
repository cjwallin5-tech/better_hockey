import unittest

import numpy as np

import lottery as lt


class Matrix(unittest.TestCase):
    def test_every_seed_gets_exactly_one_pick_and_every_pick_one_seed(self):
        m = lt.MATRIX
        self.assertTrue(np.allclose(m.sum(axis=1), 1.0))
        self.assertTrue(np.allclose(m.sum(axis=0), 1.0))

    def test_first_overall_odds_match_the_nhl_guide(self):
        first = lt.MATRIX[:, 0]
        published = [25.5, 13.5, 11.5, 9.5, 8.5, 7.5, 6.5, 6.0, 5.0, 3.5, 3.0, 0, 0, 0, 0, 0]
        self.assertTrue(np.allclose(first * 100, published, atol=1e-9))

    def test_the_worst_team_cannot_fall_out_of_the_top_three_and_the_best_cannot_rise_past_sixth(self):
        self.assertAlmostEqual(lt.MATRIX[0][:3].sum(), 1.0)             # seed 1: picks 1, 2 or 3 only (seed 16 at best sixth)
        self.assertAlmostEqual(lt.MATRIX[15][:5].sum(), 0.0)
        self.assertAlmostEqual(lt.MATRIX[11][0], 0.0)

    def test_nobody_moves_up_more_than_ten_spots_or_down_more_than_two(self):
        for seed in range(1, 17):
            for pick in range(1, 17):
                if lt.MATRIX[seed - 1][pick - 1] > 1e-12:
                    self.assertLessEqual(seed - pick, 10, (seed, pick))
                    self.assertLessEqual(pick - seed, 2, (seed, pick))

    def test_seed_one_is_never_worse_than_third_and_loses_the_first_pick_only_to_a_winner(self):
        self.assertAlmostEqual(lt.MATRIX[0][0], 0.255)
        self.assertGreater(lt.MATRIX[0][1], 0)


class Teams(unittest.TestCase):
    def test_a_sure_seed_one_gets_the_odds_of_seed_one(self):
        s = lt.summary([1.0] + [0.0] * 15)
        self.assertAlmostEqual(s["first_overall"], 0.255)
        self.assertAlmostEqual(s["worst_record"], 1.0)
        self.assertAlmostEqual(s["in_lottery"], 1.0)
        self.assertAlmostEqual(sum(s["picks"]), 1.0)

    def test_a_team_in_the_lottery_half_the_time_has_half_the_picks(self):
        s = lt.summary([0.5] + [0.0] * 15)
        self.assertAlmostEqual(sum(s["picks"]), 0.5)
        self.assertAlmostEqual(s["first_overall"], 0.1275)
        self.assertAlmostEqual(s["in_lottery"], 0.5)
        # the expected pick is given that it is in the lottery
        self.assertAlmostEqual(s["expected_pick"], sum((i + 1) * p for i, p in enumerate(lt.pick_distribution([1.0] + [0.0] * 15))))

    def test_a_team_never_in_the_lottery_has_nothing(self):
        s = lt.summary([0.0] * 16)
        self.assertEqual((s["first_overall"], s["in_lottery"]), (0.0, 0.0))
        self.assertIsNone(s["expected_pick"])

    def test_a_mixed_seed_is_the_weighted_sum_of_its_seeds(self):
        mixed = lt.pick_distribution([0.0, 0.5, 0.5] + [0.0] * 13)
        a, b = lt.pick_distribution([0.0, 1.0] + [0.0] * 14), lt.pick_distribution([0.0, 0.0, 1.0] + [0.0] * 13)
        self.assertTrue(np.allclose(mixed, 0.5 * np.array(a) + 0.5 * np.array(b)))


if __name__ == "__main__":
    unittest.main()
