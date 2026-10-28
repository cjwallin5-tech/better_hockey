import datetime as dt
import unittest

import predictions as pr


def game(state="FUT", win=0.55, home_goalie=None, away_goalie=None):
    return {"game_id": 1, "state": state, "home": "BOS", "away": "NYR", "home_win": win,
            "goalies": {"home": home_goalie, "away": away_goalie} if home_goalie or away_goalie else None}


def goalie(team, pid, p, confirmed=False):
    return {"team": team, "player_id": pid, "probability": p, "confirmed": confirmed}


class Logging(unittest.TestCase):
    def test_a_game_logs_one_win_row_and_a_row_per_known_goalie(self):
        rows = pr.rows_from_tonight([game(home_goalie=goalie("BOS", 7, 0.7), away_goalie=goalie("NYR", 8, 0.6, True))])
        self.assertEqual([(r["kind"], r["subject"], r["p"]) for r in rows],
                         [("win", "BOS", 0.55), ("goalie", "BOS", 0.7), ("goalie", "NYR", 0.6)])
        self.assertTrue(rows[2]["confirmed"])

    def test_games_already_started_are_not_logged(self):
        self.assertEqual(pr.rows_from_tonight([game(state="LIVE"), game(state="OFF")]), [])

    def test_missing_predictions_are_skipped(self):
        self.assertEqual(pr.rows_from_tonight([game(win=None, home_goalie=goalie("BOS", None, None))]), [])


class Grading(unittest.TestCase):
    def test_win(self):
        self.assertEqual(pr.grade({"kind": "win"}, {"home_score": 3, "away_score": 2}, None), (True, None))
        self.assertEqual(pr.grade({"kind": "win"}, {"home_score": 1, "away_score": 2}, None), (False, None))
        self.assertEqual(pr.grade({"kind": "win"}, {"home_score": None, "away_score": None}, None), (None, None))

    def test_goalie(self):
        self.assertEqual(pr.grade({"kind": "goalie", "pick": 7}, {}, 7), (True, 7))
        self.assertEqual(pr.grade({"kind": "goalie", "pick": 7}, {}, 9), (False, 9))
        self.assertEqual(pr.grade({"kind": "goalie", "pick": 7}, {}, None), (None, None))


class Report(unittest.TestCase):
    def test_only_graded_rows_count(self):
        d = dt.date(2026, 10, 27)
        rows = [{"kind": "win", "game_date": d, "p": 0.6, "outcome": True, "confirmed": False},
                {"kind": "win", "game_date": d, "p": 0.4, "outcome": False, "confirmed": False},
                {"kind": "win", "game_date": d, "p": 0.7, "outcome": None, "confirmed": False},
                {"kind": "goalie", "game_date": d, "p": 0.8, "outcome": True, "confirmed": False},
                {"kind": "goalie", "game_date": d, "p": 0.9, "outcome": False, "confirmed": True}]
        out = pr.report(rows)
        self.assertEqual(out["win"]["games"], 2)
        self.assertAlmostEqual(out["win"]["model"]["brier"], 0.16)
        self.assertEqual(out["goalie"]["games"], 2)
        self.assertEqual(out["goalie"]["top_correct"], 0.5)
        self.assertEqual(out["goalie"]["unconfirmed"], 1)
        self.assertEqual(out["goalie"]["top_correct_unconfirmed"], 1.0)

    def test_empty(self):
        out = pr.report([])
        self.assertEqual(out["win"]["games"], 0)
        self.assertIsNone(out["goalie"]["top_correct"])


if __name__ == "__main__":
    unittest.main()
