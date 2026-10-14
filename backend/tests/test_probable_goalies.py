import unittest

import probable_goalies as pg


def probs(candidates):
    return {c["player_id"]: c["probability"] for c in candidates}


class RepeatRate(unittest.TestCase):
    def test_no_data_falls_back_to_the_prior(self):
        self.assertAlmostEqual(pg.repeat_rate(0, 0), pg.REPEAT_PRIOR)

    def test_never_repeating_is_floored(self):
        # 0 repeats in 28 back-to-backs would shrink to 6%, but a rested goalie is never certain
        self.assertEqual(pg.repeat_rate(28, 0), pg.REPEAT_FLOOR)

    def test_plenty_of_data_moves_toward_the_observed_rate(self):
        self.assertAlmostEqual(pg.repeat_rate(100, 50), 53 / 120)


class Predict(unittest.TestCase):
    def test_no_history_gives_no_candidates(self):
        self.assertEqual(pg.predict([], False), [])

    def test_recent_starts_weigh_more(self):
        out = pg.predict([(1, "A"), (2, "B")], False)
        # weights 1 and 0.85
        self.assertAlmostEqual(probs(out)[1], 1 / 1.85, places=3)
        self.assertAlmostEqual(sum(probs(out).values()), 1.0, places=2)
        self.assertEqual([c["player_id"] for c in out], [1, 2])  # most likely first

    def test_back_to_back_rests_last_nights_starter(self):
        out = pg.predict([(1, "A"), (2, "B")], True, p_repeat=0.2)
        self.assertEqual(probs(out), {2: 0.8, 1: 0.2})

    def test_back_to_back_splits_the_rest_by_weight(self):
        out = pg.predict([(1, "A"), (2, "B"), (3, "C"), (3, "C")], True, p_repeat=0.1)
        p = probs(out)
        self.assertAlmostEqual(p[1], 0.1)
        self.assertAlmostEqual(p[2] + p[3], 0.9, places=2)
        self.assertGreater(p[3], p[2])  # C started twice, B once

    def test_a_lone_goalie_has_nobody_to_rest_him(self):
        self.assertEqual(probs(pg.predict([(1, "A"), (1, "A")], True)), {1: 1.0})

    def test_only_the_last_window_games_count(self):
        recent = [(1, "A")] * pg.WINDOW + [(2, "B")] * 5
        out = pg.predict(recent, False)
        self.assertEqual(probs(out), {1: 1.0})
        self.assertEqual(out[0]["starts"], pg.WINDOW)


class NextDistribution(unittest.TestCase):
    RECENT = [(1, "A"), (2, "B"), (1, "A"), (1, "A"), (2, "B"), (1, "A")]

    def test_empty_history(self):
        self.assertEqual(pg.next_distribution([], {}, True), {})

    def test_known_previous_starter_matches_predict(self):
        d = pg.next_distribution(self.RECENT, {1: 1.0}, True, 0.1, prepend=False)
        self.assertEqual({k: round(v, 3) for k, v in d.items()},
                         {k: round(v, 3) for k, v in probs(pg.predict(self.RECENT, True, 0.1)).items()})

    def test_probabilities_always_sum_to_one(self):
        d = pg.next_distribution(self.RECENT, {1: 1.0}, True, 0.1, prepend=False)
        for tired in (True, True, False, True):
            self.assertAlmostEqual(sum(d.values()), 1.0)
            d = pg.next_distribution(self.RECENT, d, tired, 0.1)
        self.assertAlmostEqual(sum(d.values()), 1.0)

    def test_the_starter_comes_back_after_a_backup_night(self):
        night1 = pg.next_distribution(self.RECENT, {1: 1.0}, True, 0.1, prepend=False)
        self.assertGreater(night1[2], 0.85)             # backup likely the night after A started
        night2 = pg.next_distribution(self.RECENT, night1, True, 0.1)
        self.assertGreater(night2[1], night1[1])        # so A is likelier again on the third night


class Confirmed(unittest.TestCase):
    BOX = {"homeTeam": {"abbrev": "NJD"}, "awayTeam": {"abbrev": "DET"},
           "playerByGameStats": {
               "homeTeam": {"goalies": [{"playerId": 1, "name": {"default": "J. Allen"}, "starter": True},
                                        {"playerId": 2, "name": {"default": "N. Daws"}, "starter": False}]},
               "awayTeam": {"goalies": [{"playerId": 3, "name": {"default": "J. Gibson"}, "starter": True}]}}}

    def test_reads_the_flagged_starter_for_each_team(self):
        self.assertEqual(pg.confirmed_starters(self.BOX), {"NJD": (1, "J. Allen"), "DET": (3, "J. Gibson")})

    def test_nothing_published_yet(self):
        self.assertEqual(pg.confirmed_starters({"homeTeam": {"abbrev": "A"}, "awayTeam": {"abbrev": "B"}}), {})

    def test_override_keeps_our_full_name_for_a_known_goalie(self):
        out = pg.apply_confirmed([{"player_id": 1, "name": "Jake Allen", "probability": 0.2, "starts": 4}], (1, "J. Allen"))
        self.assertEqual(out, [{"player_id": 1, "name": "Jake Allen", "probability": 1.0, "starts": 4}])

    def test_override_for_a_call_up_uses_the_boxscore_name(self):
        out = pg.apply_confirmed([{"player_id": 1, "name": "Jake Allen", "probability": 0.9, "starts": 4}], (9, "A. Callup"))
        self.assertEqual(out, [{"player_id": 9, "name": "A. Callup", "probability": 1.0, "starts": 0}])


if __name__ == "__main__":
    unittest.main()
