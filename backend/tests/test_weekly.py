import datetime as dt
import unittest

import auth
import weekly as wk

D = [dt.date(2026, 11, 2) + dt.timedelta(days=i) for i in range(7)]


def skater_row(pid, pos="C", gp=10, goals=5, assists=5, **stats):
    return {"player_id": pid, "position": pos, "games_played": gp, "goals": goals, "assists": assists, **stats}


class Rates(unittest.TestCase):
    def test_no_record_is_pulled_toward_the_position_average(self):
        rows = [skater_row(1, goals=10, assists=10), skater_row(2, goals=0, assists=0)]
        rates = wk.skater_rates(rows, {"goals": 1, "assists": 1}, {})
        self.assertEqual(rates[1][0], "C")
        self.assertGreater(rates[1][1], rates[2][1])
        self.assertLess(rates[1][1], 2.0)          # raw rate is 2.0 a game
        self.assertGreater(rates[2][1], 0)

    def test_a_record_pulls_toward_the_players_own_history(self):
        row = [skater_row(1, goals=0, assists=0)]
        high = wk.skater_rates(row, {"goals": 1, "assists": 1}, {1: {"goals": 0.5, "assists": 0.5}})[1][1]
        none = wk.skater_rates(row, {"goals": 1, "assists": 1}, {})[1][1]
        self.assertGreater(high, none)

    def test_unknown_positions_count_as_centers_and_players_without_games_are_left_out(self):
        rates = wk.skater_rates([skater_row(1, pos="F"), skater_row(2, gp=0)], {"goals": 1}, {})
        self.assertEqual(rates[1][0], "C")
        self.assertNotIn(2, rates)

    def test_other_stats_count_when_scored(self):
        rows = [skater_row(1, shots=40), skater_row(2, shots=10)]
        rates = wk.skater_rates(rows, {"shots": 0.5}, {})
        self.assertGreater(rates[1][1], rates[2][1])

    def test_game_score_moves_with_the_matchup(self):
        self.assertAlmostEqual(wk.skater_game_score(1.0, 1.2), 1.2)
        self.assertAlmostEqual(wk.skater_game_score(-1.0, 1.2), -0.8)
        self.assertEqual(wk.skater_game_score(1.0, None), 1.0)
        self.assertLess(wk.skater_game_score(1.0, 0.8), 1.0)

    def test_goalie_score_is_chance_times_the_line(self):
        game = {"probability": 0.5, "line": {"win": 0.6, "loss": 0.3, "otl": 0.1, "saves": 26, "ga": 2.5, "shutout": 0.08}}
        pts = wk.goalie_game_score(game, {"wins": 4, "saves": 0.2, "goals_against": -1, "shutouts": 3})
        self.assertAlmostEqual(pts, 0.5 * (4 * 0.6 + 0.2 * 26 - 2.5 + 3 * 0.08))


def entry(pid, group, scores, name=None):
    return {"id": pid, "name": name or str(pid), "kind": "skater", "group": group, "known": True,
            "games": [{"date": d, "score": s, "opponent": "X", "home": True} for d, s in scores.items()]}


class Lineup(unittest.TestCase):
    def test_each_day_starts_the_best_players_who_have_a_game(self):
        es = [entry(1, "C", {D[0]: 3, D[1]: 3}), entry(2, "C", {D[0]: 2, D[1]: 2}), entry(3, "C", {D[0]: 1})]
        plan = wk.optimize(es, {"C": 2})
        self.assertEqual(plan["starts"][D[0]], {1, 2})
        self.assertEqual(plan["starts"][D[1]], {1, 2})
        self.assertAlmostEqual(plan["total"], 3 + 2 + 3 + 2)
        self.assertEqual(plan["by_player"][3], {"starts": 0, "score": 0.0, "sat": 1})

    def test_a_bench_player_steps_in_on_a_day_a_starter_is_off(self):
        es = [entry(1, "C", {D[0]: 3}), entry(2, "C", {D[0]: 2, D[1]: 2})]
        plan = wk.optimize(es, {"C": 1})
        self.assertEqual(plan["starts"][D[0]], {1})
        self.assertEqual(plan["starts"][D[1]], {2})

    def test_groups_fill_independently(self):
        es = [entry(1, "C", {D[0]: 3}), entry(2, "D", {D[0]: 1})]
        plan = wk.optimize(es, {"C": 1, "D": 1})
        self.assertEqual(plan["starts"][D[0]], {1, 2})

    def test_a_group_with_no_slots_starts_nobody(self):
        plan = wk.optimize([entry(1, "G", {D[0]: 3})], {"C": 2})
        self.assertEqual(plan["starts"][D[0]], set())


class Load(unittest.TestCase):
    def test_heavy_and_light_weeks(self):
        es = [entry(1, "C", {d: 1 for d in D[:4]}, "Busy"), entry(2, "C", {D[0]: 1}, "Quiet"), entry(3, "C", {d: 1 for d in D[:3]}, "Mid")]
        heavy, light = wk.week_load(es)
        self.assertEqual(heavy, [("Busy", 4)])
        self.assertEqual(light, [("Quiet", 1)])


class Streaming(unittest.TestCase):
    PLAN = [{"player_id": 1, "name": "Mine", "team": "AAA", "games": [{"date": D[0], "probability": 1.0, "line": {"win": 0.5, "saves": 30}}]},
            {"player_id": 2, "name": "Good", "team": "BBB", "games": [{"date": D[0], "probability": 1.0, "line": {"win": 0.7, "saves": 30}}]},
            {"player_id": 3, "name": "Meh", "team": "CCC", "games": [{"date": D[0], "probability": 0.5, "line": {"win": 0.4, "saves": 28}}]},
            {"player_id": 4, "name": "Later", "team": "DDD", "games": [{"date": D[6] + dt.timedelta(days=3), "probability": 1.0, "line": {"win": 0.9}}]}]

    def test_ranks_goalies_not_on_the_roster_inside_the_window(self):
        picks = wk.streaming_picks(self.PLAN, {1}, {"wins": 4, "saves": 0.2}, set(D))
        self.assertEqual([p["name"] for p in picks], ["Good", "Meh"])

    def test_no_goalie_scoring_means_no_picks(self):
        self.assertEqual(wk.streaming_picks(self.PLAN, set(), {"goals": 1}, set(D)), [])


class Rendering(unittest.TestCase):
    def test_a_points_league_email_has_the_lineup_and_the_caveat(self):
        es = [entry(1, "C", {D[0]: 3, D[1]: 3}, "Star"), entry(2, "C", {D[0]: 1}, "Bench"), entry(3, "C", {D[0]: 1}, "Bench2")]
        plan = wk.optimize(es, {"C": 1})
        body = wk.render(plan, es, [], [], [], {**wk.DEFAULT_SLOTS, "C": 1}, True, D[0], D[6])
        self.assertIn("WEEK AHEAD: Mon 11/2 to Sun 11/8", body)
        self.assertIn("start Star (C)", body)
        self.assertIn("sit Bench, Bench2", body)
        self.assertIn("injuries", body)

    def test_a_category_league_gets_no_lineup(self):
        es = [entry(1, "C", {D[0]: 3}, "Star")]
        body = wk.render(wk.optimize(es, {"C": 1}), es, [], [], [], wk.DEFAULT_SLOTS, False, D[0], D[6])
        self.assertNotIn("BEST LINEUP", body)
        self.assertIn("categories", body)

    def test_no_games_says_so(self):
        body = wk.render(wk.optimize([], {}), [], [], [], [], wk.DEFAULT_SLOTS, True, D[0], D[6])
        self.assertIn("None of your players have a game", body)

    def test_the_week_is_the_seven_days_after_today(self):
        days = wk.week_dates(dt.date(2026, 11, 1))      # a Sunday
        self.assertEqual((days[0], days[-1]), (dt.date(2026, 11, 2), dt.date(2026, 11, 8)))
        self.assertEqual(days[0].weekday(), 0)


class LeagueSync(unittest.TestCase):
    def test_league_is_cleaned_to_whole_numbers_in_range(self):
        self.assertEqual(auth.clean_league({"format": "categories", "teams": "x", "slots": {"C": 3, "D": 99, "G": "a", "X": 1}}),
                         {"format": "categories", "slots": {"C": 3, "D": 10}})
        self.assertEqual(auth.clean_league({"teams": 12, "slots": {"C": 2}}), {"format": "points", "slots": {"C": 2}, "teams": 12})

    def test_nothing_usable_stays_empty(self):
        self.assertEqual(auth.clean_league({}), {})
        self.assertEqual(auth.clean_league("nope"), {})


if __name__ == "__main__":
    unittest.main()
