import unittest

import goaliemap as gm
import matchupfit as mf


def summary(zone_gsax, shots_per_zone=100):
    """A goaliemap-style summary with a given gsax in each (range, lane); every other zone has 0."""
    zones = []
    for rng in gm.RANGES:
        for lane in gm.LANES:
            g = zone_gsax.get((rng, lane), 0.0)
            zones.append({"range": rng, "lane": lane, "shots": shots_per_zone, "gsax": g})
    return {"zones": zones, "total": {"shots": 9 * shots_per_zone, "gsax": sum(z["gsax"] for z in zones)}}


class Rates(unittest.TestCase):
    def test_rates_are_shrunk_toward_zero(self):
        rates, over = mf.goalie_rates(summary({("mid", "glove"): 10.0}), k=300)
        self.assertAlmostEqual(rates[("mid", "glove")], 10.0 / 400)
        self.assertAlmostEqual(over, 10.0 / (900 + 300))

    def test_a_thin_record_moves_less_than_a_thick_one(self):
        thin, _ = mf.goalie_rates(summary({("mid", "glove"): 5.0}, shots_per_zone=20), k=300)
        thick, _ = mf.goalie_rates(summary({("mid", "glove"): 5.0}, shots_per_zone=500), k=300)
        self.assertLess(abs(thin[("mid", "glove")]) - abs(thick[("mid", "glove")]), 1)   # per-shot rates, both small
        self.assertGreater(thin[("mid", "glove")], thick[("mid", "glove")])


class Lanes(unittest.TestCase):
    def test_glove_side_follows_the_catching_hand(self):
        self.assertEqual(mf.lane_for("neg", "L"), "glove")
        self.assertEqual(mf.lane_for("pos", "L"), "blocker")
        self.assertEqual(mf.lane_for("pos", "R"), "glove")
        self.assertEqual(mf.lane_for("middle", "R"), "middle")
        self.assertEqual(mf.lane_for("neg", None), "glove")

    def test_agrees_with_the_goalie_map(self):
        for y, catches in ((10, "L"), (-10, "L"), (10, "R"), (-10, "R")):
            side = "pos" if y > 0 else "neg"
            z = gm.zone({"distance": 20, "angle": 40, "y": y}, catches)
            self.assertEqual(z[1], mf.lane_for(side, catches))


class Diet(unittest.TestCase):
    def test_shares_sum_to_one_and_blend_with_last_season(self):
        shares, n = mf.diet({("mid", "pos"): 30, ("mid", "neg"): 10}, {("mid", "neg"): 600}, prior_shots=300)
        self.assertAlmostEqual(sum(shares.values()), 1.0)
        self.assertGreater(shares[("mid", "neg")], 10 / 40)
        self.assertEqual(n, 40 + 300)

    def test_no_prior_is_just_this_season(self):
        shares, n = mf.diet({("close", "middle"): 5, ("long", "pos"): 5})
        self.assertEqual(shares, {("close", "middle"): 0.5, ("long", "pos"): 0.5})
        self.assertEqual(n, 10)


class Fit(unittest.TestCase):
    def test_a_team_that_shoots_where_he_leaks_gets_a_positive_fit(self):
        s = summary({("mid", "blocker"): -30.0, ("mid", "glove"): 30.0})
        rates, over = mf.goalie_rates(s)
        # catches L: the glove side is rink y < 0 ('neg'); a team shooting from 'pos' (his blocker side, where he leaks)
        leaky = mf.fit({("mid", "pos"): 1.0}, 30, rates, over, "L")
        strong = mf.fit({("mid", "neg"): 1.0}, 30, rates, over, "L")
        self.assertGreater(leaky["fit_goals"], 0.1)        # more goals for the shooting team than his average gives
        self.assertLess(strong["fit_goals"], -0.1)
        self.assertTrue(leaky["notable"])
        self.assertEqual((leaky["zones"][0]["range"], leaky["zones"][0]["lane"]), ("mid", "blocker"))

    def test_the_shots_he_usually_faces_have_no_fit(self):
        s = summary({("mid", "blocker"): -30.0, ("mid", "glove"): 30.0})
        rates, over = mf.goalie_rates(s)
        even = mf.fit({(r, side): 1 / 9 for r in gm.RANGES for side in ("pos", "middle", "neg")}, 30, rates, over, "L")
        self.assertAlmostEqual(even["fit_goals"], 0.0, places=6)
        self.assertFalse(even["notable"])

    def test_goalie_goals_come_from_his_overall_rate(self):
        rates, over = mf.goalie_rates(summary({("long", "glove"): 12.0}))
        out = mf.fit({("long", "neg"): 1.0}, 30, rates, over, "L")
        self.assertAlmostEqual(out["goalie_goals"], -30 * over, places=3)


def entry(fit_goals=0.12, **over):
    base = {"team": "EDM", "fit_goals": fit_goals, "goalie_goals": -0.15, "shots_per_game": 25, "notable": True,
            "goalie": {"name": "Devin Cooley", "probability": 0.66, "confirmed": False},
            "zones": [{"range": "mid", "lane": "blocker", "share": 0.16, "league_share": 0.13, "rate_per_100": 2.1, "goals": 0.08}]}
    base.update(over)
    return base


class Wording(unittest.TestCase):
    def test_zones_read_as_a_place_on_the_ice(self):
        self.assertEqual(mf.zone_label({"range": "mid", "lane": "blocker"}), "mid-range, blocker side")
        self.assertEqual(mf.zone_label({"range": "close", "lane": "middle"}), "close range through the middle")

    def test_a_leaky_zone_is_worded_as_a_leak_from_the_shooting_teams_side(self):
        s = mf.sentence(entry())
        self.assertIn("Devin Cooley gives up +2.1 goals per 100 shots from mid-range, blocker side (16% of their shots, 13% league-wide)", s)
        self.assertIn("against -0.6 overall", s)
        self.assertIn("Worth about +0.12 goals to EDM", s)

    def test_a_strong_zone_is_worded_as_a_strength(self):
        s = mf.sentence(entry(fit_goals=-0.12, zones=[{"range": "long", "lane": "glove", "share": 0.2, "league_share": 0.15, "rate_per_100": -1.5, "goals": -0.08}]))
        self.assertIn("better than his average", s)
        self.assertIn("-0.12 goals to EDM", s)

    def test_the_goalies_view_says_more_or_fewer_goals_against(self):
        self.assertIn("about 0.12 more goals against than his usual", mf.goalie_sentence(entry()))
        self.assertIn("about 0.12 fewer goals against than his usual", mf.goalie_sentence(entry(fit_goals=-0.12)))

    def test_start_notes(self):
        self.assertEqual(mf.start_note({"confirmed": True, "probability": 1.0}), "confirmed starter")
        self.assertEqual(mf.start_note({"confirmed": False, "probability": 0.66}), "likely starter, 66%")
        self.assertEqual(mf.start_note({"confirmed": False, "probability": None}), "starter unclear")


if __name__ == "__main__":
    unittest.main()
