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


def goal(event_id, order, scorer, a1=None, a2=None, period_type="REG"):
    details = {"scoringPlayerId": scorer}
    if a1:
        details["assist1PlayerId"] = a1
    if a2:
        details["assist2PlayerId"] = a2
    return {"eventId": event_id, "sortOrder": order, "typeDescKey": "goal", "periodDescriptor": {"number": 1, "periodType": period_type}, "details": details}


class GoalAssistsTest(unittest.TestCase):
    def test_primary_and_secondary_assisters_in_game_order(self):
        pbp = {"plays": [goal(7, 20, 1, 2, 3), goal(5, 10, 4, 5)]}
        self.assertEqual(shots.extract_goal_assists(pbp), [(5, 4, 5, None), (7, 1, 2, 3)])

    def test_unassisted_goal_has_no_assisters(self):
        self.assertEqual(shots.extract_goal_assists({"plays": [goal(1, 1, 9)]}), [(1, 9, None, None)])

    def test_shootout_goals_and_other_events_are_left_out(self):
        plays = [goal(1, 1, 9, period_type="SO"), {"eventId": 2, "sortOrder": 2, "typeDescKey": "shot-on-goal", "periodDescriptor": {"number": 1, "periodType": "REG"}}]
        self.assertEqual(shots.extract_goal_assists({"plays": plays}), [])


def play(event_id, order, kind, period=1, period_type="REG", clock="05:00", **details):
    return {"eventId": event_id, "sortOrder": order, "typeDescKey": kind, "timeInPeriod": clock,
            "periodDescriptor": {"number": period, "periodType": period_type}, "details": details}


class SpecialShotsTest(unittest.TestCase):
    def test_shootout_attempts_are_goals_saves_and_misses(self):
        pbp = {"plays": [play(1, 1, "goal", 5, "SO", scoringPlayerId=10, goalieInNetId=90, eventOwnerTeamId=1),
                         play(2, 2, "shot-on-goal", 5, "SO", shootingPlayerId=11, goalieInNetId=91, eventOwnerTeamId=2),
                         play(3, 3, "missed-shot", 5, "SO", shootingPlayerId=12, goalieInNetId=90, eventOwnerTeamId=1),
                         play(4, 4, "period-end", 5, "SO")]}
        out = shots.extract_special_shots(pbp)
        self.assertEqual([(o["kind"], o["shooter_id"], o["goalie_id"], o["scored"], o["on_goal"]) for o in out],
                         [("shootout", 10, 90, True, True), ("shootout", 11, 91, False, True), ("shootout", 12, 90, False, False)])

    def test_the_shot_after_a_penalty_shot_penalty_is_the_penalty_shot(self):
        pbp = {"plays": [play(1, 1, "penalty", typeCode="PS", descKey="ps-slash-on-breakaway"),
                         play(2, 2, "shot-on-goal", shootingPlayerId=20, goalieInNetId=95, eventOwnerTeamId=3),
                         play(3, 3, "shot-on-goal", clock="06:10", shootingPlayerId=21, goalieInNetId=95, eventOwnerTeamId=3)]}
        out = shots.extract_special_shots(pbp)
        self.assertEqual([(o["kind"], o["event_id"], o["shooter_id"], o["scored"]) for o in out], [("penalty_shot", 2, 20, False)])

    def test_an_ordinary_penalty_gives_no_penalty_shot(self):
        pbp = {"plays": [play(1, 1, "penalty", typeCode="MIN"), play(2, 2, "shot-on-goal", shootingPlayerId=20)]}
        self.assertEqual(shots.extract_special_shots(pbp), [])

    def test_a_penalty_shot_goal_counts_as_scored(self):
        pbp = {"plays": [play(1, 1, "penalty", typeCode="PS"), play(2, 2, "goal", scoringPlayerId=20, goalieInNetId=95, eventOwnerTeamId=3)]}
        self.assertTrue(shots.extract_special_shots(pbp)[0]["scored"])

