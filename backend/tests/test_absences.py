import datetime as dt
import unittest

import absences as ab
import digest


def toi(ev=900, pp=0, sh=0, position="C"):
    return {"ev": ev, "pp": pp, "sh": sh, "position": position}


def season(n_games, lineups):
    """{game_id: {player_id: toi}} for games 1..n; lineups(g) gives that game's {player_id: toi}."""
    return {g: lineups(g) for g in range(1, n_games + 1)}, list(range(1, n_games + 1))


class Basics(unittest.TestCase):
    def test_groups_and_power_play_roles(self):
        self.assertEqual(ab.group("D"), "D")
        self.assertEqual([ab.group(p) for p in ("C", "L", "R")], ["F", "F", "F"])
        self.assertEqual([ab.role(s) for s in (150, 100, 60, 30, 10, 0)], ["PP1", "PP1", "PP2", "PP2", "none", "none"])

    def test_the_average_gain_follows_the_absent_players_role_and_stays_in_the_group(self):
        top = {"pp": 150}
        ev, pp = ab.expected_change("D", top, "D", {"pp": 5})
        self.assertGreater(ev, 30)                              # a top-unit defenseman out: the others gain a lot at even strength
        self.assertEqual(ab.expected_change("D", top, "F", {"pp": 0}), (0.0, 0.0))     # nothing across groups
        ev_none, _ = ab.expected_change("F", {"pp": 0}, "F", {"pp": 0})
        self.assertLess(abs(ev_none), 20)                       # a no-power-play forward out: no real gain
        _, pp_up = ab.expected_change("F", {"pp": 150}, "F", {"pp": 50})
        self.assertGreater(pp_up, 10)                           # the second unit moves up


class Detection(unittest.TestCase):
    def games(self, missing_from):
        """Players 1-12 play every game, except player 1 who misses games from `missing_from` on; 15 games."""
        def lineup(g):
            d = {p: toi(900 + p, pp=40 if p < 6 else 0) for p in range(2, 13)}
            if g < missing_from:
                d[1] = toi(1300, pp=150)
            return d
        return season(15, lineup)

    def test_a_regular_who_missed_the_latest_games_is_found(self):
        gm, order = self.games(missing_from=13)
        found = ab.current_absences(gm, order)
        self.assertEqual([(a["player"], a["games_out"]) for a in found], [(1, 3)])
        self.assertEqual(found[0]["absent_games"], [13, 14, 15])

    def test_a_player_who_is_back_is_not_out(self):
        gm, order = self.games(missing_from=99)
        self.assertEqual(ab.current_absences(gm, order), [])

    def test_someone_who_barely_played_is_not_a_regular(self):
        gm, order = season(15, lambda g: {**{p: toi() for p in range(2, 13)}, **({1: toi()} if g in (3, 9) else {})})
        self.assertEqual(ab.current_absences(gm, order), [])

    def test_a_long_gone_player_is_not_counted(self):
        gm, order = season(60, lambda g: {**{p: toi() for p in range(2, 13)}, **({1: toi()} if g < 10 else {})})
        self.assertEqual(ab.current_absences(gm, order), [])

    def test_the_baseline_and_the_change_while_out(self):
        gm, order = self.games(missing_from=13)
        found = ab.current_absences(gm, order)[0]
        # teammate 7 gets 20 minutes while player 1 is out, against 900 + 7 seconds before
        for g in (13, 14, 15):
            gm[g][7] = toi(1200)
        base = ab.baseline(gm, found["base_games"], 1)
        self.assertAlmostEqual(base["total"], 1450)
        eff = ab.effect(gm, found, 7)
        self.assertEqual(eff["games"], 3)
        self.assertAlmostEqual(eff["change"]["ev"], 1200 - 907)
        self.assertIsNone(ab.effect(gm, found, 99))              # never played: nothing to compare

    def test_a_teammate_with_too_few_games_has_no_baseline(self):
        gm, order = season(15, lambda g: {p: toi() for p in range(2, 13)} | ({99: toi()} if g == 14 else {}))
        self.assertIsNone(ab.baseline(gm, order[-10:], 99))


class Email(unittest.TestCase):
    def absent(self, seen_games=3):
        return [{"player_id": 1, "name": "Star Center", "team": "AAA", "games_out": 3, "role": "PP1",
                 "teammates": [{"player_id": 7, "name": "Next Man", "expected": {"ev": 16, "pp": 14, "total": 30},
                                "seen": {"games": seen_games, "ev": 80, "pp": 20, "total": 100}},
                               {"player_id": 8, "name": "Not On Roster", "expected": {"ev": 16, "pp": 14, "total": 30},
                                "seen": {"games": 3, "ev": 90, "pp": 0, "total": 90}},
                               {"player_id": 9, "name": "Small Gain", "expected": {"ev": 5, "pp": 0, "total": 5},
                                "seen": {"games": 3, "ev": 5, "pp": 0, "total": 5}}]}]

    def test_only_roster_players_with_a_real_gain_get_a_line(self):
        lines = digest.teammate_lines(self.absent(), {7: {}, 9: {}})
        self.assertEqual([e["name"] for e in lines], ["Next Man"])

    def test_the_line_gives_what_happened_and_what_is_usual(self):
        text = digest.absent_line(digest.teammate_lines(self.absent(), {7: {}})[0])
        self.assertIn("Star Center (AAA, PP1 player) has missed 3 games", text)
        self.assertIn("+1:40 a game more since", text)
        self.assertIn("usually gains about +0:30", text)

    def test_with_one_game_seen_it_is_the_average_that_counts(self):
        line = digest.teammate_lines(self.absent(seen_games=1), {7: {}})[0]
        text = digest.absent_line(line)
        self.assertIn("only been 3 games", text)

    def test_the_section_appears_in_the_email_and_is_enough_to_send_one(self):
        d = {"today": dt.date(2026, 12, 3), "roster_size": 1, "playing": [], "idle": [{"name": "X"}], "hot": [], "watch": [],
             "absent": digest.teammate_lines(self.absent(), {7: {}})}
        subject, body = digest.render(d)
        self.assertIn("TEAMMATE OUT", body)
        self.assertIn("Next Man", body)

    def test_formatting_minutes_and_seconds(self):
        self.assertEqual(digest.mmss(65), "+1:05")
        self.assertEqual(digest.mmss(-33), "-0:33")
        self.assertEqual(digest.mmss(0), "+0:00")


if __name__ == "__main__":
    unittest.main()
