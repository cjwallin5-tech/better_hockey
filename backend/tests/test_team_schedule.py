import unittest
from contextlib import contextmanager
from unittest import mock

from routes import teams

LEAGUE = {"goals_pg": 3.0, "shots_pg": 30.0}
TEAM = {"off_ratio": 1.0, "def_ratio": 1.0}
WIN_GAPS = {"tired": -0.10, "edge": 0.05}


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_args, **_kwargs):
        return mock.Mock(fetchall=lambda: [dict(r) for r in self.rows])


def game(game_id, home, away, state="FUT", **extra):
    return {"game_id": game_id, "game_date": "2026-11-20", "start_time": None, "home": home, "away": away,
            "home_score": None, "away_score": None, "last_period": None, "state": state, "venue": "", **extra}


def schedule(rows, kinds, abbrev="TOR"):
    """team_schedule without the database: fixed rows, equal ratings for every team, and the given rest kinds."""
    @contextmanager
    def connect(*_a, **_k):
        yield FakeConn(rows)
    ratings = [dict(TEAM, team=t) for t in ("TOR", "MTL", "BOS")]
    with mock.patch.object(teams.psycopg, "connect", connect), \
            mock.patch.object(teams.matchups_db, "team_table", return_value=(ratings, LEAGUE)), \
            mock.patch.object(teams, "_rest_context", return_value=(None, kinds)), \
            mock.patch.dict(teams._rest_gaps_cache, {"win": WIN_GAPS}):
        return teams.team_schedule.__wrapped__(abbrev)


class TeamScheduleRest(unittest.TestCase):
    def test_each_upcoming_game_carries_this_teams_rest_kind(self):
        out = schedule([game(1, "TOR", "MTL"), game(2, "BOS", "TOR")], {("TOR", 1): "edge", ("TOR", 2): "tired"})
        self.assertEqual([g["rest"] for g in out["upcoming"]], ["edge", "tired"])

    def test_normal_rest_is_none(self):
        out = schedule([game(1, "TOR", "MTL")], {})
        self.assertIsNone(out["upcoming"][0]["rest"])

    def test_win_chance_is_from_this_teams_side(self):
        # equal teams: home ice puts the home side above 50%, the visiting side below, and the two views mirror each other
        home = schedule([game(1, "TOR", "MTL")], {}, "TOR")["upcoming"][0]["win"]
        away = schedule([game(1, "TOR", "MTL")], {}, "MTL")["upcoming"][0]["win"]
        self.assertGreater(home, 0.5)
        self.assertLess(away, 0.5)
        self.assertAlmostEqual(home + away, 1.0)

    def test_home_team_rest_shifts_the_win_chance(self):
        base = schedule([game(1, "TOR", "MTL")], {})["upcoming"][0]["win"]
        tired = schedule([game(1, "TOR", "MTL")], {("TOR", 1): "tired"})["upcoming"][0]["win"]
        edge = schedule([game(1, "TOR", "MTL")], {("TOR", 1): "edge"})["upcoming"][0]["win"]
        self.assertLess(tired, base)
        self.assertGreater(edge, base)

    def test_visitors_rest_alone_does_not_move_the_odds(self):
        # the model applies the home team's rest only; the badge still shows the visitor's own rest
        base = schedule([game(1, "MTL", "TOR")], {})["upcoming"][0]
        away_tired = schedule([game(1, "MTL", "TOR")], {("TOR", 1): "tired"})["upcoming"][0]
        self.assertEqual(away_tired["win"], base["win"])
        self.assertEqual(away_tired["rest"], "tired")

    def test_only_unplayed_games_get_the_fields_and_finished_ones_get_a_result(self):
        done = game(3, "TOR", "MTL", state="OFF", home_score=4, away_score=2, last_period="REG")
        out = schedule([done, game(4, "TOR", "BOS")], {})
        self.assertNotIn("win", out["results"][0])
        self.assertEqual(out["results"][0]["result"], "W")
        self.assertIn("win", out["upcoming"][0])

    def test_missing_ratings_leave_the_win_chance_empty(self):
        out = schedule([game(1, "TOR", "XXX")], {("TOR", 1): "tired"})
        self.assertIsNone(out["upcoming"][0]["win"])
        self.assertEqual(out["upcoming"][0]["rest"], "tired")


if __name__ == "__main__":
    unittest.main()
