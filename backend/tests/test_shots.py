import unittest

import shots


def attempt(team, t, kind="shot", period=1):
    return {"team_id": team, "period": period, "time_sec": t, "kind": kind}


class FollowFlagsTest(unittest.TestCase):
    def flags(self, *attempts):
        return shots.follow_flags(list(attempts))

    def test_first_attempt_is_neither(self):
        self.assertEqual(self.flags(attempt("A", 10)), [(False, False)])

    def test_quick_follow_within_a_second_is_both(self):
        self.assertEqual(self.flags(attempt("A", 10), attempt("A", 11))[1], (True, True))
        self.assertEqual(self.flags(attempt("A", 10), attempt("A", 10))[1], (True, True))

    def test_two_or_three_seconds_later_is_a_rebound_only(self):
        self.assertEqual(self.flags(attempt("A", 10), attempt("A", 12))[1], (True, False))
        self.assertEqual(self.flags(attempt("A", 10), attempt("A", 13))[1], (True, False))

    def test_later_than_three_seconds_is_neither(self):
        self.assertEqual(self.flags(attempt("A", 10), attempt("A", 14))[1], (False, False))

    def test_only_a_shot_on_goal_makes_a_rebound(self):
        for kind in ("miss", "block", "goal"):
            self.assertEqual(self.flags(attempt("A", 10, kind), attempt("A", 12))[1], (False, False), kind)

    def test_the_other_team_and_other_periods_do_not_count(self):
        self.assertEqual(self.flags(attempt("A", 10), attempt("B", 11))[1], (False, False))
        self.assertEqual(self.flags(attempt("A", 1195), attempt("A", 2, period=2))[1], (False, False))

    def test_the_other_teams_attempt_in_between_does_not_hide_the_save(self):
        self.assertEqual(self.flags(attempt("A", 10), attempt("B", 11), attempt("A", 12))[2], (True, False))


class FeaturesTest(unittest.TestCase):
    base = {"distance": 8.0, "angle": 10.0, "strength": "ev", "shot_type": "wrist", "kind": "shot", "empty_net": False, "x": 80}

    def feature(self, name, **kw):
        s = {**self.base, "rebound": False, "quick_follow": False, **kw}
        return shots.features(s)[shots.FEATURE_NAMES.index(name)]

    def test_a_quick_follow_up_is_not_also_counted_as_a_rebound(self):
        self.assertEqual(self.feature("rebound", rebound=True, quick_follow=True), 0.0)
        self.assertEqual(self.feature("quick_follow", rebound=True, quick_follow=True), 1.0)
        self.assertEqual(self.feature("rebound", rebound=True), 1.0)

    def test_one_feature_per_name(self):
        self.assertEqual(len(shots.features({**self.base, "rebound": False})), len(shots.FEATURE_NAMES))

    def test_a_rebound_is_worth_more_and_a_quick_follow_up_less_than_a_first_shot(self):
        first = shots.xg({**self.base, "rebound": False, "quick_follow": False})
        rebound = shots.xg({**self.base, "rebound": True, "quick_follow": False})
        quick = shots.xg({**self.base, "rebound": True, "quick_follow": True})
        self.assertGreater(rebound, first)
        self.assertLess(quick, first)


if __name__ == "__main__":
    unittest.main()
