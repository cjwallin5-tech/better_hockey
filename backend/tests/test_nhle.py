import unittest
from datetime import date

import nhle


LANDING = {
    "birthDate": "2004-01-13", "position": "C",
    "seasonTotals": [
        {"season": 20212022, "gameTypeId": 2, "leagueAbbrev": "OHL", "teamName": {"default": "Windsor"}, "gamesPlayed": 60, "goals": 30, "assists": 45, "points": 75},
        {"season": 20212022, "gameTypeId": 3, "leagueAbbrev": "OHL", "teamName": {"default": "Windsor"}, "gamesPlayed": 10, "goals": 5, "assists": 6, "points": 11},
        {"season": 20222023, "gameTypeId": 1, "leagueAbbrev": "NHL", "teamName": {"default": "Edmonton"}, "gamesPlayed": 4, "goals": 1, "assists": 0, "points": 1},
        {"season": 20222023, "gameTypeId": 2, "leagueAbbrev": "NHL", "teamName": {"default": "Edmonton Oilers"}, "gamesPlayed": 70, "goals": 20, "assists": 30, "points": 50},
    ],
}

FACTORS = {"OHL": {"factor": 0.30, "lo": 0.25, "hi": 0.35, "pairs": 60}, "AHL": {"factor": 0.40, "lo": 0.35, "hi": 0.45, "pairs": 200}}


class LandingRows(unittest.TestCase):
    def test_birth_date_position_and_the_regular_season_and_playoff_rows(self):
        birth, position, seasons = nhle.landing_rows(LANDING)
        self.assertEqual((birth, position), ("2004-01-13", "C"))
        self.assertEqual(len(seasons), 3)               # the preseason row (game type 1) is left out
        self.assertEqual({s["game_type"] for s in seasons}, {2, 3})

    def test_a_season_row_carries_what_the_factors_need(self):
        _, _, seasons = nhle.landing_rows(LANDING)
        junior = next(s for s in seasons if s["league"] == "OHL" and s["game_type"] == 2)
        self.assertEqual((junior["season_id"], junior["games"], junior["points"], junior["team_name"]), (20212022, 60, 75, "Windsor"))

    def test_a_missing_season_list_gives_no_rows(self):
        self.assertEqual(nhle.landing_rows({"position": "G"}), (None, "G", []))


class NhleLine(unittest.TestCase):
    def line(self, **kw):
        return {"league": "OHL", "games": 50, "points": 75, **kw}

    def test_points_per_game_times_the_factor_over_a_full_season(self):
        out = nhle.nhle_line(self.line(), FACTORS, 84)
        self.assertAlmostEqual(out["points"], 75 / 50 * 84 * 0.30)
        self.assertAlmostEqual(out["low"], 75 / 50 * 84 * 0.25)
        self.assertAlmostEqual(out["high"], 75 / 50 * 84 * 0.35)
        self.assertEqual(out["pairs"], 60)

    def test_a_league_without_a_factor_gives_nothing(self):
        self.assertIsNone(nhle.nhle_line(self.line(league="Czechia"), FACTORS, 84))

    def test_a_season_too_short_or_without_points_gives_nothing(self):
        self.assertIsNone(nhle.nhle_line(self.line(games=nhle.MIN_GAMES_SHOWN - 1), FACTORS, 84))
        self.assertIsNone(nhle.nhle_line(self.line(points=None), FACTORS, 84))
        self.assertIsNone(nhle.nhle_line(None, FACTORS, 84))

    def test_a_zero_point_season_is_zero_not_missing(self):
        self.assertEqual(nhle.nhle_line(self.line(points=0), FACTORS, 84)["points"], 0)


class Age(unittest.TestCase):
    def test_buckets(self):
        self.assertEqual(nhle.age_bucket(18.4), "under 20")
        self.assertEqual(nhle.age_bucket(20.0), "20")
        self.assertEqual(nhle.age_bucket(21.99), "21")
        self.assertEqual(nhle.age_bucket(22.5), "22")
        self.assertEqual(nhle.age_bucket(27), "23 and over")

    def test_age_is_taken_on_september_15_of_the_seasons_first_year(self):
        self.assertAlmostEqual(nhle.age_on_season(20252026, "2005-09-15"), 20.0, places=1)
        self.assertAlmostEqual(nhle.age_on_season(20252026, date(2007, 3, 15)), 18.5, places=1)
        self.assertIsNone(nhle.age_on_season(20252026, None))

    def test_the_age_multiplier_scales_points_and_range(self):
        line = {"league": "OHL", "games": 50, "points": 75}
        plain = nhle.nhle_line(line, FACTORS, 84)
        young = nhle.nhle_line(line, FACTORS, 84, age=18.5, age_mult={"under 20": 1.10, "23 and over": 0.87})
        old = nhle.nhle_line(line, FACTORS, 84, age=25, age_mult={"under 20": 1.10, "23 and over": 0.87})
        self.assertAlmostEqual(young["points"], plain["points"] * 1.10)
        self.assertAlmostEqual(young["high"], plain["high"] * 1.10)
        self.assertAlmostEqual(old["points"], plain["points"] * 0.87)
        self.assertEqual(plain["age_mult"], 1.0)

    def test_an_age_without_a_multiplier_table_changes_nothing(self):
        line = {"league": "OHL", "games": 50, "points": 75}
        self.assertEqual(nhle.nhle_line(line, FACTORS, 84, age=19)["points"], nhle.nhle_line(line, FACTORS, 84)["points"])


class ProspectNhle(unittest.TestCase):
    import config as _config
    NOW, LAST, OLD = _config.SEASON_ID, _config.SEASON_ID - 10001, _config.SEASON_ID - 20002

    def season(self, sid, games, points, league="OHL"):
        return {"season_id": sid, "game_type": 2, "league": league, "team_name": "Club", "games": games, "points": points}

    def run_it(self, seasons, position="C"):
        import api
        return api._prospect_nhle({"position": position, "birth_date": date(2006, 5, 1)}, seasons, FACTORS, {})

    def test_this_season_is_used_once_it_has_enough_games(self):
        out = self.run_it([self.season(self.NOW, 25, 30), self.season(self.LAST, 60, 90)])
        self.assertEqual((out["season_id"], out["earlier"]), (self.NOW, False))

    def test_a_short_season_falls_back_to_last_season_and_says_so(self):
        out = self.run_it([self.season(self.NOW, 8, 12), self.season(self.LAST, 60, 90)])
        self.assertEqual((out["season_id"], out["earlier"]), (self.LAST, True))

    def test_nothing_older_than_last_season_is_used(self):
        self.assertIsNone(self.run_it([self.season(self.NOW, 8, 12), self.season(self.OLD, 60, 90)]))

    def test_someone_already_in_the_nhl_gets_none(self):
        self.assertIsNone(self.run_it([self.season(self.NOW, 30, 20, league="NHL"), self.season(self.LAST, 60, 90)]))

    def test_goalies_get_none(self):
        self.assertIsNone(self.run_it([self.season(self.NOW, 25, 0)], position="G"))


if __name__ == "__main__":
    unittest.main()
