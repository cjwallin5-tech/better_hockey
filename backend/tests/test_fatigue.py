import unittest
from datetime import date, timedelta

import fatigue


def g(team, n, day, season=1):
    return {"team": team, "season_id": season, "game_id": n, "game_date": date(2025, 11, 1) + timedelta(days=day)}


class Rest(unittest.TestCase):
    def test_days_since_the_previous_game_and_first_game(self):
        r = fatigue.rest_days([g("A", 1, 0), g("A", 2, 1), g("A", 3, 4)])
        self.assertEqual([r["A", 1], r["A", 2], r["A", 3]], [fatigue.FIRST_GAME_REST, 1, 3])

    def test_seasons_are_separate_and_order_does_not_matter(self):
        games = [g("A", 3, 4), g("A", 1, 0), g("A", 9, 0, season=2)]
        r = fatigue.rest_days(games)
        self.assertEqual(r["A", 3], 4)
        self.assertEqual(r["A", 9], fatigue.FIRST_GAME_REST)

    def test_kinds(self):
        self.assertEqual(fatigue.kind(1, 2), "tired")
        self.assertEqual(fatigue.kind(2, 1), "edge")
        self.assertEqual(fatigue.kind(1, 1), "both")
        self.assertEqual(fatigue.kind(3, 2), "normal")


def res(team, n, k, pts, gf, ga):  # one finished game
    return {"team": team, "game_id": n, "kind": k, "points": pts, "wins": 1 if pts == 2 else 0, "goals_for": gf, "goals_against": ga}


class Effects(unittest.TestCase):
    def rows(self):
        out = []
        for team in ("A", "B"):
            out += [res(team, i, "tired", 0, 1, 3) for i in range(5)]          # always loses when tired
            out += [res(team, 100 + i, "normal", 2, 3, 1) for i in range(5)]   # always wins when rested
        return out

    def test_gap_is_measured_against_the_teams_own_normal_games(self):
        e = fatigue.effects(self.rows())["tired"]
        self.assertEqual((e["games"], e["teams"]), (10, 2))
        self.assertAlmostEqual(e["points"]["gap"], -2.0)
        self.assertAlmostEqual(e["goal_diff"]["gap"], -4.0)
        self.assertAlmostEqual(e["win_rate"]["gap"], -1.0)

    def test_teams_with_too_few_games_are_left_out(self):
        rows = self.rows()[:4] + [r for r in self.rows() if r["kind"] == "normal"]
        e = fatigue.effects(rows)["tired"]
        self.assertEqual(e["teams"], 0)
        self.assertIsNone(e["points"]["gap"])

    def test_team_lines(self):
        line = fatigue.team_lines(self.rows())["A"]
        self.assertEqual(line["tired"]["games"], 5)
        self.assertEqual(line["tired"]["points_pct"], 0)
        self.assertEqual(line["normal"]["points_pct"], 1)
        self.assertEqual(line["edge"]["games"], 0)
        self.assertIsNone(line["edge"]["points_pct"])


class Classify(unittest.TestCase):
    def test_games_with_unknown_rest_are_skipped(self):
        results = [{"team": "A", "opponent": "B", "game_id": 1}, {"team": "A", "opponent": "C", "game_id": 2}]
        out = list(fatigue.classify(results, {("A", 1): 1, ("B", 1): 3, ("A", 2): 1}))
        self.assertEqual([(r["game_id"], r["kind"]) for r in out], [(1, "tired")])


class Upcoming(unittest.TestCase):
    def test_mismatch_labels(self):
        rest = {("H", 1): 1, ("A", 1): 3, ("H", 2): 3, ("A", 2): 1, ("H", 3): 1, ("A", 3): 1, ("H", 4): 2, ("A", 4): 2}
        fx = [{"game_id": i, "home": "H", "away": "A"} for i in (1, 2, 3, 4, 5)]
        out = fatigue.upcoming(fx, rest)
        self.assertEqual([o["mismatch"] for o in out], ["home_tired", "away_tired", "both", None])  # 5 has no rest data


def tg(team, opp, n, day, home, season=1):
    return {"team": team, "opponent": opp, "season_id": season, "game_id": n,
            "game_date": date(2025, 11, 1) + timedelta(days=day), "is_home": home}


class Travel(unittest.TestCase):
    def test_distance_and_time_zones_follow_the_previous_game(self):
        # NYR home, then at LAK (cross-country west), then home against BOS
        games = [tg("NYR", "BOS", 1, 0, True), tg("NYR", "LAK", 2, 2, False), tg("NYR", "BOS", 3, 5, True)]
        t = fatigue.travel(games)
        self.assertEqual(t["NYR", 1]["km"], 0)
        self.assertAlmostEqual(t["NYR", 2]["km"], 3950, delta=100)
        self.assertEqual(t["NYR", 2]["hours_east"], -3)
        self.assertEqual(t["NYR", 3]["hours_east"], 3)
        self.assertAlmostEqual(t["NYR", 3]["km"], t["NYR", 2]["km"], delta=1)

    def test_road_and_home_streaks(self):
        games = [tg("NYR", "BOS", 1, 0, True), tg("NYR", "BOS", 2, 1, True), tg("NYR", "TOR", 3, 3, False),
                 tg("NYR", "MTL", 4, 5, False), tg("NYR", "TOR", 5, 7, True)]
        t = fatigue.travel(games)
        self.assertEqual([(t["NYR", i]["home_stand"], t["NYR", i]["road_game"]) for i in range(1, 6)],
                         [(1, 0), (2, 0), (0, 1), (0, 2), (1, 0)])

    def test_first_game_of_a_season_starts_from_the_teams_own_arena(self):
        t = fatigue.travel([tg("VAN", "SEA", 1, 0, False)])
        self.assertAlmostEqual(t["VAN", 1]["km"], 190, delta=15)

    def test_every_team_has_an_arena(self):
        import arenas
        self.assertEqual(len([k for k in arenas.ARENAS if k != "ARI"]), 32)


if __name__ == "__main__":
    unittest.main()
