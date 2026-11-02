import unittest
from datetime import date, timedelta

import sos

LEAGUE = {"goals_pg": 3.0, "shots_pg": 28.0}


def team(off, de, xgf=3.0, xga=3.0):
    return {"off_ratio": off, "def_ratio": de, "xgf_pg": xgf, "xga_pg": xga}


RATINGS = {"STR": team(1.2, 0.85, 3.4, 2.5), "AVG": team(1.0, 1.0), "WEAK": team(0.85, 1.2, 2.5, 3.5), "ME": team(1.0, 1.0)}


def g(day, home, away, state="FUT", gid=None):
    return {"date": date(2026, 11, 1) + timedelta(days=day), "home": home, "away": away, "state": state, "game_id": gid or day}


class Points(unittest.TestCase):
    def test_a_win_is_worth_two_and_the_loser_keeps_a_point_in_overtime(self):
        self.assertAlmostEqual(sos.exp_points(1.0), 2.0)
        self.assertAlmostEqual(sos.exp_points(0.0), sos.OT_RATE)
        self.assertAlmostEqual(sos.exp_points(0.5), 1 + 0.5 * sos.OT_RATE)


class Schedule(unittest.TestCase):
    def rows(self, games):
        return {r["team"]: r for r in sos.team_rows(RATINGS, games, LEAGUE)}

    def test_a_schedule_of_strong_teams_is_harder_than_one_of_weak_teams(self):
        games = [g(1, "ME", "STR"), g(3, "STR", "ME")]
        hard = self.rows(games)["ME"]["left"]
        easy = self.rows([g(1, "ME", "WEAK"), g(3, "WEAK", "ME")])["ME"]["left"]
        self.assertLess(hard["schedule_points"], 0)
        self.assertGreater(easy["schedule_points"], 0)
        self.assertGreater(hard["opp_net"], easy["opp_net"])

    def test_an_average_opponent_changes_nothing(self):
        r = self.rows([g(1, "ME", "AVG"), g(3, "AVG", "ME")])["ME"]["left"]
        self.assertAlmostEqual(r["schedule_points"], 0.0, places=6)

    def test_home_and_away_are_counted_and_do_not_move_the_effect(self):
        home = self.rows([g(1, "ME", "AVG")])["ME"]["left"]
        away = self.rows([g(1, "AVG", "ME")])["ME"]["left"]
        self.assertEqual((home["home"], home["away"]), (1, 0))
        self.assertEqual((away["home"], away["away"]), (0, 1))
        self.assertAlmostEqual(home["schedule_points"], away["schedule_points"], places=6)

    def test_played_and_remaining_games_are_split_by_state(self):
        r = self.rows([g(-3, "ME", "STR", "OFF"), g(-1, "WEAK", "ME", "FINAL"), g(2, "ME", "AVG")])["ME"]
        self.assertEqual((r["played"]["games"], r["left"]["games"]), (2, 1))

    def test_the_next_block_is_the_first_games_left(self):
        games = [g(i, "ME", "STR" if i < 3 else "WEAK") for i in range(1, 7)]
        r = sos.team_rows(RATINGS, games, LEAGUE, next_n=3)
        me = next(x for x in r if x["team"] == "ME")
        self.assertEqual(me["next"]["games"], 3)
        self.assertLess(me["next"]["schedule_points"], 0)          # the first three are all against the strong team
        self.assertGreater(me["left"]["schedule_points"], me["next"]["schedule_points"])

    def test_back_to_backs_count_remaining_games_on_consecutive_days(self):
        games = [g(1, "ME", "AVG"), g(2, "AVG", "ME"), g(5, "ME", "AVG"), g(6, "WEAK", "ME")]
        self.assertEqual(self.rows(games)["ME"]["back_to_backs_left"], 2)

    def test_a_team_without_a_rating_has_no_figures_but_keeps_its_counts(self):
        r = sos.team_rows({**RATINGS}, [g(1, "ME", "NEW")], LEAGUE)
        me = next(x for x in r if x["team"] == "ME")
        self.assertEqual(me["left"]["games"], 1)
        self.assertIsNone(me["left"]["schedule_points"])


if __name__ == "__main__":
    unittest.main()
