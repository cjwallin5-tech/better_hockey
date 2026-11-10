import unittest
from unittest import mock

import ingest


class Args(unittest.TestCase):
    def test_nothing_given(self):
        self.assertEqual(ingest.parse_league_args([]), (None, None))

    def test_a_limit(self):
        self.assertEqual(ingest.parse_league_args(["--limit", "5"]), (5, None))

    def test_a_refresh_season(self):
        self.assertEqual(ingest.parse_league_args(["--refresh", "20262027"]), (None, 20262027))

    def test_both_in_either_order(self):
        self.assertEqual(ingest.parse_league_args(["--refresh", "20262027", "--limit", "3"]), (3, 20262027))
        self.assertEqual(ingest.parse_league_args(["--limit", "3", "--refresh", "20262027"]), (3, 20262027))

    def test_the_number_after_limit_is_never_taken_for_a_season(self):
        self.assertEqual(ingest.parse_league_args(["--limit", "20262027"]), (20262027, None))

    def test_bad_values_are_errors(self):
        for bad in (["--refresh"], ["--refresh", "2026"], ["--refresh", "20262028"], ["--refresh", "abcd1234"], ["--limit"],
                    ["--limit", "x"], ["--bogus"], ["20262027"]):
            with self.assertRaises(ValueError, msg=str(bad)):
                ingest.parse_league_args(bad)


class Stale(unittest.TestCase):
    def test_it_asks_about_the_given_season_and_returns_player_ids(self):
        conn = mock.Mock()
        conn.execute.return_value = [(8478402,), (8477492,)]
        self.assertEqual(ingest.stale_league_players(conn, 20262027), [8478402, 8477492])
        sql, params = conn.execute.call_args[0]
        self.assertEqual(params, {"s": 20262027})
        self.assertIn("skater_season", sql)
        self.assertIn("fetched_at <", sql)            # only players fetched before the season's last game day ended
        self.assertIn("max(game_date)", sql)

    def test_no_stale_players_is_an_empty_list(self):
        conn = mock.Mock()
        conn.execute.return_value = []
        self.assertEqual(ingest.stale_league_players(conn, 20252026), [])


if __name__ == "__main__":
    unittest.main()
