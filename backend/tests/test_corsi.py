import unittest

import corsi
import ingest


def shift(pid, team, start, end, period=1, type_code=517):
    return {"typeCode": type_code, "playerId": pid, "teamId": team, "period": period, "startTime": start, "endTime": end}


def play(kind, team, clock, situation="1551", period=1, period_type="REG"):
    return {"typeDescKey": kind, "periodDescriptor": {"number": period, "periodType": period_type},
            "timeInPeriod": clock, "situationCode": situation, "details": {"eventOwnerTeamId": team}}


class Clock(unittest.TestCase):
    def test_seconds_since_the_start_of_the_game(self):
        self.assertEqual(corsi.clock_to_seconds(1, "00:00"), 0)
        self.assertEqual(corsi.clock_to_seconds(2, "05:30"), 1200 + 330)
        self.assertEqual(corsi.clock_to_seconds(4, "01:00"), 3600 + 60)


class OnIce(unittest.TestCase):
    def test_a_shift_covers_its_end_but_not_its_start(self):
        spans = [(100, 200)]
        self.assertFalse(corsi.on_ice(spans, 100))
        self.assertTrue(corsi.on_ice(spans, 101))
        self.assertTrue(corsi.on_ice(spans, 200))
        self.assertFalse(corsi.on_ice(spans, 201))

    def test_include_start_flips_the_boundary(self):
        spans = [(100, 200)]
        self.assertTrue(corsi.on_ice(spans, 100, include_start=True))
        self.assertFalse(corsi.on_ice(spans, 200, include_start=True))


class ParseShifts(unittest.TestCase):
    def test_keeps_only_real_shifts_in_game_time(self):
        rows = [shift(1, 10, "00:10", "00:50"),
                shift(1, 10, "01:00", "01:30", type_code=505),      # not a regular shift
                shift(2, 20, "00:10", "00:50", period=5),           # shootout
                shift(3, 20, "05:00", "04:00"),                      # malformed: ends before it starts
                {"typeCode": 517, "playerId": 4, "teamId": 20, "period": 1, "startTime": None, "endTime": "01:00"},
                shift(5, 20, "00:00", "00:30", period=2)]
        spans, team_of = corsi.parse_shifts(rows)
        self.assertEqual(spans, {1: [(10, 50)], 5: [(1200, 1230)]})
        self.assertEqual(team_of, {1: 10, 5: 20})


class GameCorsi(unittest.TestCase):
    SHIFTS = [shift(1, 10, "04:00", "06:00"), shift(2, 20, "04:00", "06:00"), shift(3, 10, "10:00", "11:00")]
    PLAYS = [play("shot-on-goal", 10, "05:00"),
             play("blocked-shot", 20, "05:30"),
             play("goal", 10, "05:50"),
             play("missed-shot", 10, "10:30", situation="1451"),      # power play: not 5v5
             play("shot-on-goal", 10, "05:30", period=5, period_type="SO"),   # shootout: ignored
             play("faceoff", 10, "05:00")]

    def test_attempts_fenwick_and_goals_credit_everyone_on_the_ice(self):
        t = corsi.game_corsi(self.PLAYS, self.SHIFTS)
        # player 1 (team 10): own shot and goal for; the blocked attempt by team 20 against
        self.assertEqual(t[1], dict(cf=2, ca=1, ff=2, fa=0, gf=1, ga=0))
        # player 2 (team 20): the mirror image
        self.assertEqual(t[2], dict(cf=1, ca=2, ff=0, fa=2, gf=0, ga=1))
        self.assertNotIn(3, t)     # on the ice only for a power-play attempt

    def test_coverage_is_the_share_of_attempts_with_a_full_twelve_on_the_ice(self):
        full = [shift(p, 10 if p <= 6 else 20, "00:00", "20:00") for p in range(1, 13)]
        plays = [play("shot-on-goal", 10, "05:00"), play("shot-on-goal", 20, "06:00")]
        self.assertEqual(corsi.coverage(plays, full), 1.0)
        self.assertEqual(corsi.coverage(plays, full[:4]), 0.0)
        self.assertEqual(corsi.coverage([], full), 0.0)
        self.assertEqual(corsi.coverage(plays, []), 0.0)


class OnIceXg(unittest.TestCase):
    SHIFTS = [shift(1, 10, "00:50", "02:30"), shift(2, 20, "00:50", "02:30"), shift(3, 10, "05:00", "06:00")]

    def shot(self, team, t, xg, situation="1551"):
        return {"team_id": team, "time_sec": t, "xg": xg, "situation": situation}

    def test_xg_goes_to_everyone_on_the_ice_at_five_on_five(self):
        shots = [self.shot(10, 100, 0.2), self.shot(20, 120, 0.1),
                 self.shot(10, 100, 0.5, situation="1451"),    # power play: ignored
                 self.shot(10, 110, None)]                       # the model had no score for it
        out = ingest.onice_xg(shots, self.SHIFTS, [1, 2, 3])
        self.assertAlmostEqual(out[1][0], 0.2)
        self.assertAlmostEqual(out[1][1], 0.1)
        self.assertAlmostEqual(out[2][0], 0.1)
        self.assertAlmostEqual(out[2][1], 0.2)
        self.assertEqual(out[3], [0.0, 0.0])      # not on the ice for either shot

    def test_only_listed_skaters_are_returned(self):
        out = ingest.onice_xg([self.shot(10, 100, 0.2)], self.SHIFTS, [1])
        self.assertEqual(list(out), [1])


if __name__ == "__main__":
    unittest.main()
