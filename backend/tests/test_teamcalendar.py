import unittest
from datetime import date, datetime, timedelta, timezone

import teamcalendar as tc

UTC = timezone.utc
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def game(gid, day, home, away, hs=None, as_=None, state="FUT", period=None, start="auto", venue="Rogers Place"):
    d = date(2026, 10, 1) + timedelta(days=day)
    if start == "auto":
        start = datetime(d.year, d.month, d.day, 2, 0, tzinfo=UTC)
    return {"game_id": gid, "game_date": d, "start_time": start, "home": home, "away": away, "home_score": hs, "away_score": as_,
            "last_period": period, "state": state, "venue": venue}


class Entries(unittest.TestCase):
    def test_home_and_away_flip_the_opponent_and_the_scores(self):
        out = tc.build([game(1, 0, "EDM", "CGY", 4, 2, "OFF", "REG"), game(2, 2, "VAN", "EDM", 3, 5, "FINAL", "REG")], "EDM")["games"]
        self.assertEqual([(e["home"], e["opponent"], e["us"], e["them"], e["result"]) for e in out],
                         [(True, "CGY", 4, 2, "W"), (False, "VAN", 5, 3, "W")])

    def test_overtime_and_shootout_losses_are_not_plain_losses(self):
        out = tc.build([game(1, 0, "EDM", "CGY", 2, 3, "OFF", "OT"), game(2, 2, "EDM", "VAN", 2, 3, "OFF", "SO"),
                        game(3, 4, "EDM", "SEA", 1, 2, "OFF", "REG")], "EDM")["games"]
        self.assertEqual([(e["result"], e["period"]) for e in out], [("OTL", "OT"), ("OTL", "SO"), ("L", None)])

    def test_an_overtime_win_has_the_period_too(self):
        e = tc.build([game(1, 0, "EDM", "CGY", 3, 2, "OFF", "OT")], "EDM")["games"][0]
        self.assertEqual((e["result"], e["period"]), ("W", "OT"))

    def test_unplayed_games_have_no_score_or_result(self):
        e = tc.build([game(1, 0, "EDM", "CGY")], "EDM")["games"][0]
        self.assertEqual((e["state"], e["result"], e["us"], e["them"]), ("UPCOMING", None, None, None))

    def test_a_game_in_progress_is_live_and_has_no_result_yet(self):
        e = tc.build([game(1, 0, "EDM", "CGY", 1, 0, "LIVE")], "EDM")["games"][0]
        self.assertEqual((e["state"], e["result"]), ("LIVE", None))

    def test_the_second_night_of_a_back_to_back_is_marked(self):
        out = tc.build([game(1, 0, "EDM", "CGY"), game(2, 1, "VAN", "EDM"), game(3, 3, "EDM", "SEA"), game(4, 5, "EDM", "ANA")], "EDM")["games"]
        self.assertEqual([e["back_to_back"] for e in out], [False, True, False, False])

    def test_summary_counts_the_record_the_split_and_what_is_left(self):
        s = tc.build([game(1, 0, "EDM", "CGY", 4, 2, "OFF", "REG"), game(2, 1, "VAN", "EDM", 3, 2, "OFF", "OT"),
                      game(3, 3, "EDM", "SEA", 1, 2, "OFF", "REG"), game(4, 5, "EDM", "ANA")], "EDM")["summary"]
        self.assertEqual(s, {"games": 4, "played": 3, "remaining": 1, "wins": 1, "losses": 1, "ot_losses": 1, "home": 3, "away": 1, "back_to_backs": 1})


class Ics(unittest.TestCase):
    def ics(self, *games, **kw):
        entries = tc.build(list(games), "EDM")["games"]
        return tc.to_ics("EDM", kw.get("name", "Edmonton Oilers"), "2026-27", entries, NOW)

    def test_a_valid_calendar_wrapper_with_crlf_line_endings(self):
        text = self.ics(game(1, 0, "EDM", "CGY"))
        self.assertTrue(text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n"))
        self.assertNotIn("\n\n", text.replace("\r\n", ""))
        self.assertEqual(text.count("BEGIN:VEVENT"), text.count("END:VEVENT"))

    def test_each_game_is_an_event_in_utc_lasting_three_hours(self):
        text = self.ics(game(7, 0, "EDM", "CGY"))
        self.assertIn("UID:game-7@nhl-stats", text)
        self.assertIn("DTSTART:20261001T020000Z", text)
        self.assertIn("DTEND:20261001T050000Z", text)
        self.assertIn("SUMMARY:EDM vs CGY", text)
        self.assertIn("LOCATION:Rogers Place", text)

    def test_away_games_say_at_and_finished_games_carry_the_result(self):
        text = self.ics(game(1, 0, "CGY", "EDM", 2, 3, "OFF", "SO"))
        self.assertIn("SUMMARY:EDM @ CGY (W 3-2 SO)", text)

    def test_games_without_a_start_time_are_left_out(self):
        self.assertEqual(self.ics(game(1, 0, "EDM", "CGY", start=None)).count("BEGIN:VEVENT"), 0)

    def test_special_characters_are_escaped(self):
        text = self.ics(game(1, 0, "EDM", "CGY", venue="Rexall; Place, Edmonton"), name="A, B; C")
        self.assertIn("LOCATION:Rexall\; Place\\, Edmonton", text)
        self.assertIn("X-WR-CALNAME:A\\, B\; C 2026-27", text)

    def test_long_lines_are_folded_at_75_octets_without_splitting_a_character(self):
        text = self.ics(game(1, 0, "EDM", "CGY", venue="Stadion ééé " + "x" * 120))
        for line in text.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)
        unfolded = text.replace("\r\n ", "")
        self.assertIn("Stadion ééé " + "x" * 120, unfolded)


if __name__ == "__main__":
    unittest.main()
