import unittest

import projections as pj


def row(gp, goals, assists, ixg=None, position="C"):
    return {"games_played": gp, "goals": goals, "assists": assists, "ixg": ixg, "position": position}


AVG = {"F": (0.2, 0.3), "D": (0.05, 0.2)}


class Project(unittest.TestCase):
    def test_a_short_hot_start_is_pulled_toward_the_record(self):
        prior = {"goals": 0.3, "assists": 0.4}
        p = pj.project(row(10, 10, 10), prior, AVG, 1.0, 70, 10)   # 2.0 points a game so far
        self.assertAlmostEqual(p["goals_rate"], (10 + 40 * 0.3) / 50)
        self.assertAlmostEqual(p["assists_rate"], (10 + 40 * 0.4) / 50)
        self.assertLess(p["points_rate"], 2.0)
        self.assertGreater(p["points_rate"], 0.7)

    def test_expected_games_scale_with_how_often_they_play(self):
        full = pj.project(row(10, 3, 3), None, AVG, 1.0, 74, 10)
        half = pj.project(row(5, 3, 3), None, AVG, 1.0, 74, 10)
        self.assertAlmostEqual(full["expected_games"], 74)
        self.assertAlmostEqual(half["expected_games"], 37)

    def test_final_is_what_they_have_plus_the_rest(self):
        p = pj.project(row(20, 8, 12), {"goals": 0.3, "assists": 0.4}, AVG, 1.0, 64, 20)
        self.assertAlmostEqual(p["final_points"], 20 + p["rest_points"])
        self.assertAlmostEqual(p["final_goals"] + p["final_assists"], p["final_points"])

    def test_expected_goals_pull_a_lucky_scorer_down_and_an_unlucky_one_up(self):
        base = pj.project(row(30, 20, 10, ixg=10), None, AVG, 1.0, 54, 30)
        plain = pj.project(row(30, 20, 10), None, AVG, 1.0, 54, 30)
        self.assertLess(base["goals_rate"], plain["goals_rate"])
        unlucky = pj.project(row(30, 2, 10, ixg=10), None, AVG, 1.0, 54, 30)
        plain2 = pj.project(row(30, 2, 10), None, AVG, 1.0, 54, 30)
        self.assertGreater(unlucky["goals_rate"], plain2["goals_rate"])

    def test_no_record_uses_the_role_average_with_a_lighter_prior(self):
        d = pj.project(row(0, 0, 0, position="D"), None, AVG, 1.0, 84, 0)
        self.assertAlmostEqual(d["goals_rate"], 0.05)
        self.assertAlmostEqual(d["assists_rate"], 0.2)
        self.assertFalse(d["has_record"])

    def test_range_contains_the_estimate_and_widens_with_games_left(self):
        near = pj.project(row(70, 30, 40), {"goals": 0.4, "assists": 0.6}, AVG, 1.0, 14, 70)
        far = pj.project(row(10, 4, 6), {"goals": 0.4, "assists": 0.6}, AVG, 1.0, 74, 10)
        for p in (near, far):
            self.assertLess(p["low_points"], p["final_points"])
            self.assertGreater(p["high_points"], p["final_points"])
        self.assertLess(near["high_points"] - near["low_points"], far["high_points"] - far["low_points"])

    def test_unknown_team_schedule_projects_nothing_more(self):
        p = pj.project(row(10, 5, 5), None, AVG, 1.0, None, None)
        self.assertEqual(p["rest_points"], 0)
        self.assertEqual(p["final_points"], 10)

    def test_low_end_never_goes_below_what_they_have(self):
        p = pj.project(row(10, 0, 0), None, AVG, 1.0, 74, 10)
        self.assertGreaterEqual(p["low_points"], 0)


class LeagueFigures(unittest.TestCase):
    def test_factor_scales_expected_goals_to_goals(self):
        rows = [{"ixg": 10.0, "goals": 8}, {"ixg": 20.0, "goals": 22}, {"ixg": 0, "goals": 5}]
        self.assertAlmostEqual(pj.league_factor(rows), 1.0)
        self.assertEqual(pj.league_factor([]), 1.0)

    def test_role_averages_ignore_call_ups(self):
        rows = [row(80, 40, 40), row(80, 0, 40, position="D"), row(3, 3, 3)]
        out = pj.role_averages(rows)
        self.assertAlmostEqual(out["F"][0], 40 / 80)   # the 3-game call-up is left out
        self.assertAlmostEqual(out["D"][1], 0.5)



class GoalieFinal(unittest.TestCase):
    NOW = {"games_played": 10, "games_started": 9, "wins": 5, "saves": 250, "goals_against": 25, "shutouts": 1}

    def game(self, p, win=0.5, saves=25.0, ga=2.5, shutout=0.08):
        return {"probability": p, "line": {"win": win, "loss": 0.4, "otl": 0.1, "saves": saves, "shots": saves + ga, "ga": ga, "shutout": shutout}}

    def test_rest_is_each_games_line_weighted_by_the_chance_he_starts_it(self):
        out = pj.goalie_final(self.NOW, [self.game(1.0), self.game(0.5, win=0.6)])
        self.assertAlmostEqual(out["rest_starts"], 1.5)
        self.assertAlmostEqual(out["rest_wins"], 0.5 + 0.5 * 0.6)
        self.assertAlmostEqual(out["rest_saves"], 25 + 12.5)

    def test_final_is_what_he_has_plus_the_rest(self):
        out = pj.goalie_final(self.NOW, [self.game(1.0)])
        self.assertAlmostEqual(out["final_wins"], 5.5)
        self.assertAlmostEqual(out["final_starts"], 10)
        self.assertAlmostEqual(out["final_goals_against"], 27.5)

    def test_no_games_left_or_missing_stats_project_nothing_more(self):
        out = pj.goalie_final({"games_played": 3, "wins": None}, [])
        self.assertEqual(out["rest_starts"], 0)
        self.assertEqual(out["final_wins"], 0)


if __name__ == "__main__":
    unittest.main()
