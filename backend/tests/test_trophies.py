import unittest

import trophies

TEAMS = {8: "MTL", 22: "EDM"}


def row(season, name, player=1, team=8, status="WINNER"):
    return {"seasonId": season, "fullName": name, "playerId": player, "teamId": team, "status": status}


class Key(unittest.TestCase):
    def test_curly_quotes_and_case_do_not_matter(self):
        self.assertEqual(trophies.key("Maurice “Rocket” Richard Trophy"), trophies.key('maurice "rocket" richard trophy'))
        self.assertEqual(trophies.key("Presidents’ Trophy"), "presidentstrophy")

    def test_none_is_empty(self):
        self.assertEqual(trophies.key(None), "")


class Winners(unittest.TestCase):
    def test_finalists_are_left_out_and_newest_season_comes_first(self):
        rows = [row(20182019, "A"), row(20192020, "B", status="FINALIST"), row(20202021, "C", team=22)]
        got = trophies.winners(rows, 2, TEAMS)
        self.assertEqual([w["name"] for w in got], ["C", "A"])
        self.assertEqual(got[0]["team"], "EDM")

    def test_a_shared_award_keeps_every_winner_in_name_order(self):
        rows = [row(20192020, "Tuukka Rask", 2), row(20192020, "Jaroslav Halak", 3)]
        self.assertEqual([w["name"] for w in trophies.winners(rows, 2, TEAMS)], ["Jaroslav Halak", "Tuukka Rask"])

    def test_team_trophies_use_the_team_row_not_the_players(self):
        rows = [row(20182019, "Some Player", 7), row(20182019, "St. Louis Blues", None)]
        got = trophies.winners(rows, trophies.TEAM_CATEGORY, TEAMS)
        self.assertEqual([w["name"] for w in got], ["St. Louis Blues"])
        self.assertIsNone(got[0]["player_id"])

    def test_unknown_team_is_none(self):
        self.assertIsNone(trophies.winners([row(20182019, "A", team=999)], 2, TEAMS)[0]["team"])


class AddStats(unittest.TestCase):
    def test_stats_are_attached_by_player_and_season(self):
        w = [{"season_id": 20212022, "player_id": 5, "name": "A"}, {"season_id": 20202021, "player_id": 5, "name": "A"}]
        lines = {(5, 20212022): {"games_played": 80, "goals": 40, "assists": 60, "points": 100}}
        got = trophies.add_stats(w, lines, ["games_played", "points"])
        self.assertEqual(got[0]["stats"], {"games_played": 80, "points": 100})
        self.assertIsNone(got[1]["stats"])


class Summary(unittest.TestCase):
    INFO = {"id": 8, "name": "Hart", "categoryId": 2, "briefDescription": "Most valuable player"}

    def test_newest_winner_and_first_season(self):
        w = trophies.winners([row(20182019, "A"), row(19981999, "B")], 2, TEAMS)
        s = trophies.summary(self.INFO, w)
        self.assertEqual(s["latest"]["name"], "A")
        self.assertEqual(s["first_season"], 19981999)
        self.assertEqual(s["description"], "Most valuable player")

    def test_a_trophy_with_no_winners_yet(self):
        s = trophies.summary(self.INFO, [])
        self.assertIsNone(s["latest"])
        self.assertIsNone(s["first_season"])

    def test_sections(self):
        self.assertEqual(trophies.group_of(2), "Player awards")
        self.assertEqual(trophies.group_of(1), "Team trophies")
        self.assertEqual(trophies.group_of(5), "Coaches, executives and builders")
        self.assertEqual(trophies.group_of(99), "Other")


if __name__ == "__main__":
    unittest.main()
