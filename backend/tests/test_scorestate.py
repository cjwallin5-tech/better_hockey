import unittest

import scorestate as ss


def shot(eid, t, home, kind="shot", xg=0.1, strength="ev", period=1, team=None, opp=None, **kw):
    return {"event_id": eid, "time_sec": t, "is_home": home, "kind": kind, "xg": xg, "strength": strength,
            "period": period, "team": team or ("H" if home else "A"), "opponent": opp or ("A" if home else "H"), **kw}


class Annotate(unittest.TestCase):
    def test_the_score_before_each_shot_decides_its_state(self):
        game = [shot(1, 100, True), shot(2, 200, True, kind="goal"), shot(3, 300, False), shot(4, 400, True, kind="goal"),
                shot(5, 500, False)]
        got = [(s["event_id"], s["state"]) for s in ss.annotate(game)]
        self.assertEqual(got, [(1, "tied"), (2, "tied"), (3, "trail1"), (4, "lead1"), (5, "trail2")])

    def test_order_comes_from_time_then_event_id_not_input_order(self):
        game = [shot(2, 200, False), shot(1, 200, True, kind="goal")]
        self.assertEqual([s["event_id"] for s in ss.annotate(game)], [1, 2])
        self.assertEqual(ss.annotate(game)[1]["state"], "trail1")

    def test_state_boundaries(self):
        self.assertEqual([ss.state_of(d) for d in (-3, -2, -1, 0, 1, 2, 5)],
                         ["trail2", "trail2", "trail1", "tied", "lead1", "lead2", "lead2"])


class Adjustment(unittest.TestCase):
    def league(self):
        # Trailing teams get 60% of the xG; the leaders 40%: a typical score effect. Team H leads a lot, A trails.
        rows = []
        eid = 0
        for _ in range(60):   # H trailing... shots by the trailing side
            eid += 1
            rows.append({**shot(eid, eid, True, xg=0.1), "state": "trail1", "diff": -1})
        for _ in range(40):
            eid += 1
            rows.append({**shot(eid, eid, False, xg=0.1), "state": "lead1", "diff": 1})
        return rows

    def test_league_share_reflects_the_trailing_side_shooting_more(self):
        t = ss.team_tallies(self.league())
        self.assertAlmostEqual(ss.league_share(t, "xg")["trail1"], 0.6)
        self.assertAlmostEqual(ss.league_share(t, "xg")["lead1"], 0.4)

    def test_adjusted_share_is_even_when_a_team_only_played_the_typical_score_effect(self):
        # every event in this league follows the typical effect exactly, so each team's adjusted share is 50%
        rows, _ = ss.team_rows(ss.team_tallies(self.league()))
        for r in rows:
            self.assertAlmostEqual(r["xg_pct_adj"], 0.5, places=3)
        self.assertNotAlmostEqual(rows[0]["xg_pct"], 0.5, places=2)   # raw shares are lopsided

    def test_only_even_strength_regulation_attempts_count(self):
        rows = [{**shot(1, 1, True, strength="pp"), "state": "tied", "diff": 0},
                {**shot(2, 2, True, period=4), "state": "tied", "diff": 0},
                {**shot(3, 3, True, kind="block"), "state": "tied", "diff": 0}]
        self.assertEqual(ss.team_tallies(rows), {})

    def test_league_effects_lists_every_state(self):
        e = ss.league_effects(ss.team_tallies(self.league()))
        self.assertEqual([r["state"] for r in e], list(ss.STATES))


class Clutch(unittest.TestCase):
    def own(self, n_late, g_late, n_rest, g_rest, xg=0.1):
        def mk(i, late, goal):
            return {"kind": "goal" if goal else "shot", "xg": xg, "empty_net": False, "period": 3 if late else 1,
                    "diff": 0, "state": "tied", "strength": "ev", "event_id": i}
        rows = [mk(i, True, i < g_late) for i in range(n_late)] + [mk(100 + i, False, i < g_rest) for i in range(n_rest)]
        return rows

    def test_a_player_who_finishes_the_same_late_has_no_gap(self):
        c = ss.clutch(self.own(50, 5, 500, 50))
        self.assertAlmostEqual(c["expected_goals"], 5.0, places=1)
        self.assertAlmostEqual(c["z"], 0.0, places=1)

    def test_a_hot_late_streak_shows_a_positive_gap(self):
        c = ss.clutch(self.own(50, 12, 500, 50))
        self.assertGreater(c["z"], 2)
        self.assertEqual(c["close_late"]["goals"], 12)

    def test_third_period_blowouts_are_not_close_and_late(self):
        s = {"period": 3, "diff": 3}
        self.assertFalse(ss.is_close_late(s))
        self.assertTrue(ss.is_close_late({"period": 3, "diff": -1}))
        self.assertFalse(ss.is_close_late({"period": 2, "diff": 0}))

    def test_no_comparison_without_goals_to_compare(self):
        self.assertIsNone(ss.clutch(self.own(20, 0, 100, 0))["z"])


if __name__ == "__main__":
    unittest.main()
