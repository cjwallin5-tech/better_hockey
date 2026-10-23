import unittest
from datetime import date

import prospects as pr

LIST = {
    "forwards": [{"id": 1, "firstName": {"default": "Maksim"}, "lastName": {"default": "Berezkin"}, "positionCode": "L",
                  "shootsCatches": "R", "heightInInches": 74, "weightInPounds": 201, "birthDate": "2001-10-12", "birthCountry": "RUS"}],
    "defensemen": [{"id": 2, "firstName": {"default": "Beau"}, "lastName": {"default": "Akey"}, "positionCode": "D"}],
    "goalies": [],
}


class ParseList(unittest.TestCase):
    def test_every_group_is_read_with_its_bio(self):
        out = pr.parse_list(LIST)
        self.assertEqual([p["name"] for p in out], ["Maksim Berezkin", "Beau Akey"])
        self.assertEqual((out[0]["position"], out[0]["birth_country"], out[0]["height_in"]), ("L", "RUS", 74))
        self.assertIsNone(out[1]["birth_date"])

    def test_empty_response(self):
        self.assertEqual(pr.parse_list({}), [])


def row(season, league, games, points=None, game_type=2):
    return {"season_id": season, "game_type": game_type, "league": league, "games": games, "points": points}


class Landing(unittest.TestCase):
    DATA = {"draftDetails": {"year": 2023, "teamAbbrev": "EDM", "round": 2, "pickInRound": 24, "overallPick": 56},
            "seasonTotals": [
                {"season": 20242025, "gameTypeId": 2, "leagueAbbrev": "OHL", "teamName": {"default": "Kitchener"}, "gamesPlayed": 60,
                 "goals": 20, "assists": 40, "points": 60},
                {"season": 20242025, "gameTypeId": 1, "leagueAbbrev": "X", "gamesPlayed": 1},
                {"season": 20252026, "gameTypeId": 3, "leagueAbbrev": "OHL", "gamesPlayed": 5, "points": 4}]}

    def test_draft_and_regular_and_playoff_rows_only(self):
        draft, seasons = pr.parse_landing(self.DATA)
        self.assertEqual(draft, {"year": 2023, "round": 2, "pick": 24, "overall": 56, "team": "EDM"})
        self.assertEqual([(s["season_id"], s["game_type"]) for s in seasons], [(20242025, 2), (20252026, 3)])
        self.assertEqual(seasons[0]["team_name"], "Kitchener")

    def test_undrafted_has_no_draft(self):
        self.assertIsNone(pr.parse_landing({"seasonTotals": []})[0])


class Lines(unittest.TestCase):
    def test_current_line_is_the_league_with_the_most_games(self):
        rows = [row(20262027, "AHL", 4, 1), row(20262027, "ECHL", 9, 5), row(20252026, "AHL", 60, 30), row(20262027, "AHL", 3, 1, game_type=3)]
        self.assertEqual(pr.current_line(rows, 20262027)["league"], "ECHL")
        self.assertIsNone(pr.current_line(rows, 20272028))

    def test_age_counts_birthdays(self):
        self.assertEqual(pr.age_on(date(2005, 2, 11), date(2026, 2, 10)), 20)
        self.assertEqual(pr.age_on(date(2005, 2, 11), date(2026, 2, 11)), 21)
        self.assertIsNone(pr.age_on(None, date(2026, 1, 1)))

    def test_points_per_game(self):
        self.assertAlmostEqual(pr.points_per_game(row(1, "OHL", 40, 60)), 1.5)
        self.assertIsNone(pr.points_per_game(row(1, "OHL", 0, 0)))
        self.assertIsNone(pr.points_per_game(row(1, "OHL", 5, None)))
        self.assertIsNone(pr.points_per_game(None))


if __name__ == "__main__":
    unittest.main()
