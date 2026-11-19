import unittest

import srs


class RatingsTest(unittest.TestCase):
    def test_two_teams_split_the_margin(self):
        # A beats B by two goals twice: A is +2 a game, B is -2, and each other's strength of schedule is the other's rating
        out = srs.ratings([("A", "B", 3, 1), ("B", "A", 1, 3)])
        self.assertAlmostEqual(out["A"]["srs"], 1.0)
        self.assertAlmostEqual(out["B"]["srs"], -1.0)
        self.assertAlmostEqual(out["A"]["margin"], 2.0)
        self.assertAlmostEqual(out["A"]["sos"], -1.0)

    def test_ratings_average_to_zero(self):
        games = [("A", "B", 4, 1), ("B", "C", 2, 1), ("C", "A", 3, 2), ("A", "C", 1, 0), ("B", "A", 2, 2)]
        out = srs.ratings(games)
        self.assertAlmostEqual(sum(t["srs"] for t in out.values()), 0.0)

    def test_the_same_margin_against_a_better_team_rates_higher(self):
        # A and C each win by one goal over a different opponent; B is strong (beats D by 5), so A, who beat B, should rate above C who beat D
        games = [("B", "D", 6, 1), ("A", "B", 2, 1), ("C", "D", 2, 1)]
        out = srs.ratings(games)
        self.assertGreater(out["A"]["srs"], out["C"]["srs"])

    def test_unfinished_games_are_ignored(self):
        self.assertEqual(srs.ratings([("A", "B", None, None)]), {})

    def test_srs_is_margin_plus_strength_of_schedule(self):
        out = srs.ratings([("A", "B", 3, 1), ("B", "C", 2, 0), ("C", "A", 1, 1)])
        for t in out.values():
            self.assertAlmostEqual(t["srs"], t["margin"] + t["sos"])
