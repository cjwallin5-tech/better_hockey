import unittest

import defense as d


def row(player, hits, gp=80, toi=1200, season=1, pos="C", takeaways=0, giveaways=0, blocks=0):
    return {"player_id": player, "season_id": season, "position": pos, "games_played": gp,
            "toi_per_game_sec": toi, "hits": hits, "blocked_shots": blocks, "takeaways": takeaways, "giveaways": giveaways}


class Rates(unittest.TestCase):
    def test_index_and_percentile_against_the_league(self):
        rows = [row(1, 80), row(2, 160), row(3, 1000, gp=10)]   # 3 is a short stint, kept out of the league
        ctx = d.build(rows)
        self.assertAlmostEqual(ctx["base"][(1, "F")]["hits"], 4.5)   # 240 hits in 3200 minutes
        low, high = d.season_profile(rows[0], ctx), d.season_profile(rows[1], ctx)
        self.assertEqual(low["hits"]["rate"], 3.0)
        self.assertAlmostEqual(low["hits"]["index"], 3 / 4.5, places=2)
        self.assertAlmostEqual(high["hits"]["index"], 6 / 4.5, places=2)
        self.assertEqual((low["hits"]["percentile"], high["hits"]["percentile"]), (0, 50))

    def test_forwards_and_defensemen_are_separate_leagues(self):
        rows = [row(1, 80), row(2, 160, pos="D")]
        base = d.build(rows)["base"]
        self.assertNotEqual(base[(1, "F")]["hits"], base[(1, "D")]["hits"])

    def test_no_ice_time_gives_no_profile(self):
        ctx = d.build([row(1, 80)])
        self.assertIsNone(d.season_profile(row(2, 5, toi=0), ctx))

    def test_net_takeaways_is_a_difference_not_a_ratio(self):
        rows = [row(1, 0, takeaways=40, giveaways=80), row(2, 0, takeaways=80, giveaways=40)]
        ctx = d.build(rows)
        p = d.season_profile(rows[0], ctx)["net_takeaways"]
        self.assertIsNone(p["index"])
        self.assertLess(p["diff"], 0)

    def test_career_pools_minutes_not_rates(self):
        rows = [row(1, 80, season=1), row(2, 160, season=1), row(1, 80, season=2), row(2, 160, season=2)]
        ctx = d.build(rows)
        career = d.career_profile([rows[0], rows[2]], ctx)
        self.assertAlmostEqual(career["hits"]["index"], 3 / 4.5, places=2)
        self.assertIsNone(d.career_profile([row(1, 5, toi=0)], ctx))


class OnIce(unittest.TestCase):
    BASE = dict(player_id=1, season_id=1, position="D", on_toi=60000.0, on_xgf=45.0, on_xga=40.0,
                on_cf=900, on_ca=800, t_toi=240000.0, t_xgf=180.0, t_xga=190.0)

    def test_relative_to_teammates(self):
        m = d.onice_metrics(self.BASE)
        # 40 xGA in 1000 minutes = 2.4/60 on the ice; the team allowed 150 in 3000 minutes = 3.0/60 without him
        self.assertEqual((m["toi_min"], m["xga60"], m["rel_xga60"]), (1000, 2.4, -0.6))
        self.assertAlmostEqual(m["xgf_pct"], 45 / 85, places=3)
        self.assertAlmostEqual(m["cf_pct"], 900 / 1700, places=3)

    def test_too_little_time_off_the_ice_means_no_relative_figure(self):
        self.assertIsNone(d.onice_metrics({**self.BASE, "t_toi": 60300.0})["rel_xga60"])

    def test_percentiles_count_the_share_of_peers_who_allow_more(self):
        rows = [{**self.BASE, "player_id": i, "on_xga": x} for i, x in ((1, 30.0), (2, 40.0), (3, 50.0))]
        res = d.build_onice(rows)
        self.assertEqual([res[(i, 1)]["xga60_pct"] for i in (1, 2, 3)], [67, 33, 0])

    def test_small_samples_get_numbers_but_no_percentile(self):
        rows = [{**self.BASE, "player_id": i} for i in (1, 2, 3)]
        rows.append({**self.BASE, "player_id": 9, "on_toi": 1000.0, "t_toi": 100000.0})
        res = d.build_onice(rows)
        self.assertNotIn("xga60_pct", res[(9, 1)])
        self.assertIn("xga60_pct", res[(1, 1)])

    def test_career_pools_totals(self):
        m = d.onice_career([self.BASE, {**self.BASE, "season_id": 2}])
        self.assertEqual((m["toi_min"], m["xga60"], m["rel_xga60"]), (2000, 2.4, -0.6))
        self.assertIsNone(d.onice_career([]))


if __name__ == "__main__":
    unittest.main()
