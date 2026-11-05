import unittest

import teamstreaks as ts


def games(seq):
    """'WWLO' -> results oldest first: W win 3-1, L loss 1-3, O overtime loss 2-3."""
    table = {"W": ("W", 3, 1), "L": ("L", 1, 3), "O": ("OTL", 2, 3)}
    return [{"result": table[c][0], "gf": table[c][1], "ga": table[c][2], "opponent": "CGY"} for c in seq]


class Analyze(unittest.TestCase):
    def test_no_games_nothing_to_say(self):
        self.assertEqual(ts.analyze([]), {"current": None, "ended": None})

    def test_a_short_streak_is_not_mentioned(self):
        self.assertIsNone(ts.analyze(games("LWWW"))["current"])

    def test_a_running_win_streak_counts_goals(self):
        cur = ts.analyze(games("LLWWWWW"))["current"]
        self.assertEqual((cur["kind"], cur["length"], cur["gf"], cur["ga"]), ("win", 5, 15, 5))

    def test_overtime_losses_extend_a_losing_streak_and_are_counted(self):
        cur = ts.analyze(games("WLLOL"))["current"]
        self.assertEqual((cur["kind"], cur["length"], cur["otl"]), ("losing", 4, 1))

    def test_a_long_streak_just_ended_is_reported_with_the_game_that_ended_it(self):
        info = ts.analyze(games("LWWWWWL"))
        self.assertIsNone(info["current"])
        self.assertEqual((info["ended"]["kind"], info["ended"]["length"]), ("win", 5))

    def test_a_losing_streak_ended_by_a_win(self):
        info = ts.analyze(games("WLLLLLW"))
        self.assertEqual((info["ended"]["kind"], info["ended"]["length"]), ("losing", 5))

    def test_a_streak_under_the_ended_minimum_is_not_news(self):
        self.assertIsNone(ts.analyze(games("WLLLLW"))["ended"])

    def test_a_streak_that_ended_earlier_is_not_reported_again(self):
        # the win streak ended two games ago; the latest game is a second loss
        self.assertIsNone(ts.analyze(games("WWWWWLL"))["ended"])


class Lines(unittest.TestCase):
    def test_win_streak_line(self):
        out = ts.lines("Edmonton Oilers", ts.analyze(games("LWWWW")))
        self.assertEqual(out, ["Edmonton Oilers have won 4 straight, outscoring opponents 12-4."])

    def test_losing_streak_line_notes_overtime_losses(self):
        out = ts.lines("San Jose Sharks", ts.analyze(games("WLLOL")))
        self.assertEqual(out, ["San Jose Sharks have lost 4 straight (1 in overtime or a shootout), being outscored 12-5."])

    def test_ended_streak_lines_name_the_opponent_and_score(self):
        self.assertEqual(ts.lines("EDM", ts.analyze(games("WWWWWL"))),
                         ["EDM's 5-game win streak ended with a loss to CGY, 3-1."])
        self.assertEqual(ts.lines("EDM", ts.analyze(games("WWWWWO"))),
                         ["EDM's 5-game win streak ended with an overtime or shootout loss to CGY, 3-2."])
        self.assertEqual(ts.lines("SJS", ts.analyze(games("LLLLLW"))),
                         ["SJS's 5-game losing streak ended with a win over CGY, 3-1."])

    def test_nothing_to_say_is_an_empty_list(self):
        self.assertEqual(ts.lines("EDM", ts.analyze(games("WLWLW"))), [])


if __name__ == "__main__":
    unittest.main()
