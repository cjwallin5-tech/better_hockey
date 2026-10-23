import unittest

import explain as ex

G = 84


def facts(**kw):
    base = {"name": "Test Skater", "gp": 20, "goals": 12, "assists": 16, "points": 28, "games": G, "team": "EDM",
            "last": {"gp": 80, "goals": 30, "assists": 40, "points": 70, "team": "EDM", "toi_sec": 1200, "attempts": 240, "ixg": 24.0},
            "now": {"toi_sec": 1200, "attempts": 60, "ixg": 6.0}}
    base.update(kw)
    return base


def keys(result):
    return [x["key"] for x in result["findings"]]


class Pace(unittest.TestCase):
    def test_pace_and_change_use_a_full_season_of_the_same_length(self):
        r = ex.explain(facts())
        self.assertAlmostEqual(r["pace"], 28 / 20 * G)
        self.assertAlmostEqual(r["last_pace"], 70 / 80 * G)
        self.assertAlmostEqual(r["change"], r["pace"] - r["last_pace"])

    def test_a_quiet_player_says_nothing_stands_out(self):
        r = ex.explain(facts())
        self.assertEqual(r["findings"], [])
        self.assertIn("Nothing stands out", r["headline"])

    def test_no_games_this_season(self):
        r = ex.explain(facts(gp=0, points=0, goals=0, assists=0))
        self.assertIsNone(r["pace"])
        self.assertIn("no games", r["headline"])


class Luck(unittest.TestCase):
    LK = {"enough": True, "diff_adj": 3.0, "goals": 12, "ixg": 8.0, "skill": 0.1, "assist_luck": 2.0}

    def test_finishing_is_priced_over_a_full_season(self):
        r = ex.explain(facts(luck=self.LK))
        f = next(x for x in r["findings"] if x["key"] == "finishing")
        self.assertAlmostEqual(f["price"], 3.0 * G / 20)
        self.assertEqual((f["kind"], f["direction"]), ("luck", "up"))

    def test_teammates_scoring_needs_a_bigger_gap(self):
        small = dict(self.LK, assist_luck=0.2)
        self.assertNotIn("teammates", keys(ex.explain(facts(luck=small))))
        self.assertIn("teammates", keys(ex.explain(facts(luck=self.LK))))

    def test_luck_is_ignored_on_a_small_sample(self):
        self.assertEqual(keys(ex.explain(facts(luck=dict(self.LK, enough=False)))), [])

    def test_cold_finishing_points_down(self):
        f = next(x for x in ex.explain(facts(luck=dict(self.LK, diff_adj=-3.0)))["findings"] if x["key"] == "finishing")
        self.assertEqual(f["direction"], "down")
        self.assertLess(f["price"], 0)


class RealChanges(unittest.TestCase):
    def test_more_shots_at_last_seasons_quality(self):
        # 4.5 attempts a game now against 3.0 last season; 0.1 expected goals each
        r = ex.explain(facts(now={"toi_sec": 1200, "attempts": 90, "ixg": 9.0}))
        v = next(x for x in r["findings"] if x["key"] == "volume")
        self.assertAlmostEqual(v["price"], (4.5 - 3.0) * 0.1 * G)
        self.assertEqual(v["kind"], "real")

    def test_better_shots(self):
        r = ex.explain(facts(now={"toi_sec": 1200, "attempts": 60, "ixg": 9.0}))   # 0.15 per attempt against 0.10
        q = next(x for x in r["findings"] if x["key"] == "quality")
        self.assertAlmostEqual(q["price"], (0.15 - 0.10) * 3.0 * G)

    def test_more_ice_time_at_last_seasons_scoring_per_minute(self):
        r = ex.explain(facts(now={"toi_sec": 1380, "attempts": 60, "ixg": 6.0}))   # three more minutes a game
        t = next(x for x in r["findings"] if x["key"] == "ice_time")
        self.assertAlmostEqual(t["price"], 3 * (70 / 80 / 20) * G)   # last season: 0.875 points in 20 minutes

    def test_a_short_sample_or_baseline_gives_no_comparison(self):
        self.assertEqual(keys(ex.explain(facts(gp=3, now={"toi_sec": 1800, "attempts": 40, "ixg": 8.0}))), [])
        short_last = dict(facts()["last"], gp=10)
        self.assertEqual(keys(ex.explain(facts(last=short_last, now={"toi_sec": 1800, "attempts": 90, "ixg": 9.0}))), [])

    def test_a_new_team_is_noted(self):
        last = dict(facts()["last"], team="TOR")
        self.assertIn("team", keys(ex.explain(facts(last=last))))
        traded = dict(facts()["last"], team="NYR,TOR")   # last stop was TOR
        self.assertNotIn("team", keys(ex.explain(facts(last=traded, team="TOR"))))


class RoleAndLines(unittest.TestCase):
    ROLE = {"pp_change": "up", "pp_label": "Promoted to PP1", "pp": 150, "pp_base": 60, "ev_change": None, "window": 5, "direction": "up"}

    def test_power_play_promotion_is_priced_at_the_players_rate(self):
        r = ex.explain(facts(role=self.ROLE, pp_points_per60=6.0))
        f = next(x for x in r["findings"] if x["key"] == "role")
        self.assertAlmostEqual(f["price"], 90 / 3600 * 6.0 * G)
        self.assertIn("Promoted to PP1", f["text"])

    def test_role_without_a_rate_is_unpriced(self):
        f = next(x for x in ex.explain(facts(role=self.ROLE))["findings"] if x["key"] == "role")
        self.assertIsNone(f["price"])

    def test_new_linemates_are_reported(self):
        lm = {"season": [{"id": 1, "name": "A", "ppg": 0.5}, {"id": 2, "name": "B", "ppg": 0.6}],
              "recent": [{"id": 3, "name": "C", "ppg": 1.4}, {"id": 4, "name": "D", "ppg": 1.2}], "recent_games": 5}
        f = next(x for x in ex.explain(facts(linemates=lm))["findings"] if x["key"] == "linemates")
        self.assertEqual(f["direction"], "up")
        self.assertIn("C and D", f["text"])

    def test_the_same_linemates_say_nothing_unless_they_are_stars(self):
        same = {"season": [{"id": 1, "name": "A", "ppg": 0.5}, {"id": 2, "name": "B", "ppg": 0.6}],
                "recent": [{"id": 1, "name": "A", "ppg": 0.5}, {"id": 2, "name": "B", "ppg": 0.6}], "recent_games": 5}
        self.assertNotIn("linemates", keys(ex.explain(facts(linemates=same))))
        stars = {"season": [{"id": 1, "name": "A", "ppg": 1.5}, {"id": 2, "name": "B", "ppg": 1.2}], "recent": [], "recent_games": 0}
        self.assertIn("linemates", keys(ex.explain(facts(linemates=stars))))


class Summary(unittest.TestCase):
    def test_the_change_is_split_into_luck_real_and_the_rest(self):
        lk = {"enough": True, "diff_adj": 2.0, "goals": 10, "ixg": 6.0, "skill": 0.0, "assist_luck": 0.0}
        r = ex.explain(facts(luck=lk, now={"toi_sec": 1200, "attempts": 90, "ixg": 9.0}))
        self.assertAlmostEqual(r["unexplained"], r["change"] - r["luck_total"] - r["real_total"])
        self.assertIn("left unexplained", r["headline"])

    def test_a_small_sample_is_flagged_early(self):
        self.assertTrue(ex.explain(facts(gp=9))["early"])
        self.assertFalse(ex.explain(facts(gp=40))["early"])

    def test_no_baseline_means_no_split(self):
        r = ex.explain(facts(last=None))
        self.assertIsNone(r["unexplained"])
        self.assertIsNone(r["last_pace"])


class Ordering(unittest.TestCase):
    def test_biggest_price_first_and_totals_split_luck_from_real(self):
        lk = {"enough": True, "diff_adj": 2.0, "goals": 10, "ixg": 6.0, "skill": 0.0, "assist_luck": 0.0}
        r = ex.explain(facts(luck=lk, now={"toi_sec": 1200, "attempts": 90, "ixg": 9.0}))
        prices = [abs(x["price"]) for x in r["findings"] if x["price"] is not None]
        self.assertEqual(prices, sorted(prices, reverse=True))
        self.assertAlmostEqual(r["luck_total"], 2.0 * G / 20)
        self.assertGreater(r["real_total"], 0)


if __name__ == "__main__":
    unittest.main()
