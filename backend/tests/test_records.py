import unittest
from datetime import date
from pathlib import Path

import records


def game(pid, g, a, gt=2):
    return {"player_id": pid, "game_type": gt, "goals": g, "assists": a, "points": g + a}


def season(pid, sid, gp, g, a):
    return {"player_id": pid, "season_id": sid, "games_played": gp, "goals": g, "assists": a, "points": g + a}


class BigGames(unittest.TestCase):
    def test_counts_each_kind_of_big_game(self):
        out = records.game_counts([game(1, 3, 0), game(1, 4, 1), game(1, 5, 0), game(1, 0, 3), game(1, 2, 2), game(1, 2, 3)])
        self.assertEqual(out[(1, 2)], {"hat_tricks": 3, "four_goal_games": 2, "five_goal_games": 1, "three_assist_games": 2,
                                       "four_point_games": 4, "five_point_games": 3})

    def test_playoff_games_count_separately(self):
        out = records.game_counts([game(1, 3, 0), game(1, 3, 0, gt=3)])
        self.assertEqual(out[(1, 2)]["hat_tricks"], 1)
        self.assertEqual(out[(1, 3)]["hat_tricks"], 1)


class Seasons(unittest.TestCase):
    def test_milestones_and_bests(self):
        out = records.season_figures([season(1, 20202021, 82, 52, 48), season(1, 20212022, 82, 31, 71), season(1, 20222023, 40, 12, 20)])
        o = out[1]
        self.assertEqual(o["seasons_played"], 3)
        self.assertEqual((o["seasons_100p"], o["seasons_50g"], o["seasons_30g"], o["seasons_20g"]), (2, 1, 2, 2))
        self.assertEqual((o["seasons_60a"], o["seasons_50a"]), (1, 1))
        self.assertEqual((o["best_goals"], o["best_assists"], o["best_points"]), (52, 71, 102))

    def test_the_threshold_itself_counts(self):
        self.assertEqual(records.season_figures([season(1, 20202021, 82, 50, 50)])[1]["seasons_100p"], 1)


class Rookies(unittest.TestCase):
    def test_first_season_over_the_games_limit_is_the_rookie_season(self):
        rows = [season(1, 20182019, 10, 1, 1), season(1, 20192020, 70, 20, 30), season(1, 20202021, 70, 40, 40)]
        line = records.rookie_lines(rows, {1: date(2000, 1, 1)})[1]
        self.assertEqual((line["rookie_season"], line["rookie_gp"], line["rookie_points"]), (20192020, 70, 50))
        self.assertEqual(line["rookie_points_per_game"], round(50 / 70, 3))

    def test_exactly_the_limit_is_not_enough(self):
        self.assertEqual(records.rookie_lines([season(1, 20192020, records.ROOKIE_GAMES, 1, 1)], {}), {})

    def test_too_old_when_the_season_starts(self):
        rows = [season(1, 20192020, 70, 20, 30)]
        self.assertEqual(records.rookie_lines(rows, {1: date(1990, 1, 1)}), {})             # 29
        self.assertEqual(records.rookie_lines(rows, {1: date(1993, 9, 15)}), {})            # turns 26 on Sept 15 2019
        self.assertIn(1, records.rookie_lines(rows, {1: date(1993, 9, 16)}))                # still 25 on Sept 15

    def test_unknown_birth_date_is_not_held_against_the_player(self):
        self.assertIn(1, records.rookie_lines([season(1, 20192020, 70, 20, 30)], {1: None}))


class Schema(unittest.TestCase):
    def test_every_column_is_declared_in_schema_sql(self):
        sql = (Path(__file__).parent.parent / "schema.sql").read_text()
        for col, sql_type in records.COLUMNS:
            self.assertIn(f"ALTER TABLE career_skater ADD COLUMN IF NOT EXISTS {col} {sql_type};", sql, col)


if __name__ == "__main__":
    unittest.main()
