import datetime as dt
import unittest

import leagues as lg


class Codes(unittest.TestCase):
    def test_codes_are_readable_and_the_right_length(self):
        for _ in range(50):
            code = lg.new_invite_code()
            self.assertEqual(len(code), lg.CODE_LEN)
            self.assertTrue(set(code) <= set(lg.CODE_ALPHABET))
        self.assertTrue(set("IO01").isdisjoint(lg.CODE_ALPHABET))

    def test_a_pasted_code_is_cleaned(self):
        self.assertEqual(lg.clean_code("  abcd-2345 "), "ABCD2345")
        self.assertEqual(lg.clean_code("ABCD2345"), "ABCD2345")
        self.assertIsNone(lg.clean_code("short"))
        self.assertIsNone(lg.clean_code(None))
        self.assertIsNone(lg.clean_code("ABCD23456"))


class Cleaning(unittest.TestCase):
    def test_names(self):
        self.assertEqual(lg.clean_name("  The   Big  League "), "The Big League")
        self.assertIsNone(lg.clean_name("   "))
        self.assertEqual(lg.clean_name("", "My team"), "My team")
        self.assertEqual(len(lg.clean_name("x" * 200)), lg.NAME_LEN)

    def test_players_keep_valid_rows_without_repeats(self):
        raw = [{"id": 1, "kind": "skater", "name": "A"}, {"id": 1, "kind": "skater", "name": "A again"},
               {"id": "2", "kind": "skater", "name": "B"}, {"id": 3, "kind": "coach", "name": "C"}, {"id": 4, "kind": "goalie"},
               {"id": True, "kind": "skater", "name": "D"}, "junk", {"id": 5, "kind": "goalie", "name": "E", "extra": 1}]
        self.assertEqual(lg.clean_players(raw), [{"id": 1, "kind": "skater", "name": "A"}, {"id": 5, "kind": "goalie", "name": "E"}])
        self.assertEqual(lg.clean_players(None), [])

    def test_players_are_capped(self):
        raw = [{"id": i, "kind": "skater", "name": str(i)} for i in range(lg.MAX_ROSTER + 20)]
        self.assertEqual(len(lg.clean_players(raw)), lg.MAX_ROSTER)

    def test_settings_keep_only_valid_parts(self):
        out = lg.clean_settings({
            "format": "categories", "slots": {"C": 2, "L": 99, "R": -3, "D": "x", "G": 1, "Z": 5},
            "scoring": {"goals": 3, "assists": "2", "wins": 4.5, "": 1, "flag": True},
            "categories": {"skater": ["goals", 7, "x" * 40, "assists"], "goalie": ["wins"], "other": ["z"]}, "junk": 1})
        self.assertEqual(out["format"], "categories")
        self.assertEqual(out["slots"], {"C": 2, "L": 10, "R": 0, "G": 1})
        self.assertEqual(out["scoring"], {"goals": 3.0, "wins": 4.5})
        self.assertEqual(out["categories"], {"skater": ["goals", "assists"], "goalie": ["wins"]})
        self.assertNotIn("junk", out)

    def test_bad_settings_become_empty(self):
        self.assertEqual(lg.clean_settings(None), {})
        self.assertEqual(lg.clean_settings({"format": "weird", "slots": 3, "scoring": [], "categories": "x"}), {})


NOW = dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc)


def team(tid, name, user_id=None, players=()):
    return {"id": tid, "name": name, "user_id": user_id, "players": list(players)}


class Views(unittest.TestCase):
    LEAGUE = {"id": 1, "name": "The League", "owner_id": 10, "teams": 4, "settings": {"format": "points"}, "created_at": NOW}
    A = {"id": 1, "kind": "skater", "name": "A"}
    B = {"id": 2, "kind": "goalie", "name": "B"}
    C = {"id": 3, "kind": "skater", "name": "C"}

    def view(self, viewer=10):
        teams = [team(1, "Owner team", 10), team(2, "Friend", 11), team(3, "Manual", None, [self.C])]
        return lg.league_view(self.LEAGUE, teams, {10: [self.A], 11: [self.B]}, viewer)

    def test_a_user_linked_team_shows_the_owners_synced_roster_and_a_manual_team_its_own(self):
        v = self.view()
        self.assertEqual([t["players"] for t in v["teams"]], [[self.A], [self.B], [self.C]])
        self.assertEqual([t["manual"] for t in v["teams"]], [False, False, True])

    def test_mine_is_marked_for_the_viewer_only(self):
        self.assertEqual([t["mine"] for t in self.view(10)["teams"]], [True, False, False])
        self.assertEqual([t["mine"] for t in self.view(11)["teams"]], [False, True, False])
        self.assertEqual(self.view(11)["is_owner"], False)
        self.assertEqual(self.view(10)["is_owner"], True)

    def test_taken_is_everyone_on_any_team(self):
        self.assertEqual(self.view()["taken"], [1, 2, 3])

    def test_no_email_or_user_id_is_exposed(self):
        v = self.view()
        for t in v["teams"]:
            self.assertEqual(set(t), {"id", "name", "manual", "mine", "players"})
        self.assertEqual(v["owner_team"], "Owner team")

    def test_a_member_who_never_synced_has_an_empty_team(self):
        v = lg.league_view(self.LEAGUE, [team(1, "Owner team", 10)], {}, 10)
        self.assertEqual(v["teams"][0]["players"], [])
        self.assertEqual(v["taken"], [])


if __name__ == "__main__":
    unittest.main()
