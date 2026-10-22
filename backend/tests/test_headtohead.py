import unittest
from datetime import date

import headtohead as h2h


def game(n, result, gf, ga, season=20252026, day=1):
    return {"game_id": n, "season_id": season, "game_date": date(2025, 11, day), "gf": gf, "ga": ga, "result": result}


class TeamSummary(unittest.TestCase):
    GAMES = [game(1, "W", 4, 1, day=1), game(2, "OTL", 2, 3, day=5), game(3, "OTW", 3, 2, day=9),
             game(4, "W", 5, 2, day=12), game(5, "L", 0, 3, season=20242025, day=3)]

    def test_record_counts_overtime_results_from_both_sides(self):
        s = h2h.team_summary(self.GAMES)
        self.assertEqual((s["games"], s["a_wins"], s["b_wins"]), (5, 3, 2))
        self.assertEqual((s["a_ot_losses"], s["b_ot_losses"]), (1, 1))
        self.assertEqual((s["a_goals"], s["b_goals"]), (14, 11))

    def test_streak_counts_back_from_the_latest_game(self):
        # newest first: W (12th), OTW (9th), then an OT loss
        self.assertEqual(h2h.team_summary(self.GAMES)["streak"], {"team": "a", "games": 2})
        self.assertEqual(h2h.team_summary([game(1, "W", 1, 0, day=1), game(2, "L", 0, 1, day=2)])["streak"],
                         {"team": "b", "games": 1})

    def test_input_order_does_not_matter(self):
        self.assertEqual(h2h.team_summary(list(reversed(self.GAMES))), h2h.team_summary(self.GAMES))

    def test_split_by_season_newest_first(self):
        by = h2h.team_summary(self.GAMES)["by_season"]
        self.assertEqual([x["season_id"] for x in by], [20252026, 20242025])
        self.assertEqual((by[0]["games"], by[0]["a_wins"], by[0]["b_wins"], by[0]["gf"], by[0]["ga"]), (4, 3, 1, 14, 8))
        self.assertEqual((by[1]["a_wins"], by[1]["b_wins"]), (0, 1))

    def test_no_meetings(self):
        s = h2h.team_summary([])
        self.assertEqual((s["games"], s["streak"], s["by_season"]), (0, None, []))


class PlayerSummary(unittest.TestCase):
    def rows(self):
        mk = lambda opp, g, a, season=20252026: {"season_id": season, "game_id": 1, "game_date": date(2025, 11, 1),
                                                 "opponent": opp, "goals": g, "assists": a}
        return [mk("CGY", 1, 2), mk("CGY", 0, 1, season=20242025), mk("VAN", 2, 2), mk("SEA", 0, 0), mk("SEA", 1, 0)]

    def test_line_against_the_team_and_everyone_else(self):
        s = h2h.player_summary(self.rows(), "CGY")
        self.assertEqual(s["vs"], {"games": 2, "goals": 1, "assists": 3, "points": 4, "points_per_game": 2.0})
        self.assertEqual((s["rest"]["games"], s["rest"]["points"], s["rest"]["points_per_game"]), (3, 5, 1.67))

    def test_by_season_split(self):
        by = h2h.player_summary(self.rows(), "CGY")["by_season"]
        self.assertEqual([(x["season_id"], x["games"], x["points"]) for x in by], [(20252026, 1, 3), (20242025, 1, 1)])

    def test_never_faced_them(self):
        s = h2h.player_summary(self.rows(), "EDM")
        self.assertEqual((s["vs"]["games"], s["vs"]["points_per_game"], s["by_season"]), (0, None, []))
        self.assertEqual(s["rest"]["games"], 5)


class GoalieSummary(unittest.TestCase):
    def rows(self):
        mk = lambda opp, sa, ga, season=20252026: {"season_id": season, "game_id": 1, "game_date": date(2025, 11, 1),
                                                   "opponent": opp, "shots_against": sa, "goals_against": ga}
        return [mk("CGY", 30, 3), mk("CGY", 20, 0, season=20242025), mk("VAN", 25, 2), mk("SEA", 35, 1)]

    def test_line_against_the_team_and_everyone_else(self):
        s = h2h.goalie_summary(self.rows(), "CGY")
        self.assertEqual(s["vs"], {"games": 2, "shots_against": 50, "goals_against": 3, "save_pct": 0.94,
                                   "shots_per_game": 25.0, "goals_against_per_game": 1.5})
        self.assertEqual((s["rest"]["games"], s["rest"]["save_pct"]), (2, 0.95))

    def test_by_season_split_newest_first(self):
        by = h2h.goalie_summary(self.rows(), "CGY")["by_season"]
        self.assertEqual([(x["season_id"], x["games"], x["save_pct"]) for x in by], [(20252026, 1, 0.9), (20242025, 1, 1.0)])

    def test_never_faced_them(self):
        s = h2h.goalie_summary(self.rows(), "EDM")
        self.assertEqual((s["vs"]["games"], s["vs"]["save_pct"], s["by_season"]), (0, None, []))
        self.assertEqual(s["rest"]["games"], 4)


if __name__ == "__main__":
    unittest.main()
