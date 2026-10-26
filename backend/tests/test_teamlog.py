import datetime as dt
import unittest

import teamlog as tl


def game(gid, home, away, hs, as_, period="REG", day=1):
    return {"game_id": gid, "game_date": dt.date(2026, 10, day), "home": home, "away": away, "home_score": hs, "away_score": as_, "last_period": period}


def shots(xgf, xga, cf=50, ca=50, sf=30, sa=30, pp_xgf=0.5, pk_xga=0.4):
    return {"xgf": xgf, "xga": xga, "cf": cf, "ca": ca, "sf": sf, "sa": sa, "pp_xgf": pp_xgf, "pk_xga": pk_xga}


class Rows(unittest.TestCase):
    def test_results(self):
        self.assertEqual(tl.result(3, 2, "REG"), "W")
        self.assertEqual(tl.result(3, 2, "SO"), "W")
        self.assertEqual(tl.result(2, 3, "REG"), "L")
        self.assertEqual(tl.result(2, 3, "OT"), "OTL")

    def test_share(self):
        self.assertAlmostEqual(tl.share(3, 1), 0.75)
        self.assertIsNone(tl.share(0, 0))
        self.assertIsNone(tl.share(None, 2))

    def test_home_and_road_games_read_from_the_teams_side(self):
        home = tl.game_row(game(1, "EDM", "DET", 4, 1), "EDM", shots(3.0, 1.0))
        road = tl.game_row(game(2, "DET", "EDM", 4, 1, "OT"), "EDM", shots(1.0, 3.0))
        self.assertEqual((home["opponent"], home["home_game"], home["gf"], home["ga"], home["result"]), ("DET", True, 4, 1, "W"))
        self.assertEqual((road["opponent"], road["home_game"], road["gf"], road["ga"], road["result"]), ("DET", False, 1, 4, "OTL"))
        self.assertAlmostEqual(home["xg_share"], 0.75)

    def test_a_game_without_shots_has_no_shares(self):
        r = tl.game_row(game(1, "EDM", "DET", 2, 1), "EDM", None)
        self.assertFalse(r["has_shots"])
        self.assertIsNone(r["xg_share"])
        self.assertEqual(r["result"], "W")


class Trends(unittest.TestCase):
    def rows(self, specs):
        return [tl.game_row(game(i, "EDM", "DET", gf, ga, day=i + 1), "EDM", s) for i, (gf, ga, s) in enumerate(specs)]

    def test_rolling_starts_at_the_window_and_uses_the_last_games(self):
        rows = self.rows([(1, 0, shots(2, 1))] * 4 + [(0, 3, shots(1, 2))] * 2)
        out = tl.rolling(rows, 3)
        self.assertEqual([r["n"] for r in out], [3, 4, 5, 6])
        self.assertAlmostEqual(out[0]["xg_share"], 2 / 3)
        self.assertAlmostEqual(out[-1]["xg_share"], 4 / 9)     # last three games: 1 xG-for-game wins, 2 losses
        self.assertAlmostEqual(out[-1]["goal_share"], 1 / 7)

    def test_rolling_leaves_out_games_without_shots_on_both_sides(self):
        rows = self.rows([(2, 1, shots(2, 1)), (5, 0, None), (1, 0, shots(2, 1))])
        out = tl.rolling(rows, 3)[0]
        self.assertAlmostEqual(out["xg_share"], 4 / 6)
        self.assertAlmostEqual(out["goal_share"], 3 / 4)   # the 5-0 game has no xG, so it is left out of the goals too

    def test_summary_counts_the_record_and_judges_results_against_the_play(self):
        # winning every game by a goal while being outplayed on chances
        rows = self.rows([(2, 1, shots(1.0, 2.0))] * 6)
        s = tl.summary(rows)
        self.assertEqual((s["wins"], s["losses"], s["ot_losses"], s["points"]), (6, 0, 0, 12))
        self.assertAlmostEqual(s["xg_share"], 1 / 3)
        self.assertAlmostEqual(s["goal_share"], 2 / 3)
        self.assertEqual(s["verdict"], "ahead")

    def test_summary_behind_and_in_line_and_too_few_games(self):
        self.assertEqual(tl.summary(self.rows([(1, 2, shots(2.0, 1.0))] * 6))["verdict"], "behind")
        self.assertEqual(tl.summary(self.rows([(2, 2, shots(2.0, 2.0))] * 6))["verdict"], "in line")
        self.assertIsNone(tl.summary(self.rows([(2, 1, shots(1.0, 2.0))] * 3))["verdict"])

    def test_summary_shares_only_use_games_that_have_shots(self):
        rows = self.rows([(5, 0, None)] + [(1, 1, shots(1.0, 1.0))] * 5)
        s = tl.summary(rows)
        self.assertEqual(s["shot_games"], 5)
        self.assertAlmostEqual(s["goal_share"], 0.5)   # the 5-0 game has no xG, so it is left out of both sides
        self.assertEqual(s["verdict"], "in line")
        self.assertEqual(s["games"], 6)


class PlayerForm(unittest.TestCase):
    def test_hot_cold_and_small_samples(self):
        self.assertEqual(tl.player_form({"recent_games": 5, "point_pace": 60, "recent_pace": 90}), "hot")
        self.assertEqual(tl.player_form({"recent_games": 5, "point_pace": 60, "recent_pace": 30}), "cold")
        self.assertIsNone(tl.player_form({"recent_games": 5, "point_pace": 60, "recent_pace": 62}))
        self.assertIsNone(tl.player_form({"recent_games": 2, "point_pace": 60, "recent_pace": 120}))
        self.assertIsNone(tl.player_form({"recent_games": 5, "point_pace": 0, "recent_pace": 10}))


if __name__ == "__main__":
    unittest.main()
