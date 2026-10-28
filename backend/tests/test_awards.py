import random
import unittest

import awards as aw


def skater(pid, points, gp=80, pos="C", team_pct=0.6, toi=1200, rookie=False, age=22):
    return {"id": pid, "name": f"S{pid}", "pos": pos, "team": "AAA", "gp": gp, "goals": points // 3, "points": points, "toi_pg": toi,
            "team_pct": team_pct, "rookie": rookie, "age": age}


def goalie(pid, gsaa, wins, gp=60, team_pct=0.6):
    return {"id": pid, "name": f"G{pid}", "team": "AAA", "gp": gp, "wins": wins, "gsaa": gsaa, "team_pct": team_pct, "saves": 1500, "shots_against": 1650}


class Pools(unittest.TestCase):
    def test_hart_takes_the_top_scorers_best_first(self):
        rows = [skater(i, 100 - i) for i in range(30)]
        out = aw.pool("hart", rows, [])
        self.assertEqual(len(out), aw.POOL["hart"])
        self.assertEqual([r["id"] for r in out[:3]], [0, 1, 2])

    def test_norris_is_defensemen_only(self):
        rows = [skater(1, 90, pos="C"), skater(2, 60, pos="D"), skater(3, 50, pos="D")]
        self.assertEqual([r["id"] for r in aw.pool("norris", rows, [])], [2, 3])

    def test_calder_is_rookies_under_the_age_cap(self):
        rows = [skater(1, 90), skater(2, 60, rookie=True), skater(3, 70, rookie=True, age=27), skater(4, 40, rookie=True, age=None)]
        self.assertEqual([r["id"] for r in aw.pool("calder", rows, [])], [2])

    def test_vezina_needs_a_real_workload_and_ranks_by_goals_saved(self):
        gs = [goalie(1, 20, 30, gp=60), goalie(2, 35, 20, gp=10), goalie(3, 10, 25, gp=55)]
        self.assertEqual([r["id"] for r in aw.pool("vezina", [], gs)], [1, 3])


def forward(pid, points, sat=0.5, sh=60.0, fo=0.5, pos="C", gp=80, takeaways=40):
    return {**skater(pid, points, gp=gp, pos=pos), "sat": sat, "sh": sh, "fo": fo, "fo_n": 800, "takeaways": takeaways}


class Selke(unittest.TestCase):
    def test_the_short_list_is_forwards_who_rank_well_on_points_shots_and_penalty_killing_together(self):
        rows = [forward(1, 100, sat=0.48, sh=5), forward(2, 70, sat=0.56, sh=110), forward(3, 20, sat=0.45, sh=0), forward(4, 70, sat=0.5, sh=60, pos="D")]
        out = aw.pool("selke", rows, [])
        self.assertEqual([r["id"] for r in out][:2], [2, 1])      # the all-round forward beats the pure scorer; the defenseman is not a forward
        self.assertNotIn(4, [r["id"] for r in out])

    def test_part_timers_are_left_out(self):
        rows = [forward(1, 50, gp=80), forward(2, 60, gp=20)]
        self.assertEqual([r["id"] for r in aw.pool("selke", rows, [])], [1])

    def test_faceoffs_count_for_centers_only(self):
        c, w = forward(1, 60, fo=0.58), forward(2, 60, fo=0.58, pos="L")
        f = aw.features("selke", [c, w])
        i = aw.FEATURES["selke"].index("fo")
        self.assertAlmostEqual(f[0][i], 0.8)
        self.assertEqual(f[1][i], 0.0)

    def test_a_better_two_way_forward_gets_more(self):
        rows = aw.pool("selke", [forward(1, 70, sat=0.58, sh=110, fo=0.56, takeaways=80), forward(2, 70, sat=0.5, sh=20, fo=0.48, takeaways=30)], [])
        p = aw.win_probs("selke", rows)
        self.assertGreater(p[0], p[1])


class Probabilities(unittest.TestCase):
    def test_chances_sum_to_one_and_the_better_candidate_gets_more(self):
        rows = aw.pool("hart", [skater(1, 120, team_pct=0.65), skater(2, 90, team_pct=0.5), skater(3, 60, team_pct=0.5)], [])
        p = aw.win_probs("hart", rows)
        self.assertAlmostEqual(sum(p), 1.0)
        self.assertGreater(p[0], p[1])
        self.assertGreater(p[1], p[2])

    def test_a_better_team_helps_a_vezina_candidate(self):
        gs = aw.pool("vezina", [], [goalie(1, 20, 30, team_pct=0.7), goalie(2, 20, 30, team_pct=0.45)])
        self.assertGreater(aw.win_probs("vezina", gs)[0], aw.win_probs("vezina", gs)[1])

    def test_features_are_relative_to_the_best_candidate(self):
        rows = aw.pool("norris", [skater(1, 80, pos="D", toi=1500), skater(2, 40, pos="D", toi=1200)], [])
        f = aw.features("norris", rows)
        self.assertEqual(f[0][0], 1.0)
        self.assertAlmostEqual(f[1][0], 0.5)
        self.assertAlmostEqual(f[1][1], 0.8)           # ice time, relative to the busiest

    def test_the_weights_cover_every_feature(self):
        for award in aw.AWARDS:
            self.assertEqual(set(aw.FEATURES[award]), set(aw.WEIGHTS[award]))


def cand(pid, now, final, sd=5.0, team="AAA"):
    return {"id": pid, "name": f"S{pid}", "team": team, "pos": "C", "games_played": 12, "points": now, "goals": now // 3, "toi_pg": 1200,
            "rookie": False, "age": 24, "final_gp": 84, "final_points": final, "sd_points": sd}


class Odds(unittest.TestCase):
    TEAMS = {"AAA": (100.0, 8.0)}

    def test_a_clear_leader_is_favoured_but_not_certain(self):
        cands = [cand(1, 30, 150), cand(2, 20, 120), cand(3, 18, 110)]
        p = aw.odds("hart", cands, self.TEAMS, draws=200, seed=1)
        self.assertGreater(p[1], p[2])
        self.assertLess(p[1], 1.0)
        self.assertAlmostEqual(sum(p.values()), 1.0, places=6)

    def test_more_uncertainty_flattens_the_odds(self):
        tight = aw.odds("hart", [cand(1, 30, 130, sd=1), cand(2, 25, 120, sd=1)], self.TEAMS, draws=300, seed=2)
        loose = aw.odds("hart", [cand(1, 30, 130, sd=25), cand(2, 25, 120, sd=25)], self.TEAMS, draws=300, seed=2)
        self.assertGreater(tight[1], loose[1])

    def test_same_seed_same_answer(self):
        cands = [cand(1, 30, 150), cand(2, 20, 120)]
        self.assertEqual(aw.odds("hart", cands, self.TEAMS, draws=50, seed=3), aw.odds("hart", cands, self.TEAMS, draws=50, seed=3))

    def test_a_finish_never_falls_below_what_is_already_banked(self):
        rows = aw.draw_finals("hart", [cand(1, 40, 41, sd=30)], self.TEAMS, random.Random(5))
        self.assertGreaterEqual(rows[0]["points"], 40)

    def test_goalie_draws_carry_wins_and_goals_saved(self):
        g = {"id": 9, "name": "G9", "team": "AAA", "games_played": 12, "wins": 8, "gsaa": 5.0, "final_gp": 60, "final_wins": 36, "sd_wins": 3.0,
             "final_gsaa": 20.0, "sd_gsaa": 6.0}
        rows = aw.draw_finals("vezina", [g], self.TEAMS, random.Random(1))
        self.assertGreaterEqual(rows[0]["wins"], 8)
        self.assertIn("gsaa", rows[0])


if __name__ == "__main__":
    unittest.main()
