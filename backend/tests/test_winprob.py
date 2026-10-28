import unittest

import api
import winprob as wp


class Probability(unittest.TestCase):
    def test_an_even_game_at_the_start_is_near_a_coin_flip_with_a_home_edge(self):
        p = wp.win_prob(0, 0, 0.0)
        self.assertTrue(0.5 < p < 0.56)

    def test_a_lead_is_worth_more_with_less_time_left(self):
        early, late = wp.win_prob(1, 600, 0.0), wp.win_prob(1, 3400, 0.0)
        self.assertGreater(late, early)
        self.assertGreater(wp.win_prob(2, 3000, 0.0), wp.win_prob(1, 3000, 0.0))

    def test_a_trailing_home_team_is_the_mirror(self):
        self.assertLess(wp.win_prob(-1, 3000, 0.0), 0.5)
        self.assertLess(wp.win_prob(-2, 3000, 0.0), wp.win_prob(-1, 3000, 0.0))

    def test_the_better_team_is_favored_and_the_edge_fades_as_the_game_goes(self):
        self.assertGreater(wp.win_prob(0, 0, 0.4), wp.win_prob(0, 0, 0.0))
        gap = lambda t: wp.win_prob(0, t, 0.4) - wp.win_prob(0, t, 0.0)
        self.assertGreater(gap(0), gap(3000))

    def test_decided_games_and_overtime(self):
        self.assertEqual(wp.win_prob(1, 3600, 0.0), 1.0)
        self.assertEqual(wp.win_prob(-1, 3700, 0.0), 0.0)
        self.assertTrue(0.45 < wp.win_prob(0, 3600, 0.0) < 0.6)           # tied after regulation: close to a coin flip
        self.assertGreater(wp.win_prob(0, 3600, 0.5), wp.win_prob(0, 3600, -0.5))

    def test_probabilities_stay_between_zero_and_one(self):
        for d in range(-5, 6):
            for t in range(0, 3601, 300):
                self.assertTrue(0.0 <= wp.win_prob(d, t, 0.3) <= 1.0)


class Ratings(unittest.TestCase):
    def test_goal_difference_per_game_pulled_toward_zero(self):
        r = wp.ratings([("A", "B", 5, 1), ("B", "A", 1, 2)])
        self.assertAlmostEqual(r["A"], 5 / (2 + wp.PRIOR_GAMES))
        self.assertAlmostEqual(r["B"], -5 / (2 + wp.PRIOR_GAMES))
        self.assertEqual(wp.ratings([]), {})


class Timeline(unittest.TestCase):
    def test_it_steps_at_each_goal_and_ends_at_the_result(self):
        pts, events = wp.timeline([(600, 1), (1500, 0), (3000, 1)], 0.0, 3600)
        self.assertEqual([e["diff"] for e in events], [1, 0, 1])
        self.assertAlmostEqual(pts[0][1], wp.win_prob(0, 0, 0.0))
        self.assertEqual(pts[-1], [3600, 1.0])
        goal = [(t, p) for t, p in pts if t == 600]
        self.assertGreater(goal[1][1], goal[0][1])                         # a home goal lifts the home chance in one step

    def test_an_overtime_goal_ends_it(self):
        pts, events = wp.timeline([(1000, 0), (2000, 1), (3700, 1)], 0.0, 3700, True)
        self.assertEqual(events[-1]["diff"], 1)
        self.assertEqual(pts[-1][1], 1.0)
        self.assertTrue(any(t == 3600 and 0.45 < p < 0.6 for t, p in pts))   # tied at the end of regulation

    def test_a_shootout_closes_on_the_result(self):
        pts, _ = wp.timeline([(1000, 0), (2000, 1)], 0.0, 3900, False)
        self.assertEqual(pts[-1], [3900, 0.0])

    def test_clock_labels(self):
        self.assertEqual(wp.clock(1), "P1 0:01")
        self.assertEqual(wp.clock(1200), "P1 20:00")
        self.assertEqual(wp.clock(3700), "OT 1:40")


class Story(unittest.TestCase):
    def tell(self, goals, hs, as_, gap=0.0, end="REG", xg=None):
        ended = 3600 if end == "REG" else 3700 if end == "OT" else 3900
        pts, ev = wp.timeline(goals, gap, ended, hs > as_)
        return wp.story("HOM", "AWY", gap, ev, hs, as_, end, pts, xg)

    def test_a_comeback_is_called_out(self):
        text = " ".join(self.tell([(300, 0), (600, 0), (900, 0), (2400, 1), (2800, 1), (3300, 1), (3500, 1)], 4, 3))
        self.assertIn("HOM won 4-3", text)
        self.assertIn("before coming back", text)
        self.assertIn("biggest swing", text)

    def test_a_blowout_says_when_it_was_settled(self):
        text = " ".join(self.tell([(300, 1), (900, 1), (1500, 1), (2000, 1)], 4, 0))
        self.assertIn("effectively settled", text)

    def test_overtime_and_shootout_are_named(self):
        self.assertIn("in overtime", " ".join(self.tell([(1000, 0), (2000, 1), (3650, 1)], 2, 1, end="OT")))
        self.assertIn("in a shootout", " ".join(self.tell([(1000, 0), (2000, 1)], 2, 1, end="SO")))

    def test_the_favorite_and_a_toss_up(self):
        self.assertIn("close to even", self.tell([(300, 1)], 1, 0)[0])
        self.assertIn("HOM were the favorites", self.tell([(300, 1)], 1, 0, gap=0.8)[0])

    def test_the_team_with_the_chances_that_lost_is_noted(self):
        text = " ".join(self.tell([(300, 0), (3000, 1), (3400, 0)], 1, 2, xg={"home": 3.2, "away": 1.1}))
        self.assertIn("HOM had the better of the chances", text)
        self.assertIn("but AWY won", text)


class Live(unittest.TestCase):
    def test_elapsed_time_from_the_period_and_clock(self):
        self.assertEqual(api._live_elapsed({"period": 1, "time_remaining": "20:00"}), 0)
        self.assertEqual(api._live_elapsed({"period": 2, "time_remaining": "05:30"}), 1200 + 870)
        self.assertEqual(api._live_elapsed({"period": 3, "time_remaining": "00:10"}), 3590)
        self.assertEqual(api._live_elapsed({"period": 4, "time_remaining": "03:00"}), 3600)
        self.assertEqual(api._live_elapsed({"period": 2, "time_remaining": None}), 1200)


if __name__ == "__main__":
    unittest.main()
