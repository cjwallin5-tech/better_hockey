import unittest

import scouting as sc


def row(pid, pos="C", gp=40, points=20, toi=1200, **kw):
    base = {"player_id": pid, "position": pos, "games_played": gp, "points": points, "toi_per_game_sec": toi,
            "toi_5v5_per_game": 900, "ixg": 5.0, "xgf_pct": 0.5, "xga": 10.0, "pp_points_per60": 4.0,
            "hits_per60": 3.0, "blocks_per60": 1.0, "top_speed_mph": 22.0}
    base.update(kw)
    return base


def league(n=20):
    return [row(i, points=10 + i) for i in range(1, n + 1)]


class Card(unittest.TestCase):
    def axis(self, c, key):
        return next(a for a in c["axes"] if a["key"] == key)

    def test_best_scorer_tops_the_scoring_axis(self):
        rows = league()
        c = sc.card(rows, rows[-1])
        self.assertEqual(self.axis(c, "scoring")["percentile"], 100)
        self.assertEqual(sc.card(rows, rows[0])["axes"][0]["percentile"], 5)

    def test_fewer_expected_goals_against_is_better(self):
        rows = [row(i, xga=5 + i) for i in range(1, 21)]
        self.assertEqual(self.axis(sc.card(rows, rows[0]), "defense")["percentile"], 100)
        self.assertEqual(self.axis(sc.card(rows, rows[-1]), "defense")["percentile"], 5)

    def test_forwards_and_defensemen_are_ranked_apart(self):
        rows = league() + [row(100 + i, pos="D", points=2 + i) for i in range(12)]
        d = sc.card(rows, rows[-1])
        self.assertEqual(d["peer_group"], "defensemen")
        self.assertEqual(d["peer_count"], 12)
        self.assertEqual(self.axis(d, "scoring")["percentile"], 100)

    def test_strengths_skip_style_axes(self):
        rows = [row(i, hits_per60=i) for i in range(1, 21)]
        c = sc.card(rows, rows[-1])
        self.assertEqual(self.axis(c, "hits")["percentile"], 100)
        self.assertNotIn("Hits", c["strengths"])

    def test_missing_figures_give_no_percentile(self):
        rows = league()
        rows[-1]["top_speed_mph"] = None
        self.assertIsNone(self.axis(sc.card(rows, rows[-1]), "speed")["percentile"])

    def test_too_few_peers_gives_no_percentiles(self):
        rows = league(5)
        self.assertTrue(all(a["percentile"] is None for a in sc.card(rows, rows[0])["axes"]))

    def test_short_stint_is_flagged_but_still_shown(self):
        rows = league() + [row(99, gp=5)]
        c = sc.card(rows, rows[-1])
        self.assertTrue(c["small_sample"])
        self.assertEqual(c["peer_count"], 21)


if __name__ == "__main__":
    unittest.main()
