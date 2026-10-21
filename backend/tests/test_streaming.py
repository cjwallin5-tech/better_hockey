import math
import unittest

import streaming

AVG = {"off_ratio": 1.0, "def_ratio": 1.0}
LEAGUE = {"goals_pg": 3.0, "shots_pg": 27.0}


def line(own=AVG, opp=AVG, mult=1.0, otl=0.23):
    return streaming.expected_line(own, opp, LEAGUE["goals_pg"], LEAGUE["shots_pg"], mult, otl)


class ExpectedLine(unittest.TestCase):
    def test_two_average_teams(self):
        x = line()
        self.assertAlmostEqual(x["win"], 0.5)
        self.assertAlmostEqual(x["ga"], 3.0)
        self.assertAlmostEqual(x["gf"], 3.0)
        self.assertAlmostEqual(x["shots"], 27.0)
        self.assertAlmostEqual(x["saves"], 24.0)
        self.assertAlmostEqual(x["shutout"], math.exp(-3))

    def test_the_outcomes_add_to_one(self):
        x = line({"off_ratio": 1.1, "def_ratio": 0.95}, {"off_ratio": 0.92, "def_ratio": 1.06})
        self.assertAlmostEqual(x["win"] + x["loss"] + x["otl"], 1.0)

    def test_overtime_losses_take_their_share_of_non_wins(self):
        x = line(otl=0.25)
        self.assertAlmostEqual(x["otl"], 0.5 * 0.25)
        self.assertAlmostEqual(x["loss"], 0.5 * 0.75)

    def test_a_stronger_opposing_offense_means_more_goals_and_fewer_wins(self):
        easy, hard = line(opp={"off_ratio": 0.9, "def_ratio": 1.0}), line(opp={"off_ratio": 1.1, "def_ratio": 1.0})
        self.assertGreater(hard["ga"], easy["ga"])
        self.assertLess(hard["win"], easy["win"])
        self.assertGreater(hard["shots"], easy["shots"])
        self.assertLess(hard["shutout"], easy["shutout"])

    def test_a_leakier_opposing_defense_means_a_better_chance_to_win(self):
        self.assertGreater(line(opp={"off_ratio": 1.0, "def_ratio": 1.1})["win"], 0.5)

    def test_a_better_own_team_helps_on_both_ends(self):
        good = line(own={"off_ratio": 1.1, "def_ratio": 0.9})
        self.assertGreater(good["win"], 0.5)
        self.assertLess(good["ga"], 3.0)

    def test_pythagorean_odds(self):
        # 3.3 goals for against 3.0 against: odds (3.3 / 3.0)^2
        x = line(own={"off_ratio": 1.1, "def_ratio": 1.0})
        self.assertAlmostEqual(x["win"] / (1 - x["win"]), 1.1 ** 2)

    def test_half_of_the_ratio_is_shot_volume(self):
        x = line(opp={"off_ratio": 1.21, "def_ratio": 1.0})
        self.assertAlmostEqual(x["shots"], 27.0 * 1.1)         # sqrt(1.21)
        self.assertAlmostEqual(x["ga"], 3.0 * 1.21)

    def test_a_goalie_who_stops_more_lowers_goals_against_and_helps_wins(self):
        base, better = line(), line(mult=0.95)
        self.assertAlmostEqual(better["ga"], 3.0 * 0.95)
        self.assertGreater(better["win"], base["win"])
        self.assertGreater(better["shutout"], base["shutout"])

    def test_saves_cannot_go_negative(self):
        self.assertEqual(streaming.expected_line(AVG, AVG, 10.0, 5.0)["saves"], 0.0)


class GoalieGame(unittest.TestCase):
    def test_an_unknown_goalie_is_an_average_one(self):
        a = streaming.goalie_game(AVG, AVG, 0.0, LEAGUE, 0.23)
        b = line()
        self.assertAlmostEqual(a["ga"], b["ga"])
        self.assertAlmostEqual(a["win"], b["win"])

    def test_estimate_shifts_goals_against_the_right_way(self):
        good = streaming.goalie_game(AVG, AVG, 1.0, LEAGUE, 0.23)    # +1 goal saved per 100 shots
        poor = streaming.goalie_game(AVG, AVG, -1.0, LEAGUE, 0.23)
        self.assertLess(good["ga"], 3.0)
        self.assertGreater(poor["ga"], 3.0)
        # +1 per 100 shots over 27 shots is 0.27 goals, 9% of 3 goals a game
        self.assertAlmostEqual(good["ga"], 3.0 * (1 - 0.27 / 3.0))


if __name__ == "__main__":
    unittest.main()
