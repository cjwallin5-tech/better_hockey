import unittest

import config
import ingest

DEFAULT = [20222023, 20232024]


class ParseBackfillArgs(unittest.TestCase):
    def test_no_arguments_uses_the_default_seasons(self):
        self.assertEqual(ingest.parse_backfill_args([], DEFAULT), (DEFAULT, None))

    def test_the_number_after_limit_is_a_limit_not_a_season(self):
        # this used to select "season 20" and find nothing
        self.assertEqual(ingest.parse_backfill_args(["--limit", "20"], DEFAULT), (DEFAULT, 20))

    def test_seasons_and_limit_together_in_either_order(self):
        self.assertEqual(ingest.parse_backfill_args(["20212022,20222023", "--limit", "5"], DEFAULT), ([20212022, 20222023], 5))
        self.assertEqual(ingest.parse_backfill_args(["--limit", "5", "20212022,20222023"], DEFAULT), ([20212022, 20222023], 5))

    def test_a_single_season(self):
        self.assertEqual(ingest.parse_backfill_args(["20242025"], DEFAULT), ([20242025], None))


def play(event_id, kind, owner, x, y, situation="1551", shooter=8000001, goalie=8000002, period=1, time="10:00"):
    return {"eventId": event_id, "sortOrder": event_id, "typeDescKey": kind, "timeInPeriod": time,
            "periodDescriptor": {"number": period, "periodType": "REG"}, "homeTeamDefendingSide": "left",
            "situationCode": situation,
            "details": {"eventOwnerTeamId": owner, "xCoord": x, "yCoord": y, "shootingPlayerId": shooter,
                        "scoringPlayerId": shooter, "goalieInNetId": goalie, "shotType": "wrist"}}


PBP = {"homeTeam": {"id": 1}, "awayTeam": {"id": 2}, "plays": [
    play(1, "shot-on-goal", 1, 70, 5),
    play(2, "blocked-shot", 1, 60, 0, shooter=8000003),
    play(3, "goal", 1, 80, 0, situation="0551", goalie=None),  # the away goalie is pulled: an empty-net goal
    {"eventId": 4, "sortOrder": 4, "typeDescKey": "faceoff", "timeInPeriod": "10:05",
     "periodDescriptor": {"number": 1, "periodType": "REG"}, "details": {}},
]}


class ShotHistRows(unittest.TestCase):
    def setUp(self):
        self.rows = ingest.shot_hist_rows(555, 20252026, PBP)

    def test_one_row_per_attempt_and_nothing_else(self):
        self.assertEqual([r[1] for r in self.rows], [1, 2, 3])
        self.assertTrue(all(r[0] == 555 and r[2] == 20252026 for r in self.rows))

    def test_fields_are_in_insert_order(self):
        game_id, event_id, season_id, shooter, goalie, kind, strength, xg = self.rows[0]
        self.assertEqual((shooter, goalie, kind, strength), (8000001, 8000002, "shot", "ev"))
        self.assertGreater(xg, 0)

    def test_blocked_shots_and_empty_net_goals_have_no_xg(self):
        self.assertIsNone(self.rows[1][7])
        self.assertEqual(self.rows[2][5], "goal")
        self.assertIsNone(self.rows[2][7])


if __name__ == "__main__":
    unittest.main()
