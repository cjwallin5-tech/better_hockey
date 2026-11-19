import unittest

import finishes


def season(sid, g, a, p, gr, ar, pr):
    return {"season_id": sid, "goals": g, "assists": a, "points": p, "goals_rank": gr, "assists_rank": ar, "points_rank": pr}


class SummarizeTest(unittest.TestCase):
    def test_led_seasons_and_top_counts(self):
        rows = [season(2, 50, 80, 130, 3, 1, 1), season(1, 20, 60, 80, 40, 6, 9), season(3, 30, 40, 70, 12, 11, 20)]
        out = {e["stat"]: e for e in finishes.summarize(rows)}
        self.assertEqual([s["season_id"] for s in out["points"]["led"]], [2])
        self.assertEqual((out["points"]["top5"], out["points"]["top10"]), (1, 2))
        self.assertEqual(out["assists"]["led"], [{"season_id": 2, "value": 80}])
        self.assertEqual((out["assists"]["top5"], out["assists"]["top10"]), (1, 2))
        self.assertEqual(out["goals"]["led"], [])
        self.assertEqual((out["goals"]["top5"], out["goals"]["top10"]), (1, 1))

    def test_a_stat_with_no_top_ten_finish_is_left_out(self):
        self.assertEqual(finishes.summarize([season(1, 5, 5, 10, 90, 90, 90)]), [])

    def test_a_zero_total_never_counts_even_when_everyone_ties_at_zero(self):
        self.assertEqual(finishes.summarize([season(1, 0, 0, 0, 1, 1, 1)]), [])

    def test_led_seasons_are_oldest_first(self):
        rows = [season(5, 1, 1, 9, 1, 1, 1), season(2, 1, 1, 8, 1, 1, 1)]
        led = {e["stat"]: e["led"] for e in finishes.summarize(rows)}
        self.assertEqual([s["season_id"] for s in led["points"]], [2, 5])
