import unittest

import matchups


def row(team, games, xgf, xga):
    return {"team": team, "games": games, "xgf": xgf, "xga": xga}


class ShrunkRate(unittest.TestCase):
    def test_pulled_toward_the_league_rate(self):
        self.assertAlmostEqual(matchups.shrunk_rate(40, 10, 3.0, 20), (40 + 20 * 3.0) / 30)

    def test_no_games_is_the_league_rate(self):
        self.assertAlmostEqual(matchups.shrunk_rate(0, 0, 2.9, 20), 2.9)

    def test_a_long_season_mostly_ignores_the_prior(self):
        self.assertAlmostEqual(matchups.shrunk_rate(300, 100, 2.0, 20), (300 + 40) / 120)


class TeamRatings(unittest.TestCase):
    def setUp(self):
        # league: 3 teams x 10 games, 90 xG for in total = 3.0 per team-game
        self.ratings, self.league = matchups.team_ratings([
            row("AAA", 10, 36.0, 24.0),   # scores 3.6 a game, allows 2.4
            row("BBB", 10, 24.0, 36.0),
            row("CCC", 10, 30.0, 30.0),
        ])

    def test_league_rate(self):
        self.assertAlmostEqual(self.league, 3.0)

    def test_average_team_is_exactly_one(self):
        self.assertAlmostEqual(self.ratings["CCC"]["off_ratio"], 1.0)
        self.assertAlmostEqual(self.ratings["CCC"]["def_ratio"], 1.0)

    def test_ratios_point_the_right_way_and_are_shrunk(self):
        a, b = self.ratings["AAA"], self.ratings["BBB"]
        self.assertGreater(a["off_ratio"], 1)
        self.assertLess(a["def_ratio"], 1)       # allows less than average: a tough opponent for skaters
        self.assertGreater(b["def_ratio"], 1)    # leaky: a soft one
        # raw 3.6 a game is 1.2x the league; with 10 of 30 games' weight on the data it is 1 + 0.2 / 3
        self.assertAlmostEqual(a["off_ratio"], 1 + 0.2 / 3)
        self.assertAlmostEqual(b["def_ratio"], 1 + 0.2 / 3)

    def test_more_games_means_less_shrinkage(self):
        short, _ = matchups.team_ratings([row("A", 10, 36.0, 30.0), row("B", 10, 24.0, 30.0)])
        long, _ = matchups.team_ratings([row("A", 80, 288.0, 240.0), row("B", 80, 192.0, 240.0)])
        self.assertGreater(long["A"]["off_ratio"], short["A"]["off_ratio"])

    def test_nothing_to_rate(self):
        self.assertEqual(matchups.team_ratings([]), ({}, None))
        self.assertEqual(matchups.team_ratings([row("A", 0, 0, 0)]), ({}, None))


class Goalies(unittest.TestCase):
    def test_estimate_is_pulled_hard_toward_zero(self):
        # +20 goals over 1,500 shots is +1.33 per 100 raw; the prior leaves about a seventh of that
        est = matchups.goalie_estimate(20, 1500)
        self.assertAlmostEqual(est, 20 / 9500 * 100)
        self.assertLess(est, 0.25)
        self.assertAlmostEqual(matchups.goalie_estimate(-20, 1500), -est)
        self.assertEqual(matchups.goalie_estimate(0, 0), 0)

    def test_multiplier(self):
        # +1 goal saved per 100 shots over 30 shots a game is 0.3 goals a game, a tenth of 3 goals
        self.assertAlmostEqual(matchups.goalie_multiplier(1.0, 30, 3.0), 0.9)
        self.assertAlmostEqual(matchups.goalie_multiplier(-1.0, 30, 3.0), 1.1)
        self.assertEqual(matchups.goalie_multiplier(0, 30, 3.0), 1.0)
        self.assertEqual(matchups.goalie_multiplier(5, 30, 0), 1.0)

    def test_expected_multiplier_is_weighted_by_starts(self):
        self.assertAlmostEqual(matchups.expected_goalie_multiplier([(8, 0.98), (2, 1.02)]), 0.988)
        self.assertEqual(matchups.expected_goalie_multiplier([]), 1.0)
        self.assertEqual(matchups.expected_goalie_multiplier([(0, 0.9)]), 1.0)


class Games(unittest.TestCase):
    def test_skater_ratio_combines_defense_and_goalie(self):
        self.assertAlmostEqual(matchups.skater_ratio(1.06, 0.98), 1.06 * 0.98)

    def test_labels(self):
        self.assertEqual(matchups.label(1.05), "soft")
        self.assertEqual(matchups.label(1.04), "soft")
        self.assertEqual(matchups.label(1.0), "neutral")
        self.assertEqual(matchups.label(0.97), "neutral")
        self.assertEqual(matchups.label(0.96), "tough")
        self.assertIsNone(matchups.label(None))

    def test_schedule_summary(self):
        s = matchups.schedule_summary([1.1, 0.9, 1.05, None])
        self.assertEqual(s["games"], 3)
        self.assertAlmostEqual(s["avg"], 3.05 / 3)
        self.assertAlmostEqual(s["index"], 0.05)

    def test_empty_schedule(self):
        self.assertEqual(matchups.schedule_summary([]), {"games": 0, "avg": None, "index": 0.0})
        self.assertEqual(matchups.schedule_summary([None])["games"], 0)

    def test_more_games_at_the_same_difficulty_give_a_bigger_index(self):
        self.assertGreater(matchups.schedule_summary([1.05] * 4)["index"], matchups.schedule_summary([1.05] * 3)["index"])


class RestInMatchups(unittest.TestCase):
    GAPS = {"tired": -0.3, "edge": 0.3}

    def test_a_tired_teams_skaters_get_a_tougher_game_and_a_rested_teams_a_softer_one(self):
        self.assertAlmostEqual(matchups.skater_game_ratio(1.0, "tired", self.GAPS, 3.0), 0.9)
        self.assertAlmostEqual(matchups.skater_game_ratio(1.0, "edge", self.GAPS, 3.0), 1.1)

    def test_normal_and_both_tired_games_are_left_alone(self):
        for kind in ("normal", "both", None):
            self.assertEqual(matchups.skater_game_ratio(1.05, kind, self.GAPS, 3.0), 1.05)
            self.assertEqual(matchups.goalie_game_ratio(0.95, kind, self.GAPS, 3.0), 2 - 0.95)

    def test_a_goalie_facing_a_tired_offense_gets_an_easier_game(self):
        # our goalie is rested (edge), so the opponent is the tired side: its offense is cut by 0.3 of 3.0 goals
        self.assertAlmostEqual(matchups.goalie_game_ratio(1.0, "edge", self.GAPS, 3.0), 2 - 0.9)
        # our goalie is tired, so the opponent's offense is up
        self.assertAlmostEqual(matchups.goalie_game_ratio(1.0, "tired", self.GAPS, 3.0), 2 - 1.1)

    def test_missing_inputs_do_not_break_the_ratio(self):
        self.assertIsNone(matchups.skater_game_ratio(None, "tired", self.GAPS, 3.0))
        self.assertEqual(matchups.skater_game_ratio(1.02, "tired", None, 3.0), 1.02)
        self.assertEqual(matchups.skater_game_ratio(1.02, "tired", self.GAPS, None), 1.02)
        self.assertIsNone(matchups.goalie_game_ratio(None, "tired", self.GAPS, 3.0))


if __name__ == "__main__":
    unittest.main()
