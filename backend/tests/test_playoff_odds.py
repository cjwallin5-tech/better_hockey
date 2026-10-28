import unittest

import playoff_odds as po


def league():
    """Two conferences, each two divisions of five teams (the top three per division plus two wild cards make it)."""
    teams = []
    for conf in ("East", "West"):
        for div, base in (("A", 100), ("B", 90)):
            for i in range(5):
                teams.append({"abbrev": f"{conf[0]}{div}{i}", "conference": conf, "division": f"{conf}{div}",
                              "points": base - 2 * i, "reg_wins": 30, "goal_diff": 0, "games_played": 40})
    return teams


class Ratings(unittest.TestCase):
    def test_goal_difference_is_shrunk_toward_average(self):
        t = [{"abbrev": "X", "goal_diff": 20, "games_played": 25}, {"abbrev": "Y", "goal_diff": 0, "games_played": 25}]
        r = po.team_ratings(t)
        self.assertAlmostEqual(r["X"], 20 / (25 + po.PRIOR_GAMES))
        self.assertEqual(r["Y"], 0)


class Simulate(unittest.TestCase):
    def test_with_nothing_left_to_play_the_standings_decide(self):
        out = po.simulate(league(), [], sims=200)
        made = {a for a, o in out.items() if o["make_playoffs"] == 1.0}
        # top 3 of each division, then the two best of the rest in each conference
        for conf in "EW":
            self.assertEqual({a for a in made if a[0] == conf}, {f"{conf}A0", f"{conf}A1", f"{conf}A2", f"{conf}B0", f"{conf}B1", f"{conf}B2", f"{conf}A3", f"{conf}A4"})
        self.assertTrue(all(o["make_playoffs"] in (0.0, 1.0) for o in out.values()))
        self.assertEqual(out["EA0"]["win_division"], 1.0)

    def test_sixteen_teams_make_it_in_every_simulation(self):
        teams = league()
        remaining = [(teams[i]["abbrev"], teams[(i + 7) % 20]["abbrev"]) for i in range(20)]
        out = po.simulate(teams, remaining, sims=500, seed=3)
        self.assertAlmostEqual(sum(o["make_playoffs"] for o in out.values()), 16.0, places=6)
        self.assertAlmostEqual(sum(o["win_division"] for o in out.values()), 4.0, places=6)

    def test_a_stronger_team_does_better(self):
        teams = league()
        for t in teams:
            if t["abbrev"] == "EB3":
                t["goal_diff"] = 200   # a bubble team that has been dominant
        remaining = [("EB3", other["abbrev"]) for other in teams if other["division"] == "EastB" and other["abbrev"] != "EB3"] * 6
        strong = po.simulate(teams, remaining, sims=500, seed=1)["EB3"]["make_playoffs"]
        teams[[t["abbrev"] for t in teams].index("EB3")]["goal_diff"] = -200
        weak = po.simulate(teams, remaining, sims=500, seed=1)["EB3"]["make_playoffs"]
        self.assertGreater(strong, weak)

    def test_same_seed_same_answer(self):
        teams = league()
        remaining = [("EA0", "EB0"), ("WA1", "WB2")]
        self.assertEqual(po.simulate(teams, remaining, sims=100, seed=5), po.simulate(teams, remaining, sims=100, seed=5))


class Playoffs(unittest.TestCase):
    def test_a_series_is_fair_between_equals_and_favors_the_better_team(self):
        import numpy as np
        S = po.series_matrix(np.array([0.0, 0.0, 1.0]))
        self.assertTrue(0.5 < S[0, 1] < 0.6)            # equal teams: only the home edge helps
        self.assertGreater(S[2, 0], 0.75)
        self.assertGreater(S[2, 0], S[0, 2])            # home ice matters

    def test_exactly_one_cup_winner_and_the_field_narrows_by_halves(self):
        teams = league()
        remaining = [(teams[i]["abbrev"], teams[(i + 7) % 20]["abbrev"]) for i in range(20)]
        out = po.simulate(teams, remaining, sims=300, seed=2)
        for key, total in (("make_playoffs", 16), ("round2", 8), ("conf_final", 4), ("final", 2), ("cup", 1)):
            self.assertAlmostEqual(sum(o[key] for o in out.values()), total, places=6, msg=key)

    def test_odds_never_go_up_from_one_round_to_the_next(self):
        out = po.simulate(league(), [("EA0", "EB0")], sims=100, seed=1)
        for o in out.values():
            self.assertGreaterEqual(o["make_playoffs"] + 1e-9, o["round2"])
            self.assertGreaterEqual(o["round2"] + 1e-9, o["conf_final"])
            self.assertGreaterEqual(o["conf_final"] + 1e-9, o["final"])
            self.assertGreaterEqual(o["final"] + 1e-9, o["cup"])

    def test_a_dominant_team_is_the_cup_favorite(self):
        teams = league()
        for t in teams:
            if t["abbrev"] == "WB1":
                t["goal_diff"] = 400
        out = po.simulate(teams, [], sims=200, seed=1)
        self.assertEqual(max(out, key=lambda a: out[a]["cup"]), "WB1")


if __name__ == "__main__":
    unittest.main()
