import unittest

import ingest
import roles


def game(ev=840, pp=90, share=0.25, ot=0, sh=0):
    return {"ev_sec": ev, "ot_sec": ot, "pp_sec": pp, "sh_sec": sh, "total_sec": ev + pp + sh, "pp_share": share}


def run(base, recent, window=5):
    return roles.role_line([*base, *recent], window)


class Unit(unittest.TestCase):
    def test_cutoffs(self):
        self.assertEqual(roles.unit(0.62), "PP1")
        self.assertEqual(roles.unit(0.45), "PP1")
        self.assertEqual(roles.unit(0.44), "PP2")
        self.assertEqual(roles.unit(0.15), "PP2")
        self.assertIsNone(roles.unit(0.14))
        self.assertIsNone(roles.unit(None))


class Promotions(unittest.TestCase):
    def test_pp2_to_pp1(self):
        line = run([game(share=0.25)] * 4, [game(share=0.6, pp=190)] * 5)
        self.assertEqual((line["unit_base"], line["unit"]), ("PP2", "PP1"))
        self.assertEqual(line["pp_change"], "up")
        self.assertEqual(line["pp_label"], "Promoted to PP1")
        self.assertAlmostEqual(line["pp_share_delta"], 0.35)
        self.assertAlmostEqual(line["pp_delta"], 100)

    def test_off_the_power_play_to_pp2(self):
        line = run([game(share=0.0, pp=0)] * 4, [game(share=0.25)] * 5)
        self.assertEqual(line["pp_change"], "up")
        self.assertIn("PP2", line["pp_label"])

    def test_pp1_to_pp2_and_off(self):
        down = run([game(share=0.6)] * 4, [game(share=0.25)] * 5)
        self.assertEqual((down["pp_change"], down["pp_label"]), ("down", "Dropped to PP2"))
        off = run([game(share=0.6)] * 4, [game(share=0.02, pp=5)] * 5)
        self.assertEqual((off["pp_change"], off["pp_label"]), ("down", "Off the power play"))
        lost = run([game(share=0.25)] * 4, [game(share=0.02, pp=5)] * 5)
        self.assertEqual((lost["pp_change"], lost["pp_label"]), ("down", "Lost power-play time"))

    def test_hovering_at_a_cutoff_is_not_a_move(self):
        # 0.44 -> 0.47 crosses the PP1 line but moved less than MIN_SHARE_CHANGE
        line = run([game(share=0.44)] * 4, [game(share=0.47)] * 5)
        self.assertEqual(line["unit_base"], "PP2")
        self.assertEqual(line["unit"], "PP1")
        self.assertIsNone(line["pp_change"])

    def test_same_unit_is_not_a_move_however_much_the_share_moves(self):
        line = run([game(share=0.5)] * 4, [game(share=0.9)] * 5)
        self.assertIsNone(line["pp_change"])


class EvenStrength(unittest.TestCase):
    def test_more_time(self):
        line = run([game(ev=840)] * 4, [game(ev=960)] * 5)
        self.assertEqual(line["ev_change"], "up")
        self.assertAlmostEqual(line["ev_delta"], 120)

    def test_less_time(self):
        self.assertEqual(run([game(ev=900)] * 4, [game(ev=780)] * 5)["ev_change"], "down")

    def test_small_changes_are_ignored(self):
        self.assertIsNone(run([game(ev=840)] * 4, [game(ev=900)] * 5)["ev_change"])

    def test_overtime_minutes_do_not_count(self):
        # an overtime game adds 3-on-3 minutes to even strength; they come back out
        recent = [game(ev=1000, ot=160)] * 5
        line = run([game(ev=840)] * 4, recent)
        self.assertAlmostEqual(line["ev"], 840)
        self.assertIsNone(line["ev_change"])


class Samples(unittest.TestCase):
    def test_not_enough_games(self):
        self.assertIsNone(roles.role_line([game()] * 7, 5))   # 5 recent + only 2 before
        self.assertIsNone(roles.role_line([], 5))
        self.assertIsNone(roles.role_line([game()] * 9, 0))

    def test_exactly_enough_games(self):
        self.assertIsNotNone(roles.role_line([game()] * 8, 5))

    def test_windows_use_the_players_last_games(self):
        games = [game(ev=600)] * 5 + [game(ev=900)] * 3 + [game(ev=1000)] * 3
        three, six = roles.role_line(games, 3), roles.role_line(games, 6)
        self.assertAlmostEqual(three["ev"], 1000)
        self.assertEqual(three["base_games"], 8)
        self.assertAlmostEqual(six["ev"], 950)

    def test_a_team_with_no_power_play_has_no_share(self):
        games = [game(pp=0, share=None)] * 8
        line = roles.role_line(games, 5)
        self.assertEqual(line["pp_share"], 0.0)
        self.assertIsNone(line["unit"])
        self.assertIsNone(line["pp_change"])


class Direction(unittest.TestCase):
    def line(self, pp=None, ev=None):
        return {"pp_change": pp, "ev_change": ev}

    def test_directions(self):
        self.assertIsNone(roles.direction(self.line()))
        self.assertEqual(roles.direction(self.line(pp="up")), "up")
        self.assertEqual(roles.direction(self.line(ev="down")), "down")
        self.assertEqual(roles.direction(self.line(pp="up", ev="up")), "up")

    def test_a_power_play_move_outranks_even_strength_when_they_disagree(self):
        self.assertEqual(roles.direction(self.line(pp="down", ev="up")), "down")

    def test_even_strength_alone_cannot_disagree_with_itself(self):
        self.assertEqual(roles.direction(self.line(ev="up")), "up")


class ToiRows(unittest.TestCase):
    def test_rows_in_insert_order_with_missing_numbers_as_zero(self):
        data = [{"playerId": 7, "gameId": 2026020001, "gameDate": "2026-10-03", "teamAbbrev": "NJD", "positionCode": "C",
                 "evTimeOnIce": 418, "ppTimeOnIce": 75, "shTimeOnIce": None, "otTimeOnIce": None, "timeOnIce": 493, "shifts": 14}]
        self.assertEqual(ingest.toi_rows(data, 20262027),
                         [(7, 2026020001, 20262027, "2026-10-03", "NJD", "C", 418, 75, 0, 0, 493, 14)])


if __name__ == "__main__":
    unittest.main()
