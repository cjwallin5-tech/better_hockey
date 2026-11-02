import unittest

import goaliemap as gm


def shot(kind="shot", xg=0.1, distance=20.0, angle=30.0, y=10.0, **kw):
    return {"kind": kind, "xg": xg, "distance": distance, "angle": angle, "y": y, **kw}


class Zones(unittest.TestCase):
    def test_range_bands(self):
        self.assertEqual(gm.zone(shot(distance=10), "L")[0], "close")
        self.assertEqual(gm.zone(shot(distance=15), "L")[0], "mid")
        self.assertEqual(gm.zone(shot(distance=34.9), "L")[0], "mid")
        self.assertEqual(gm.zone(shot(distance=60), "L")[0], "long")

    def test_straight_on_is_the_middle_either_side(self):
        self.assertEqual(gm.zone(shot(angle=10, y=3), "L")[1], "middle")
        self.assertEqual(gm.zone(shot(angle=10, y=-3), "R")[1], "middle")

    def test_glove_side_follows_the_catching_hand(self):
        # shooter's left is +y, so a left-catching goalie has the glove toward -y
        self.assertEqual(gm.zone(shot(y=-20), "L")[1], "glove")
        self.assertEqual(gm.zone(shot(y=20), "L")[1], "blocker")
        self.assertEqual(gm.zone(shot(y=20), "R")[1], "glove")
        self.assertEqual(gm.zone(shot(y=-20), "R")[1], "blocker")

    def test_unknown_location_has_no_zone(self):
        self.assertIsNone(gm.zone(shot(distance=None), "L"))


class Summary(unittest.TestCase):
    def test_gsax_is_expected_minus_actual(self):
        shots = [shot(kind="goal", xg=0.1, y=-20)] + [shot(xg=0.1, y=-20) for _ in range(9)]
        s = gm.summarize(shots, 1.0, "L")
        z = next(z for z in s["zones"] if (z["range"], z["lane"]) == ("mid", "glove"))
        self.assertEqual((z["shots"], z["goals"]), (10, 1))
        self.assertAlmostEqual(z["xg"], 1.0)
        self.assertAlmostEqual(z["gsax"], 0.0)

    def test_factor_scales_expected_goals(self):
        s = gm.summarize([shot(xg=0.1) for _ in range(10)], 2.0, "L")
        self.assertAlmostEqual(s["total"]["xg"], 2.0)

    def test_empty_net_misses_and_unmodeled_shots_are_left_out(self):
        shots = [shot(), shot(empty_net=True), shot(kind="miss"), shot(kind="block"), shot(xg=None)]
        s = gm.summarize(shots, 1.0, "L")
        self.assertEqual(s["total"]["shots"], 1)
        self.assertEqual(s["skipped"], 2)

    def test_flag_needs_a_real_sample_and_a_big_gap(self):
        leaky = [shot(kind="goal", xg=0.05, y=-20) for _ in range(20)]
        s = gm.summarize(leaky, 1.0, "L")
        z = next(z for z in s["zones"] if z["shots"])
        self.assertTrue(z["flag"])
        self.assertLess(z["gsax"], 0)
        few = gm.summarize(leaky[:5], 1.0, "L")
        self.assertFalse(next(z for z in few["zones"] if z["shots"])["flag"])

    def test_headline_picks_extremes(self):
        shots = ([shot(kind="goal", xg=0.1, y=-20, distance=10) for _ in range(5)] + [shot(xg=0.1, y=-20, distance=10) for _ in range(20)]
                 + [shot(xg=0.1, y=20, distance=50) for _ in range(25)])
        h = gm.headline(gm.summarize(shots, 1.0, "L"))
        self.assertEqual((h["worst"]["range"], h["worst"]["lane"]), ("close", "glove"))
        self.assertEqual((h["best"]["range"], h["best"]["lane"]), ("long", "blocker"))
        self.assertIsNone(gm.headline(gm.summarize([], 1.0, "L")))


class Calibration(unittest.TestCase):
    def test_league_sits_at_zero_in_every_group_after_calibration(self):
        # the model says 10% everywhere, but slot shots score 20% and point shots 5%
        league = ([shot(kind="goal", xg=0.1, distance=10, angle=0, y=0, catches="L")] * 20
                  + [shot(xg=0.1, distance=10, angle=0, y=0, catches="L")] * 80
                  + [shot(kind="goal", xg=0.1, distance=50, angle=30, y=-20, catches="L")] * 5
                  + [shot(xg=0.1, distance=50, angle=30, y=-20, catches="L")] * 95)
        cal = gm.league_calibration(league, 1.0)
        s = gm.summarize(league, 1.0, "L", cal)
        for z in s["zones"]:
            if z["shots"]:
                self.assertAlmostEqual(z["gsax"], 0.0, places=1)

    def test_a_goalie_is_compared_with_the_league_in_the_same_zone(self):
        league = ([shot(kind="goal", xg=0.1, distance=10, angle=0, y=0, catches="L")] * 20
                  + [shot(xg=0.1, distance=10, angle=0, y=0, catches="L")] * 80)
        cal = gm.league_calibration(league, 1.0)
        mine = [shot(kind="goal", xg=0.1, distance=10, angle=0, y=0)] * 10 + [shot(xg=0.1, distance=10, angle=0, y=0)] * 90
        z = next(z for z in gm.summarize(mine, 1.0, "L", cal)["zones"] if z["shots"])
        self.assertAlmostEqual(z["xg"], 20.0, places=1)   # an average goalie lets in 20 of these
        self.assertAlmostEqual(z["gsax"], 10.0, places=1)


class Seasons(unittest.TestCase):
    def test_each_season_uses_its_own_scale_and_is_reported_separately(self):
        a = [shot(xg=0.1, f=1.0, season_id=1)] * 10
        b = [shot(xg=0.1, f=2.0, season_id=2)] * 10
        s = gm.summarize(a + b, 1.0, "L")
        self.assertEqual(s["seasons"], [1, 2])
        self.assertAlmostEqual(s["total"]["xg"], 3.0)
        z = next(z for z in s["zones"] if z["shots"])
        self.assertAlmostEqual(z["by_season"][1], 1.0)
        self.assertAlmostEqual(z["by_season"][2], 2.0)


if __name__ == "__main__":
    unittest.main()
