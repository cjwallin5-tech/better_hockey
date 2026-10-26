import unittest

import chemistry as ch


def together(toi=6000, cf=60, ca=40, xgf=3.0, xga=2.0):
    return {"toi": toi, "cf": cf, "ca": ca, "xgf": xgf, "xga": xga}


def total(toi, cf, ca, xgf, xga):
    return {"toi": toi, "cf": cf, "ca": ca, "xgf": xgf, "xga": xga}


class Basics(unittest.TestCase):
    def test_share_and_per60(self):
        self.assertAlmostEqual(ch.share(3, 1), 0.75)
        self.assertIsNone(ch.share(0, 0))
        self.assertIsNone(ch.share(None, 1))
        self.assertAlmostEqual(ch.per60(2.0, 3600), 2.0)
        self.assertAlmostEqual(ch.per60(1.0, 1800), 2.0)
        self.assertIsNone(ch.per60(1.0, 0))

    def test_verdict_needs_time_and_a_measurable_lift(self):
        self.assertIsNone(ch.verdict(0.1, 3.0, 600))
        self.assertIsNone(ch.verdict(None, 3.0, 6000))
        self.assertEqual(ch.verdict(0.02, 0.5, 6000), ("no clear effect", "none"))
        self.assertEqual(ch.verdict(0.05, 1.5, 6000), ("slight boost", "slight"))
        self.assertEqual(ch.verdict(-0.05, -2.5, 6000), ("clear drag", "clear"))


class PairView(unittest.TestCase):
    def test_apart_is_the_players_own_totals_minus_the_time_together(self):
        t = together()
        mine = total(12000, 120, 120, 6.0, 6.0)      # apart: 6000s, 60 cf, 80 ca, 3.0 xgf, 4.0 xga
        partner = total(9000, 90, 90, 4.5, 4.5)      # apart: 3000s, 30 cf, 50 ca, 1.5 xgf, 2.5 xga
        v = ch.pair_view(t, mine, partner)
        self.assertAlmostEqual(v["xg_share_together"], 0.6)
        self.assertAlmostEqual(v["xg_share_apart"], 3.0 / 7.0)
        self.assertAlmostEqual(v["xg_lift"], 0.6 - 3.0 / 7.0)
        self.assertAlmostEqual(v["xgf60_together"], 3.0 / 6000 * 3600)
        self.assertAlmostEqual(v["xgf60_apart"], 3.0 / 6000 * 3600)
        self.assertAlmostEqual(v["xga60_apart"], 4.0 / 6000 * 3600)
        self.assertEqual(v["basis"], "xg")
        self.assertGreater(v["xg_z"], 0)
        self.assertAlmostEqual(v["partner_xg_share_apart"], 1.5 / 4.0)       # the teammate's own view
        self.assertAlmostEqual(v["partner_xg_lift"], 0.6 - 1.5 / 4.0)

    def test_a_weak_partner_does_not_make_a_star_look_boosted(self):
        # the star is just as good apart (60%) as with the weak partner (60%); the partner is poor alone (35%)
        t = together(cf=600, ca=400, xgf=30.0, xga=20.0, toi=60000)
        star = total(120000, 1200, 800, 60.0, 40.0)
        weak = total(80000, 800, 1000, 35.0, 65.0)
        v = ch.pair_view(t, star, weak)
        self.assertAlmostEqual(v["xg_lift"], 0.0, places=6)
        self.assertEqual(v["verdict"], "no clear effect")
        self.assertGreater(v["partner_lift"], 0.2)       # the partner does get a big lift from playing with the star
        self.assertEqual(v["partner_verdict"], "clear boost")

    def test_a_strong_lift_over_lots_of_attempts_is_a_clear_boost_and_a_small_sample_is_not(self):
        big = ch.pair_view(together(cf=600, ca=300, xgf=30.0, xga=15.0, toi=60000),
                           total(120000, 1200, 1200, 70.0, 70.0), total(100000, 1000, 1000, 55.0, 55.0))
        self.assertEqual(big["verdict"], "clear boost")
        small = ch.pair_view(together(cf=12, ca=8, xgf=0.9, xga=0.4, toi=1200),
                             total(12000, 120, 120, 6.0, 6.0), total(9000, 90, 90, 4.5, 4.5))
        self.assertIsNone(small["verdict"])      # under the time threshold

    def test_a_drag(self):
        v = ch.pair_view(together(cf=300, ca=600, xgf=15.0, xga=30.0, toi=60000),
                         total(120000, 1200, 1200, 70.0, 70.0), total(100000, 1000, 1000, 55.0, 55.0))
        self.assertEqual(v["verdict"], "clear drag")
        self.assertLess(v["lift"], 0)

    def test_a_player_who_is_nearly_always_with_the_teammate_gets_no_verdict(self):
        # 99% of his attempts are with this teammate: almost nothing apart to compare against
        t = together(cf=990, ca=500, xgf=45.0, xga=20.0, toi=100000)
        v = ch.pair_view(t, total(101000, 1000, 505, 46.0, 20.5), total(100000, 1000, 1000, 55.0, 55.0))
        self.assertIsNotNone(v["lift"])
        self.assertEqual(v["strength"], "none")      # present, but the z is small against so little apart data

    def test_falls_back_to_corsi_when_expected_goals_are_not_stored(self):
        t = together(cf=600, ca=300, xgf=None, xga=None, toi=60000)
        v = ch.pair_view(t, total(120000, 1200, 1200, None, None), total(100000, 1000, 1000, None, None))
        self.assertEqual(v["basis"], "corsi")
        self.assertIsNone(v["xg_lift"])
        self.assertEqual(v["verdict"], "clear boost")
        self.assertAlmostEqual(v["lift"], v["cf_lift"])

    def test_no_totals_means_no_comparison(self):
        v = ch.pair_view(together(), None, None)
        self.assertIsNone(v["lift"])
        self.assertIsNone(v["verdict"])
        self.assertAlmostEqual(v["xg_share_together"], 0.6)

    def test_missing_partner_still_compares_the_player_with_himself_apart(self):
        v = ch.pair_view(together(), total(12000, 120, 120, 6.0, 6.0), None)
        self.assertAlmostEqual(v["xg_share_apart"], 3.0 / 7.0)
        self.assertIsNone(v["partner_lift"])


class BestWorst(unittest.TestCase):
    def test_only_rated_boosts_and_drags(self):
        rows = [{"strength": "clear", "lift": 0.08, "z": 3.0, "n": "a"}, {"strength": "slight", "lift": 0.03, "z": 1.4, "n": "b"},
                {"strength": "clear", "lift": -0.06, "z": -2.4, "n": "c"}, {"strength": "none", "lift": 0.01, "z": 0.2, "n": "d"},
                {"strength": None, "lift": 0.2, "z": 9.0, "n": "e"}]
        best, worst = ch.best_and_worst(rows)
        self.assertEqual((best["n"], worst["n"]), ("a", "c"))
        self.assertEqual(ch.best_and_worst([]), (None, None))
        self.assertEqual(ch.best_and_worst([rows[1]]), (rows[1], None))


if __name__ == "__main__":
    unittest.main()
