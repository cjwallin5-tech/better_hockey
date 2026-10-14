import math
import unittest
from datetime import date

import trajectory as tj


class Age(unittest.TestCase):
    def test_age_on_february_first(self):
        self.assertEqual(tj.age_in(20152016, date(1997, 1, 13)), 19)
        self.assertEqual(tj.age_in(20152016, date(1997, 2, 1)), 19)   # birthday on the cutoff counts
        self.assertEqual(tj.age_in(20152016, date(1997, 2, 2)), 18)

    def test_role(self):
        self.assertEqual([tj.role(p) for p in "CLRD"], ["F", "F", "F", "D"])


class Baselines(unittest.TestCase):
    def test_league_rate_ignores_short_stints_and_splits_by_role(self):
        rows = [(1, "F", 80, 80), (1, "F", 60, 30), (1, "F", 10, 100), (1, "D", 80, 40)]
        base = tj.baselines(rows)
        self.assertAlmostEqual(base[(1, "F")], 110 / 140)   # the 10-game player is left out
        self.assertAlmostEqual(base[(1, "D")], 0.5)


class Curve(unittest.TestCase):
    def test_relative_scoring_by_age_for_qualifying_seasons_only(self):
        base = {(20152016, "F"): 1.0}
        out = tj.curve([(20152016, 80, 96), (20162017, 10, 50)], date(1997, 1, 13), "F", base)
        self.assertEqual(list(out), [19])
        self.assertEqual(out[19][0], 80)
        self.assertAlmostEqual(out[19][1], 1.2)

    def test_season_without_a_league_rate_is_skipped(self):
        self.assertEqual(tj.curve([(20152016, 80, 96)], date(1997, 1, 13), "F", {}), {})


class Distance(unittest.TestCase):
    def test_identical_curves_are_zero_apart(self):
        c = {20: (82, 1.0), 21: (82, 1.2)}
        self.assertEqual(tj.distance(c, dict(c)), (0.0, 2))

    def test_known_gap(self):
        target = {20: (80, 1.0), 21: (80, 1.2)}
        cand = {20: (80, 1.1), 21: (70, 1.1), 22: (80, 1.0)}
        rms, n = tj.distance(target, cand)
        self.assertAlmostEqual(rms, 0.1)     # both overlapping seasons are off by 0.1
        self.assertEqual(n, 2)

    def test_too_little_overlap_means_no_answer(self):
        target = {a: (82, 1.0) for a in range(20, 25)}      # five seasons: need ceil(0.6 * 5) = 3 in common
        cand = {20: (82, 1.0), 21: (82, 1.0)}
        self.assertIsNone(tj.distance(target, cand))

    def test_short_seasons_count_for_less(self):
        full = tj.distance({20: (82, 1.0), 21: (82, 1.0)}, {20: (82, 1.0), 21: (82, 2.0)})[0]
        short = tj.distance({20: (82, 1.0), 21: (82, 1.0)}, {20: (82, 1.0), 21: (20, 2.0)})[0]
        self.assertLess(short, full)

    def test_similarity_falls_as_curves_diverge(self):
        self.assertEqual(tj.similarity(0), 100)
        self.assertEqual(tj.similarity(0.25), 50)
        self.assertGreater(tj.similarity(0.1), tj.similarity(0.3))


class Projection(unittest.TestCase):
    def test_needs_a_few_matches(self):
        self.assertIsNone(tj.projection([10, 20]))

    def test_median_and_middle_half(self):
        out = tj.projection([10, 20, 30, 40])
        self.assertEqual((out["median"], out["low"], out["high"], out["matches"]), (25, 18, 32, 4))


if __name__ == "__main__":
    unittest.main()
