import datetime as dt
import unittest

import digest
import tradewatch as tw

GAMES = 84


def skater(pid, points, xpoints, gp=20, flag="hot", z=2.0, enough=True, name=None, team="EDM"):
    return {"player_id": pid, "name": name or f"P{pid}", "team": team, "games_played": gp, "points": points,
            "xpoints_adj": xpoints, "points_flag_adj": flag, "points_z_adj": z, "enough": enough}


def goalie(pid, goals, xga, flag="hot", z=2.0, enough=True):
    return {"player_id": pid, "name": f"G{pid}", "team": "BOS", "goals": goals, "xga": xga, "flag": flag, "z": z, "enough": enough}


class SellHigh(unittest.TestCase):
    def test_only_my_hot_skaters_with_a_real_gap(self):
        rows = [skater(1, 25, 18), skater(2, 25, 18), skater(3, 20, 18), skater(4, 25, 18, flag="cold"), skater(5, 25, 18, enough=False)]
        out = tw.sell_high(rows, [], {1, 3, 4, 5}, GAMES)
        self.assertEqual([a["name"] for a in out], ["P1"])   # 2 is not mine, 3's gap is 2, 4 is cold, 5 is a small sample

    def test_biggest_gap_first_and_capped(self):
        rows = [skater(i, 20 + i, 10) for i in range(1, 7)]
        out = tw.sell_high(rows, [], set(range(1, 7)), GAMES)
        self.assertEqual([a["name"] for a in out], ["P6", "P5", "P4"])

    def test_the_gap_is_points_above_expectation(self):
        self.assertAlmostEqual(tw.sell_high([skater(1, 25, 15.5)], [], {1}, GAMES)[0]["gap"], 9.5)

    def test_hot_goalies_follow_the_skaters(self):
        out = tw.sell_high([skater(1, 25, 15)], [goalie(9, 5, 9.4), goalie(8, 5, 9.4, flag="cold")], {1, 9, 8}, GAMES)
        self.assertEqual([a["kind"] for a in out], ["skater", "goalie"])


class BuyLow(unittest.TestCase):
    def test_cold_good_players_not_on_my_team(self):
        rows = [skater(1, 10, 18, flag="cold", z=-2), skater(2, 10, 18, flag="cold", z=-2), skater(3, 10, 18, flag="hot")]
        out = tw.buy_low(rows, {2}, GAMES)
        self.assertEqual([a["name"] for a in out], ["P1"])

    def test_a_player_who_is_not_good_enough_is_skipped(self):
        # expected 8 points in 20 games is a 34-point pace: below the floor
        self.assertEqual(tw.buy_low([skater(1, 2, 8, flag="cold", z=-2)], set(), GAMES), [])

    def test_a_small_gap_is_skipped(self):
        self.assertEqual(tw.buy_low([skater(1, 16, 18, flag="cold", z=-2)], set(), GAMES), [])

    def test_watchlist_first_then_biggest_gap(self):
        rows = [skater(1, 8, 20, flag="cold", z=-2), skater(2, 12, 20, flag="cold", z=-2), skater(3, 10, 20, flag="cold", z=-2)]
        out = tw.buy_low(rows, set(), GAMES, watched={2})
        self.assertEqual([a["name"] for a in out], ["P2", "P1", "P3"])
        self.assertTrue(out[0]["watched"])


class Lines(unittest.TestCase):
    def test_sell_line(self):
        a = tw.sell_high([skater(1, 25, 15, name="A Hot", z=2.4)], [], {1}, GAMES)[0]
        line = tw.sell_line(a)
        self.assertIn("A Hot (EDM) has 25 points against about 15 expected", line)
        self.assertIn("z +2.4", line)
        self.assertIn("10 more than expected", line)

    def test_buy_line_notes_the_watchlist(self):
        a = tw.buy_low([skater(1, 10, 20, flag="cold", z=-2.2, name="B Cold")], set(), GAMES, watched={1})[0]
        self.assertIn("(on your watchlist)", tw.buy_line(a))
        self.assertIn("z -2.2", tw.buy_line(a))

    def test_goalie_sell_line_talks_about_goals_against(self):
        a = tw.sell_high([], [goalie(9, 5, 9.4)], {9}, GAMES)[0]
        self.assertIn("allowed 5 goals against about 9 expected", tw.sell_line(a))


class EmailSections(unittest.TestCase):
    def day(self, **extra):
        return {"today": dt.date(2026, 12, 3), "roster_size": 1, "playing": [], "idle": [{"name": "x"}], "hot": [], "watch": [], **extra}

    def test_sections_appear_and_alone_are_enough_to_send(self):
        sell = tw.sell_high([skater(1, 25, 15, name="A Hot")], [], {1}, GAMES)
        buy = tw.buy_low([skater(2, 10, 20, flag="cold", name="B Cold")], set(), GAMES)
        out = digest.render(self.day(sell=sell, buy=buy))
        self.assertIsNotNone(out)
        self.assertIn("SELL HIGH", out[1])
        self.assertIn("A Hot (EDM)", out[1])
        self.assertIn("BUY LOW", out[1])
        self.assertIn("B Cold (EDM)", out[1])

    def test_nothing_to_suggest_adds_no_section(self):
        _, body = digest.render(self.day(sell=[], buy=[], luck=[{"name": "c", "kind": "skater", "flag": "cold", "z": -2, "actual": 3, "expected": 7.2}]))
        self.assertNotIn("SELL HIGH", body)
        self.assertNotIn("BUY LOW", body)

    def test_roster_luck_check_keeps_only_the_cold_ones_while_watchlist_keeps_both(self):
        league = {"skaters": [skater(1, 25, 15, name="Hot"), skater(2, 5, 12, flag="cold", z=-2, name="Cold")], "goalies": []}
        players = [{"id": 1}, {"id": 2}]
        self.assertEqual([a["name"] for a in digest.luck_alerts(league, players, hot=False)], ["Cold"])
        self.assertEqual({a["name"] for a in digest.luck_alerts(league, players)}, {"Hot", "Cold"})
        self.assertEqual(digest.luck_alerts(league, [{"id": 99}]), [])


if __name__ == "__main__":
    unittest.main()
