import unittest

import shootermap as sm


def shot(kind="shot", xg=0.1, distance=20.0, angle=30.0, y=10.0, **kw):
    return {"kind": kind, "xg": xg, "distance": distance, "angle": angle, "y": y, "season_id": 1, **kw}


class Zones(unittest.TestCase):
    def test_left_is_positive_y_as_the_shooter_sees_it(self):
        self.assertEqual(sm.zone(shot(y=12)), ("mid", "left"))
        self.assertEqual(sm.zone(shot(y=-12)), ("mid", "right"))
        self.assertEqual(sm.zone(shot(angle=5, y=2)), ("mid", "middle"))

    def test_ranges_match_the_goalie_map(self):
        self.assertEqual([sm.zone(shot(distance=d))[0] for d in (5, 20, 50)], ["close", "mid", "long"])

    def test_unknown_location_has_no_zone(self):
        self.assertIsNone(sm.zone(shot(y=None)))


class Profile(unittest.TestCase):
    def test_blocked_empty_net_and_unmodelled_attempts_are_left_out(self):
        rows = [shot(), shot(kind="block"), shot(empty_net=True), shot(xg=None), shot(kind="miss")]
        self.assertEqual(len(sm.usable(rows)), 2)

    def test_each_season_is_scaled_to_its_own_goals(self):
        rows = [shot(kind="goal", xg=0.1, season_id=1)] + [shot(xg=0.1, season_id=1)] * 9      # 10% goals on 0.1 xG: factor 1
        rows += [shot(kind="goal", xg=0.1, season_id=2)] * 2 + [shot(xg=0.1, season_id=2)] * 8  # 20% goals: factor 2
        f = sm.season_factors(rows)
        self.assertAlmostEqual(f[1], 1.0)
        self.assertAlmostEqual(f[2], 2.0)

    def test_the_league_sits_at_zero_in_every_zone_after_calibration(self):
        slot = [shot(kind="goal", xg=0.1, distance=10, angle=0, y=0)] * 20 + [shot(xg=0.1, distance=10, angle=0, y=0)] * 80
        point = [shot(kind="goal", xg=0.1, distance=50, angle=30, y=5)] * 5 + [shot(xg=0.1, distance=50, angle=30, y=5)] * 95
        cal, shares = sm.league_profile(slot + point)
        out = sm.summarize(slot + point, cal, shares)
        for z in out["zones"]:
            if z["attempts"]:
                self.assertAlmostEqual(z["gsax"], 0.0, places=1)
        self.assertAlmostEqual(shares[("close", "middle")], 0.5)

    def test_a_shooter_is_compared_with_the_league_in_the_same_zone(self):
        league = [shot(kind="goal", xg=0.1, distance=10, angle=0, y=0)] * 20 + [shot(xg=0.1, distance=10, angle=0, y=0)] * 80
        cal, shares = sm.league_profile(league)
        mine = [shot(kind="goal", xg=0.1, distance=10, angle=0, y=0)] * 30 + [shot(xg=0.1, distance=10, angle=0, y=0)] * 70
        z = next(z for z in sm.summarize(mine, cal, shares)["zones"] if z["attempts"])
        self.assertAlmostEqual(z["xg"], 20.0, places=1)     # an average shooter scores 20 of these
        self.assertAlmostEqual(z["gsax"], 10.0, places=1)   # he scored 30
        self.assertGreater(z["z"], 2)
        self.assertTrue(z["flag"])

    def test_shares_are_of_his_own_attempts(self):
        mine = [shot(distance=10, angle=0, y=0)] * 30 + [shot(distance=50, angle=30, y=5)] * 10
        zs = {(z["range"], z["lane"]): z for z in sm.summarize(mine)["zones"]}
        self.assertAlmostEqual(zs[("close", "middle")]["share"], 0.75)
        self.assertAlmostEqual(zs[("long", "left")]["share"], 0.25)

    def test_headline_names_best_worst_and_favoured_zones(self):
        mine = ([shot(kind="goal", xg=0.1, distance=10, angle=0, y=0)] * 10 + [shot(xg=0.1, distance=10, angle=0, y=0)] * 20
                + [shot(xg=0.1, distance=50, angle=30, y=5)] * 25)
        h = sm.headline(sm.summarize(mine, {}, {("long", "left"): 0.5}))
        self.assertEqual((h["best"]["range"], h["best"]["lane"]), ("close", "middle"))
        self.assertEqual((h["worst"]["range"], h["worst"]["lane"]), ("long", "left"))
        self.assertEqual((h["favours"]["range"], h["favours"]["lane"]), ("close", "middle"))
        self.assertIsNone(sm.headline(sm.summarize([])))

    def test_results_are_reported_season_by_season(self):
        mine = [shot(kind="goal", xg=0.1, season_id=1)] * 5 + [shot(xg=0.1, season_id=2)] * 5
        z = next(z for z in sm.summarize(mine)["zones"] if z["attempts"])
        self.assertEqual(sorted(z["by_season"]), [1, 2])


if __name__ == "__main__":
    unittest.main()
