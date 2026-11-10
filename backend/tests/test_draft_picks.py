import unittest

import prospects as pl

PICKS = {"draftYear": 2026, "picks": [
    {"round": 1, "pickInRound": 1, "overallPick": 1, "teamAbbrev": "TOR", "firstName": {"default": "Gavin"},
     "lastName": {"default": "McKenna"}, "positionCode": "LW", "countryCode": "CAN"},
    {"round": 7, "pickInRound": 3, "overallPick": 195, "teamAbbrev": "CHI", "firstName": {"default": "Zachary"},
     "lastName": {"default": "L'Heureux Jr."}, "positionCode": "C", "countryCode": "CAN"},
    {"round": 7, "pickInRound": 4, "overallPick": None, "teamAbbrev": "CHI", "firstName": {"default": "No"}, "lastName": {"default": "Pick"}},
    {"round": 7, "pickInRound": 5, "overallPick": 197, "teamAbbrev": "CHI", "firstName": {"default": ""}, "lastName": {"default": ""}},
    {"round": 2, "pickInRound": 31, "overallPick": 63, "teamAbbrev": "VGK", "firstName": {"default": "Forfeited"}, "lastName": {"default": ""}},
    {"round": 2, "pickInRound": 32, "overallPick": 64, "teamAbbrev": "VGK", "firstName": {"default": "FORFEITED"}, "lastName": {"default": "FORFEITED"}},
]}


class Picks(unittest.TestCase):
    def test_a_pick_list_becomes_one_row_per_named_pick(self):
        rows = pl.parse_picks(PICKS)
        self.assertEqual([r["overall"] for r in rows], [1, 195])
        self.assertEqual(rows[0], {"year": 2026, "overall": 1, "round": 1, "pick": 1, "team": "TOR", "name": "Gavin McKenna",
                                   "position": "LW", "country": "CAN"})

    def test_a_forfeited_pick_is_not_a_player(self):
        self.assertNotIn(63, [r["overall"] for r in pl.parse_picks(PICKS)])
        self.assertNotIn(64, [r["overall"] for r in pl.parse_picks(PICKS)])

    def test_an_empty_or_odd_response_gives_no_rows(self):
        self.assertEqual(pl.parse_picks({}), [])
        self.assertEqual(pl.parse_picks({"draftYear": 2026, "picks": None}), [])


class Search(unittest.TestCase):
    RESULTS = [
        {"playerId": "8486067", "name": "Gavin McKenna"},
        {"playerId": "8484149", "name": "Gavin Brindley"},          # a near miss the search returns anyway
        {"playerId": "8400001", "name": "Gavin McKenna"},           # a second player with the same name
        {"playerId": "8486067", "name": "Gavin McKenna"},           # repeated
        {"playerId": "not-a-number", "name": "Gavin McKenna"},
        {"name": "Gavin McKenna"},
    ]

    def test_only_exact_name_matches_in_order_without_repeats(self):
        self.assertEqual(pl.search_candidates("Gavin McKenna", self.RESULTS), [8486067, 8400001])

    def test_accents_punctuation_and_suffixes_do_not_matter(self):
        res = [{"playerId": "1", "name": "Zachary L'Heureux"}, {"playerId": "2", "name": "Jean-Philippe Côté"}]
        self.assertEqual(pl.search_candidates("Zachary L'Heureux Jr.", res), [1])
        self.assertEqual(pl.search_candidates("Jean Philippe Cote", res), [2])

    def test_a_loose_search_accepts_a_shared_last_name_for_nicknames(self):
        res = [{"playerId": "1", "name": "Tommy Bleyl"}, {"playerId": "2", "name": "Thomas Kapusta"}, {"playerId": "3", "name": "Cy Thomas"}]
        self.assertEqual(pl.search_candidates("Thomas Bleyl", res), [])
        self.assertEqual(pl.search_candidates("Thomas Bleyl", res, loose=True), [1])
        res = [{"playerId": "9", "name": "JP Hurlbert"}, {"playerId": "8", "name": "J.P. Testwuide"}]
        self.assertEqual(pl.search_candidates("Jeffrey (JP) Hurlbert", res, loose=True), [9])

    def test_last_word_ignores_suffixes_accents_and_punctuation(self):
        self.assertEqual(pl.last_word("Zachary L'Heureux Jr."), "lheureux")
        self.assertEqual(pl.last_word("Jean-Philippe Côté"), "cote")
        self.assertEqual(pl.last_word(""), "")
        self.assertEqual(pl.last_word(None), "")

    def test_nothing_found_is_an_empty_list(self):
        self.assertEqual(pl.search_candidates("Nobody Here", self.RESULTS), [])
        self.assertEqual(pl.search_candidates("Gavin McKenna", None), [])


class Confirm(unittest.TestCase):
    def landing(self, year=2026, overall=1):
        return {"playerId": 8486067, "draftDetails": {"year": year, "teamAbbrev": "TOR", "round": 1, "pickInRound": 1, "overallPick": overall}}

    def test_the_year_and_pick_must_both_match(self):
        self.assertTrue(pl.confirms_pick(self.landing(), 2026, 1))
        self.assertFalse(pl.confirms_pick(self.landing(year=2025), 2026, 1))
        self.assertFalse(pl.confirms_pick(self.landing(overall=2), 2026, 1))

    def test_an_undrafted_or_missing_record_never_confirms(self):
        self.assertFalse(pl.confirms_pick({"playerId": 1}, 2026, 1))
        self.assertFalse(pl.confirms_pick({"draftDetails": None}, 2026, 1))
        self.assertFalse(pl.confirms_pick(None, 2026, 1))
        self.assertFalse(pl.confirms_pick(self.landing(), None, 1))
        self.assertFalse(pl.confirms_pick(self.landing(), 2026, None))


class Bio(unittest.TestCase):
    def test_a_landing_record_gives_the_same_keys_as_a_team_list(self):
        landing = {"playerId": 8486052, "firstName": {"default": "Nikita"}, "lastName": {"default": "Klepov"}, "position": "R",
                   "shootsCatches": "R", "birthDate": "2008-06-27", "birthCountry": "RUS", "heightInInches": 72, "weightInPounds": 180,
                   "headshot": "https://assets.nhle.com/mugs/nhl/20262027/ANA/8486052.png"}
        bio = pl.parse_bio(landing)
        listed = pl.parse_list({"forwards": [{"id": 1, "firstName": {"default": "A"}, "lastName": {"default": "B"}}]})[0]
        self.assertEqual(set(bio), set(listed))
        self.assertEqual((bio["player_id"], bio["name"], bio["position"], bio["birth_country"]), (8486052, "Nikita Klepov", "R", "RUS"))


class Status(unittest.TestCase):
    def test_reaching_the_nhl_needs_an_nhl_season_with_a_game(self):
        junior = {"league": "OHL", "games": 60}
        self.assertFalse(pl.reached_nhl([junior]))
        self.assertFalse(pl.reached_nhl([junior, {"league": "NHL", "games": 0}]))
        self.assertFalse(pl.reached_nhl([]))
        self.assertTrue(pl.reached_nhl([junior, {"league": "NHL", "games": 17}]))

    def test_the_team_is_the_nhl_club_in_the_record_else_the_one_that_picked_him(self):
        teams = {"TOR", "ANA", "EDM"}
        pick = {"team": "ANA"}
        self.assertEqual(pl.class_team({"currentTeamAbbrev": "EDM"}, pick, teams), "EDM")      # rights traded
        self.assertEqual(pl.class_team({"currentTeamAbbrev": "OHL"}, pick, teams), "ANA")      # not an NHL club
        self.assertEqual(pl.class_team({}, pick, teams), "ANA")
        self.assertEqual(pl.class_team(None, pick, teams), "ANA")


if __name__ == "__main__":
    unittest.main()
