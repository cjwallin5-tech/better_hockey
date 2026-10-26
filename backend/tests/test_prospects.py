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


from datetime import datetime, timezone, timedelta

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def pline(games=20, points=24, prev_games=18, prev_points=22, days_ago=0, league="OHL", **kw):
    return {"season_id": 20262027, "game_type": 2, "league": league, "games": games, "goals": 10, "assists": None if points is None else points - 10,
            "points": points, "wins": None, "save_pct": None, "gaa": None, "prev_games": prev_games, "prev_points": prev_points,
            "changed_at": NOW - timedelta(days=days_ago) if days_ago is not None else None, **kw}


class RecentChange(unittest.TestCase):
    def test_games_and_points_since_the_last_move(self):
        self.assertEqual(pr.recent_change(pline(), NOW), {"games": 2, "points": 2, "days_ago": 0})

    def test_a_stale_or_missing_change_is_nothing(self):
        self.assertIsNone(pr.recent_change(pline(days_ago=5), NOW))
        self.assertIsNone(pr.recent_change(pline(days_ago=None), NOW))
        self.assertIsNone(pr.recent_change(pline(prev_games=None), NOW))
        self.assertIsNone(pr.recent_change(pline(games=18, prev_games=18), NOW))
        self.assertIsNone(pr.recent_change(None, NOW))

    def test_a_goalie_or_unscored_row_has_no_point_change(self):
        self.assertIsNone(pr.recent_change(pline(points=None), NOW)["points"])


PROSPECT = {"name": "A Prospect", "team": "EDM", "position": "C"}


class Alert(unittest.TestCase):
    def test_prior_rate_needs_the_same_league_and_enough_games(self):
        seasons = [{"season_id": 20252026, "game_type": 2, "league": "OHL", "games": 60, "points": 45},
                   {"season_id": 20252026, "game_type": 2, "league": "AHL", "games": 5, "points": 9}]
        self.assertAlmostEqual(pr.prior_rate(seasons, 20262027, "OHL"), 0.75)
        self.assertIsNone(pr.prior_rate(seasons, 20262027, "AHL"))     # too few games
        self.assertIsNone(pr.prior_rate(seasons, 20262027, "WHL"))     # a different league

    def test_a_skater_line_with_a_recent_change_and_a_comparison(self):
        seasons = [{"season_id": 20252026, "game_type": 2, "league": "OHL", "games": 60, "points": 30}]
        a = pr.alert(PROSPECT, pline(), seasons, NOW, 20262027)
        text = pr.alert_line(a)
        self.assertIn("A Prospect (EDM prospect, C): 10-14-24 in 20 games in the OHL (1.20 points a game).", text)
        self.assertIn("Lately: 2 games, 2 points since the last update.", text)
        self.assertIn("Up from 0.50 a game last season.", text)

    def test_a_small_change_in_rate_is_not_mentioned(self):
        seasons = [{"season_id": 20252026, "game_type": 2, "league": "OHL", "games": 60, "points": 70}]   # 1.17 vs 1.20
        self.assertNotIn("last season", pr.alert_line(pr.alert(PROSPECT, pline(), seasons, NOW, 20262027)))

    def test_no_games_yet(self):
        self.assertIn("no games on record this season yet", pr.alert_line(pr.alert(PROSPECT, None, [], NOW, 20262027)))

    def test_goalies_get_wins_and_save_percentage(self):
        g = {"name": "G Prospect", "team": "BOS", "position": "G"}
        line = pline(games=12, points=None, wins=7, save_pct=0.917, gaa=2.4, prev_games=10, prev_points=None)
        text = pr.alert_line(pr.alert(g, line, [], NOW, 20262027))
        self.assertIn("12 games in the OHL, 7 wins, 0.917 save percentage.", text)
        self.assertIn("Lately: 2 games since the last update.", text)

    def test_days_ago_wording(self):
        a = pr.alert(PROSPECT, pline(days_ago=2), [], NOW, 20262027)
        self.assertIn("over the last 3 days", pr.alert_line(a))

    def test_called_up(self):
        self.assertEqual(pr.called_up_line("A Prospect", "EDM", 4, 3),
                         "A Prospect has reached the NHL with EDM: 4 NHL games, 3 points so far. He is now followed like any other player.")
        self.assertIn("1 NHL game, 1 point so far", pr.called_up_line("B", "EDM", 1, 1))
