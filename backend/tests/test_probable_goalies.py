import unittest
from unittest import mock

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


def raw_model(case):
    """Run a test class against the shares before the confidence correction (SHRINK 0), so the weighting rules are tested on their own."""
    patcher = mock.patch.object(pg, "SHRINK", 0.0)
    patcher.start()
    case.addCleanup(patcher.stop)


class Predict(unittest.TestCase):
    def setUp(self):
        raw_model(self)

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

    def test_a_lone_known_goalie_is_not_certain_there_is_an_unseen_backup(self):
        # rested: the rule of succession for k straight starts
        self.assertAlmostEqual(probs(pg.predict([(1, "A")] * 3, False))[1], 4 / 5, places=3)
        self.assertAlmostEqual(probs(pg.predict([(1, "A")] * 9, False))[1], 10 / 11, places=3)
        # second night of a back-to-back: only as likely to go again as the repeat rate says
        self.assertAlmostEqual(probs(pg.predict([(1, "A")] * 3, True, p_repeat=0.2))[1], 0.2, places=3)

    def test_only_the_last_window_games_count(self):
        recent = [(1, "A")] * pg.WINDOW + [(2, "B")] * 5
        out = pg.predict(recent, False)
        self.assertEqual(list(probs(out)), [1])                       # B's older starts are outside the window
        self.assertAlmostEqual(probs(out)[1], (pg.WINDOW + 1) / (pg.WINDOW + 2), places=3)
        self.assertEqual(out[0]["starts"], pg.WINDOW)


class Calibrate(unittest.TestCase):
    def test_shares_are_pulled_toward_an_even_split_and_still_add_up_to_one(self):
        out = pg.calibrate({1: 0.9, 2: 0.1})
        self.assertAlmostEqual(out[1], 0.8 * 0.9 + 0.2 * 0.5)
        self.assertAlmostEqual(out[2], 0.8 * 0.1 + 0.2 * 0.5)
        self.assertAlmostEqual(sum(out.values()), 1.0)

    def test_it_never_changes_who_is_most_likely(self):
        raw = {1: 0.5, 2: 0.3, 3: 0.2}
        out = pg.calibrate(raw)
        self.assertEqual(sorted(out, key=out.get), sorted(raw, key=raw.get))

    def test_a_lone_goalie_stays_certain_and_a_high_share_is_lowered(self):
        self.assertEqual(pg.calibrate({1: 1.0}), {1: 1.0})
        with mock.patch.object(pg, "SHRINK", 0.0):
            raw_top = probs(pg.predict([(1, "A")] * 9 + [(2, "B")], False))[1]
        self.assertLess(probs(pg.predict([(1, "A")] * 9 + [(2, "B")], False))[1], raw_top)

    def test_predict_applies_it_by_default(self):
        out = probs(pg.predict([(1, "A"), (2, "B")], False))
        raw = {1: 1 / 1.85, 2: 0.85 / 1.85}
        self.assertAlmostEqual(out[1], (1 - pg.SHRINK) * raw[1] + pg.SHRINK / 2, places=3)
        self.assertAlmostEqual(sum(out.values()), 1.0, places=2)


class NextDistribution(unittest.TestCase):
    def setUp(self):
        raw_model(self)

    RECENT = [(1, "A"), (2, "B"), (1, "A"), (1, "A"), (2, "B"), (1, "A")]

    def test_empty_history(self):
        self.assertEqual(pg.next_distribution([], {}, True), {})

    def test_known_previous_starter_matches_predict(self):
        d = pg.next_distribution(self.RECENT, {1: 1.0}, True, 0.1, prepend=False)
        self.assertEqual({k: round(v, 3) for k, v in d.items()},
                         {k: round(v, 3) for k, v in probs(pg.predict(self.RECENT, True, 0.1)).items()})

    def test_a_lone_goalies_chain_does_not_shrink_to_nothing(self):
        d = {1: 1.0}
        seen = []
        for _ in range(8):
            d = pg.next_distribution([(1, "A")] * 4, d, False, 0.1)
            seen.append(d[1])
        # each step is the rule of succession for the 4 starts plus the one just assumed (6/7), not that figure compounding
        self.assertTrue(all(abs(x - 6 / 7) < 1e-3 for x in seen), seen)

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
