import unittest

import era


def row(season, gp, goals, assists, role="F", player=1):
    return {"player_id": player, "season_id": season, "role": role, "games_played": gp, "goals": goals, "assists": assists}


class LeagueRates(unittest.TestCase):
    def test_rates_per_game_ignoring_short_stints(self):
        rows = [row(1, 80, 40, 40, player=1), row(1, 80, 20, 20, player=2), row(1, 5, 50, 50, player=3)]
        r = era.league_rates(rows)[(1, "F")]
        self.assertAlmostEqual(r["goals"], 60 / 160)
        self.assertAlmostEqual(r["assists"], 60 / 160)

    def test_the_cutoff_scales_with_a_short_season(self):
        # a 20-game season: 25% of 20 is 5 but the floor is 10 games
        rows = [row(1, 20, 20, 20, player=1), row(1, 12, 0, 0, player=2), row(1, 9, 90, 90, player=3)]
        r = era.league_rates(rows)[(1, "F")]
        self.assertAlmostEqual(r["goals"], 20 / 32)

    def test_roles_are_separate(self):
        rows = [row(1, 80, 40, 40), row(1, 80, 8, 40, role="D", player=2)]
        r = era.league_rates(rows)
        self.assertGreater(r[(1, "F")]["goals"], r[(1, "D")]["goals"])


class Reference(unittest.TestCase):
    def test_mean_of_the_last_completed_seasons(self):
        rates = {(20252026 - 10001 * i, "F"): {"goals": 0.2 + 0.01 * i, "assists": 0.3} for i in range(5)}
        rates[(20112012, "F")] = {"goals": 9.9, "assists": 9.9}      # too old to count
        ref = era.reference_rates(rates, 20252026)
        self.assertAlmostEqual(ref["F"]["goals"], 0.22)
        self.assertNotIn("D", ref)

    def test_missing_seasons_are_skipped(self):
        rates = {(20252026, "F"): {"goals": 0.2, "assists": 0.3}}
        self.assertEqual(era.reference_rates(rates, 20252026)["F"]["goals"], 0.2)


class Adjustment(unittest.TestCase):
    RATES = {(1, "F"): {"goals": 0.4, "assists": 0.4}, (2, "F"): {"goals": 0.2, "assists": 0.2}}
    REF = {"F": {"goals": 0.2, "assists": 0.2}}

    def test_factors_scale_a_high_scoring_era_down(self):
        f = era.factors(self.RATES, self.REF)
        self.assertEqual(f[(1, "F")], {"goals": 0.5, "assists": 0.5})
        self.assertEqual(f[(2, "F")], {"goals": 1.0, "assists": 1.0})

    def test_adjusted_career_totals(self):
        fac = era.factors(self.RATES, self.REF)
        out = era.adjust_careers([row(1, 80, 10, 10), row(2, 80, 10, 10)], fac)[1]
        self.assertEqual((out["adj_goals"], out["adj_assists"], out["adj_points"]), (15.0, 15.0, 30.0))
        self.assertAlmostEqual(out["adj_points_per_game"], 30 / 160, places=2)  # stored to 3 decimals

    def test_an_unchanged_environment_changes_nothing(self):
        rates = {(1, "F"): {"goals": 0.3, "assists": 0.3}}
        fac = era.factors(rates, {"F": {"goals": 0.3, "assists": 0.3}})
        out = era.adjust_careers([row(1, 82, 30, 50)], fac)[1]
        self.assertEqual((out["adj_goals"], out["adj_assists"]), (30.0, 50.0))

    def test_seasons_without_a_factor_are_left_out(self):
        out = era.adjust_careers([row(99, 82, 30, 50)], era.factors(self.RATES, self.REF))
        self.assertEqual(out, {})

    def test_goals_and_assists_scale_separately(self):
        rates = {(1, "F"): {"goals": 0.4, "assists": 0.2}}
        fac = era.factors(rates, {"F": {"goals": 0.2, "assists": 0.2}})
        out = era.adjust_careers([row(1, 80, 20, 20)], fac)[1]
        self.assertEqual((out["adj_goals"], out["adj_assists"]), (10.0, 20.0))


if __name__ == "__main__":
    unittest.main()
