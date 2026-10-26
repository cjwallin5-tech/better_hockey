import unittest

import tonight as tn

LEAGUE = {"goals_pg": 3.0, "shots_pg": 28.0}
EVEN = {"off_ratio": 1.0, "def_ratio": 1.0}


class Matchup(unittest.TestCase):
    def test_even_teams_are_a_coin_flip_with_an_average_game(self):
        win, total = tn.matchup(EVEN, EVEN, LEAGUE)
        self.assertAlmostEqual(win, 0.5)
        self.assertAlmostEqual(total, 6.0)

    def test_the_stronger_side_is_favored_and_a_better_offense_means_more_goals(self):
        strong = {"off_ratio": 1.2, "def_ratio": 0.9}
        win, total = tn.matchup(strong, EVEN, LEAGUE)
        self.assertGreater(win, 0.5)
        self.assertGreater(total, 6.0)

    def test_missing_ratings_give_nothing(self):
        self.assertEqual(tn.matchup(None, EVEN, LEAGUE), (None, None))
        self.assertEqual(tn.matchup(EVEN, EVEN, {}), (None, None))


class Score(unittest.TestCase):
    def score(self, **kw):
        args = {"win": 0.5, "total": 6.0, "league_total": 6.0, "odds": None, "star": None, "yours": [], "teams_followed": []}
        return tn.score_game(**{**args, **kw})

    def test_a_toss_up_beats_a_lopsided_game(self):
        close = self.score(win=0.51)
        lopsided = self.score(win=0.80)
        self.assertGreater(close["score"], lopsided["score"])
        self.assertTrue(any("Toss-up" in r for r in close["reasons"]))
        self.assertFalse(any("Toss-up" in r for r in lopsided["reasons"]))

    def test_more_goals_than_average_add_points_fewer_do_not_subtract(self):
        base = self.score()
        high = self.score(total=7.0)
        low = self.score(total=5.0)
        self.assertGreater(high["score"], base["score"])
        self.assertEqual(low["score"], base["score"])
        self.assertTrue(any("High-scoring" in r for r in high["reasons"]))

    def test_stakes_need_both_teams_in_the_race(self):
        both = self.score(odds=[0.5, 0.55])
        one = self.score(odds=[0.5, 0.97])
        self.assertGreater(both["score"], one["score"])
        self.assertTrue(any("playoff race" in r for r in both["reasons"]))
        self.assertFalse(any("playoff race" in r for r in one["reasons"]))
        self.assertEqual(self.score(odds=[None, 0.5])["score"], self.score()["score"])

    def test_a_star_counts_only_at_the_threshold(self):
        star = {"name": "A Star", "ppg": 1.5, "gp": 20}
        self.assertTrue(any("A Star" in r for r in self.score(star=star)["reasons"]))
        self.assertGreater(self.score(star=star)["score"], self.score()["score"])
        self.assertEqual(self.score(star={"name": "B", "ppg": 0.9, "gp": 20})["score"], self.score()["score"])

    def test_your_players_count_up_to_a_cap_and_a_followed_team_adds_more(self):
        one = self.score(yours=["A"])
        five = self.score(yours=["A", "B", "C", "D", "E"])
        self.assertEqual(five["score"] - self.score()["score"], tn.W_PLAYER * tn.MAX_PLAYERS)
        self.assertGreater(five["score"], one["score"])
        self.assertIn("and 2 more", five["reasons"][0])
        team = self.score(teams_followed=["EDM"])
        self.assertEqual(team["score"] - self.score()["score"], tn.W_TEAM)

    def test_no_information_still_scores(self):
        out = tn.score_game(None, None, None, None, None, [], [])
        self.assertEqual(out, {"score": 0.0, "reasons": []})

    def test_reasons_come_most_valuable_first(self):
        out = self.score(win=0.5, yours=["A", "B"], odds=[0.5, 0.5])
        self.assertTrue(out["reasons"][0].startswith("Your players"))


if __name__ == "__main__":
    unittest.main()
