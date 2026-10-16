import re
import unittest
from datetime import datetime, timedelta, timezone

import api
import edge
import ingest

DETAIL = {
    "topShotSpeed": {"imperial": 77.81, "percentile": 0.3958, "overlay": {"gameDate": "2026-10-10"}},
    "skatingSpeed": {"speedMax": {"imperial": 24.013, "percentile": 0.9977, "overlay": {"gameDate": "2026-10-03"}}},
    "totalDistanceSkated": {"imperial": 24.7741, "percentile": 0.9886},
    "distanceMaxGame": {"imperial": 4.6022, "percentile": 0.9954},
    "sogSummary": [{"locationCode": "all", "shots": 14, "goals": 4}, {"locationCode": "high", "shots": 5, "goals": 1}],
    "zoneTimeDetails": {"offensiveZonePctg": 0.4946, "offensiveZonePercentile": 0.9795, "offensiveZoneEvPctg": 0.4809,
                        "neutralZonePctg": 0.1694, "defensiveZonePctg": 0.3361, "defensiveZonePercentile": 0.9565},
}
SKATING = {
    "topSkatingSpeeds": [{"gameDate": "2025-10-08", "gameCenterLink": "/gamecenter/edm-vs-cbj/2025/10/08/2025020006",
                          "skatingSpeed": {"imperial": 24.6119}}],
    "skatingSpeedDetails": {"maxSkatingSpeed": {"imperial": 24.6119, "percentile": 0.9967},
                            "burstsOver22": {"value": 151, "percentile": 1.0}, "bursts20To22": {"value": 530},
                            "bursts18To20": {"value": 922}},
}
SHOT = {
    "hardestShots": [{"gameDate": "2025-11-13", "gameCenterLink": "/gamecenter/edm-vs-cbj/2025/11/13/2025020274",
                      "shotSpeed": {"imperial": 82.05}}],
    "shotSpeedDetails": {"topShotSpeed": {"imperial": 82.05, "percentile": 0.3098},
                         "avgShotSpeed": {"imperial": 48.3919, "percentile": 0.2574},
                         "shotAttemptsOver100": {"value": 0}, "shotAttempts90To100": {"value": 1},
                         "shotAttempts80To90": {"value": 5}, "shotAttempts70To80": {"value": 56}},
}
GOALIE = {
    "stats": {"goalsAgainstAvg": {"value": 3.33, "percentile": 0.1017}, "gamesAbove900": {"value": 0.579, "percentile": 0.7288},
              "goalDifferentialPer60": {"value": -0.4}, "goalSupportAvg": {"value": 2.9}, "pointPctg": {"value": 0.47}},
    "shotLocationSummary": [
        {"locationCode": "all", "savePctg": 0.899},
        {"locationCode": "high", "savePctg": 0.812, "savePctgPercentile": 0.5254, "saves": 255, "goalsAgainst": 59},
        {"locationCode": "mid", "savePctg": 0.882, "savePctgPercentile": 0.4576, "saves": 345, "goalsAgainst": 46},
        {"locationCode": "long", "savePctg": 0.98, "savePctgPercentile": 0.8644, "saves": 244, "goalsAgainst": 5}],
}


class ParseSkater(unittest.TestCase):
    def test_every_column_and_nothing_else(self):
        for args in ((DETAIL, SKATING, SHOT), (DETAIL, None, None), (None, None, None)):
            self.assertEqual(set(edge.parse_skater(*args)), {c for c, _ in edge.SKATER_COLUMNS})

    def test_all_three_responses(self):
        r = edge.parse_skater(DETAIL, SKATING, SHOT)
        self.assertEqual((r["top_shot_mph"], r["top_shot_pctile"], r["top_shot_date"]), (82.05, 0.3098, "2025-11-13"))
        self.assertEqual(r["top_shot_game_id"], 2025020274)
        self.assertEqual((r["top_speed_mph"], r["top_speed_date"], r["top_speed_game_id"]), (24.6119, "2025-10-08", 2025020006))
        self.assertEqual((r["bursts_22_plus"], r["bursts_20_22"], r["bursts_18_20"]), (151, 530, 922))
        self.assertEqual((r["avg_shot_mph"], r["shots_90_100"], r["shots_70_80"]), (48.3919, 1, 56))
        self.assertEqual((r["distance_miles"], r["distance_max_game_miles"]), (24.7741, 4.6022))
        self.assertEqual((r["oz_pct"], r["oz_ev_pct"], r["nz_pct"], r["dz_pct"]), (0.4946, 0.4809, 0.1694, 0.3361))
        self.assertEqual((r["sog"], r["sog_goals"], r["hd_sog"], r["hd_goals"]), (14, 4, 5, 1))

    def test_summary_alone_still_gives_the_core_stats(self):
        r = edge.parse_skater(DETAIL, None, None)
        self.assertEqual((r["top_shot_mph"], r["top_shot_date"]), (77.81, "2026-10-10"))
        self.assertEqual((r["top_speed_mph"], r["top_speed_date"]), (24.013, "2026-10-03"))
        self.assertIsNone(r["bursts_22_plus"])
        self.assertIsNone(r["avg_shot_mph"])
        self.assertIsNone(r["top_shot_game_id"])

    def test_the_dedicated_speed_responses_win_when_both_exist(self):
        r = edge.parse_skater(DETAIL, SKATING, SHOT)
        self.assertNotEqual(r["top_shot_mph"], DETAIL["topShotSpeed"]["imperial"])

    def test_no_data_is_all_none(self):
        self.assertTrue(all(v is None for v in edge.parse_skater(None, None, None).values()))

    def test_game_id_comes_from_the_end_of_the_link(self):
        self.assertEqual(edge._game_id("/gamecenter/a-vs-b/2025/11/13/2025020274"), 2025020274)
        self.assertIsNone(edge._game_id(None))
        self.assertIsNone(edge._game_id("/gamecenter/nothing"))


class ZeroMeansNoData(unittest.TestCase):
    def test_a_zero_mph_top_shot_is_missing_not_a_record_low(self):
        shot = {"hardestShots": [{"gameDate": "2025-11-13", "gameCenterLink": "/gamecenter/a/2025/11/13/2025020274",
                                  "shotSpeed": {"imperial": 0}}],
                "shotSpeedDetails": {"topShotSpeed": {"imperial": 0, "percentile": 0.0}, "avgShotSpeed": {"imperial": 0, "percentile": 0.0}}}
        r = edge.parse_skater({"topShotSpeed": {"imperial": 0, "percentile": 0.0}}, SKATING, shot)
        for col in ("top_shot_mph", "top_shot_pctile", "top_shot_date", "top_shot_game_id", "avg_shot_mph", "avg_shot_pctile"):
            self.assertIsNone(r[col], col)
        self.assertEqual(r["top_speed_mph"], 24.6119)       # the rest of the row is untouched

    def test_a_real_slow_shot_is_kept(self):
        r = edge.parse_skater({"topShotSpeed": {"imperial": 34.19, "percentile": 0.02}}, None, None)
        self.assertEqual(r["top_shot_mph"], 34.19)


class ParseGoalie(unittest.TestCase):
    def test_every_column_and_nothing_else(self):
        self.assertEqual(set(edge.parse_goalie(GOALIE)), {c for c, _ in edge.GOALIE_COLUMNS})
        self.assertEqual(set(edge.parse_goalie(None)), {c for c, _ in edge.GOALIE_COLUMNS})

    def test_save_percentage_by_range(self):
        r = edge.parse_goalie(GOALIE)
        self.assertEqual((r["sv_all"], r["sv_high"], r["sv_mid"], r["sv_long"]), (0.899, 0.812, 0.882, 0.98))
        self.assertEqual((r["saves_high"], r["ga_high"], r["sv_high_pctile"]), (255, 59, 0.5254))
        self.assertEqual((r["ga_avg"], r["games_above_900"], r["goal_diff_per60"]), (3.33, 0.579, -0.4))

    def test_missing_ranges_are_none(self):
        r = edge.parse_goalie({"shotLocationSummary": [{"locationCode": "all", "savePctg": 0.9}]})
        self.assertEqual((r["sv_all"], r["sv_high"], r["saves_long"]), (0.9, None, None))


class CurrentSeasonRefresh(unittest.TestCase):
    START = datetime(2026, 10, 14, 23, 0, tzinfo=timezone.utc)

    def pick(self, fetched, window=30):
        return ingest.edge_current_candidates({1: self.START}, {} if fetched is None else {1: fetched}, window)

    def test_never_fetched_players_are_included(self):
        self.assertEqual(self.pick(None), [1])

    def test_fetched_before_his_latest_game_is_refreshed(self):
        self.assertEqual(self.pick(self.START - timedelta(hours=16)), [1])   # the night the backfill raced the games

    def test_fetched_soon_after_the_game_is_refreshed_again_next_time(self):
        self.assertEqual(self.pick(self.START + timedelta(hours=5)), [1])    # the tracking data may not have caught up yet

    def test_fetched_long_after_the_game_is_left_alone(self):
        self.assertEqual(self.pick(self.START + timedelta(hours=31)), [])
        self.assertEqual(self.pick(self.START + timedelta(hours=30)), [])    # the window is exclusive

    def test_only_the_players_who_need_it(self):
        out = ingest.edge_current_candidates(
            {1: self.START, 2: self.START, 3: self.START},
            {1: self.START + timedelta(days=2), 2: self.START - timedelta(hours=1)})
        self.assertEqual(sorted(out), [2, 3])


class Consistency(unittest.TestCase):
    """The column lists, the ingest and the API have to agree, or a fetch or a query fails at run time."""

    def test_ingest_column_groups_are_real_columns(self):
        cols = {c for c, _ in edge.SKATER_COLUMNS}
        self.assertTrue(ingest.EDGE_EXTRA_COLUMNS <= cols)
        self.assertTrue(ingest.EDGE_REFINED_COLUMNS <= cols)
        self.assertFalse(ingest.EDGE_EXTRA_COLUMNS & ingest.EDGE_REFINED_COLUMNS)

    def test_the_summary_pass_never_touches_the_extras(self):
        core = {c for c, _ in edge.SKATER_COLUMNS} - ingest.EDGE_EXTRA_COLUMNS
        parsed = edge.parse_skater(DETAIL, None, None)
        self.assertTrue(all(parsed[c] is None for c in ingest.EDGE_EXTRA_COLUMNS))
        self.assertTrue(core)

    def test_every_leaderboard_stat_reads_real_columns(self):
        cols = {c for c, _ in edge.SKATER_COLUMNS}
        for stat, (expr, _label, _unit, pct, date, game) in api.TRACKING_STATS.items():
            used = set(re.findall(r"e\.(\w+)", expr))
            self.assertTrue(used, stat)
            self.assertTrue(used <= cols, f"{stat}: {used - cols}")
            for extra in (pct, date, game):
                if extra:
                    self.assertIn(extra, cols, stat)

    def test_every_goalie_stat_reads_real_columns(self):
        cols = {c for c, _ in edge.GOALIE_COLUMNS}
        for stat, (col, _label, shots, minimum) in api.GOALIE_TRACKING.items():
            self.assertIn(col, cols, stat)
            self.assertTrue(set(shots) <= cols, stat)
            self.assertGreater(minimum, 0)


if __name__ == "__main__":
    unittest.main()
