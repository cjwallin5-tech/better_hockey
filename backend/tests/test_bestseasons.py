import unittest

import bestseasons as bs

CURRENT = 20262027


def season(pid, sid, gp, g, a, name="P", pos="C", team="EDM", hof=None, active=None):
    return {"player_id": pid, "season_id": sid, "team": team, "games_played": gp, "goals": g, "assists": a, "points": g + a,
            "name": name, "position": pos, "birth_country": "CAN", "hall_of_fame": hof, "active_season": active}


def board(*rows, defense=None):
    return bs.skater_board(list(rows), defense or {}, CURRENT)


def ranked(rows, sort="points", **kw):
    return bs.query(rows, "skater", sort=sort, **kw)[0]


class Skaters(unittest.TestCase):
    def test_the_season_in_progress_is_left_out(self):
        rows = board(season(1, 20252026, 82, 30, 40), season(1, CURRENT, 19, 11, 37))
        self.assertEqual([r["season_id"] for r in rows], [20252026])

    def test_points_per_game_and_the_last_team_of_a_traded_player(self):
        r = board(season(1, 20252026, 80, 20, 20, team="DET,CHI"))[0]
        self.assertEqual((r["points"], r["points_per_game"], r["team"], r["teams"]), (40, 0.5, "CHI", "DET,CHI"))

    def test_a_season_is_adjusted_to_todays_scoring(self):
        # a high-scoring era (1985-86) and the last five completed seasons as "today": the same line is worth less now
        rows = [season(i, 19851986, 80, 30, 50, pos="C") for i in range(1, 11)] + \
               [season(100 + i, s, 80, 15, 25, pos="C") for i in range(1, 11) for s in range(20212022, 20262026, 10001)]
        old = next(r for r in board(*rows) if r["player_id"] == 1)
        self.assertEqual(old["points"], 80)
        self.assertLess(old["adj_points"], 80)

    def test_tracked_stats_exist_only_where_the_data_does(self):
        rows = board(season(1, 20062007, 80, 10, 10), season(1, 19801981, 80, 10, 10),
                     defense={(1, 20062007): {"hits": 200, "blocked_shots": 90, "takeaways": 30, "giveaways": 40}})
        hits = ranked(rows, "hits")
        self.assertEqual([(r["season_id"], r["hits"]) for r in hits], [(20062007, 200)])  # the 1980-81 season has no hits and can't rank

    def test_ties_share_a_place_across_players(self):
        rows = board(season(1, 20101011, 80, 30, 40, name="A"), season(2, 20111012, 80, 30, 40, name="B"), season(3, 20121013, 80, 5, 5, name="C"),
                     season(4, 20131014, 80, 40, 40, name="D"))
        out = ranked(rows)
        self.assertEqual([(r["name"], r["place"], r["tied"]) for r in out], [("D", 1, False), ("A", 2, True), ("B", 2, True), ("C", 4, False)])

    def test_ascending_order_flips_the_list(self):
        rows = board(season(1, 20101011, 80, 30, 40, name="A"), season(2, 20111012, 80, 5, 5, name="B"))
        self.assertEqual([r["name"] for r in ranked(rows, direction="asc")], ["B", "A"])

    def test_per_game_leaders_need_enough_games_but_min_gp_overrides(self):
        rows = board(season(1, 20101011, 80, 20, 20, name="Full"), season(2, 20101011, 5, 6, 6, name="Cup of coffee"))
        self.assertEqual([r["name"] for r in ranked(rows, "points_per_game")], ["Full"])
        self.assertEqual([r["name"] for r in ranked(rows, "points_per_game", min_gp=1)], ["Cup of coffee", "Full"])
        self.assertEqual(len(ranked(rows, "points")), 2)  # counting stats take everyone

    def test_filters(self):
        rows = board(season(1, 19801981, 80, 30, 40, name="Old Star", pos="C", hof="Y"), season(2, 20231024, 80, 20, 30, name="New D", pos="D", active=20252026))
        self.assertEqual([r["name"] for r in ranked(rows, position="D")], ["New D"])
        self.assertEqual([r["name"] for r in ranked(rows, position="F")], ["Old Star"])
        self.assertEqual([r["name"] for r in ranked(rows, hof=True)], ["Old Star"])
        self.assertEqual([r["name"] for r in ranked(rows, active=True)], ["New D"])
        self.assertEqual([r["name"] for r in ranked(rows, q="star")], ["Old Star"])
        self.assertEqual([r["name"] for r in ranked(rows, season_from=2000)], ["New D"])
        self.assertEqual([r["name"] for r in ranked(rows, season_to=1990)], ["Old Star"])

    def test_sorting_by_name_or_season_just_numbers_the_rows(self):
        rows = board(season(1, 20101011, 80, 1, 1, name="B"), season(2, 20111012, 80, 1, 1, name="A"), season(3, 20111012, 80, 1, 1, name="C"))
        out = ranked(rows, "season_id", direction="asc")
        self.assertEqual([(r["place"], r["tied"]) for r in out], [(1, False), (2, False), (3, False)])
        self.assertEqual([r["name"] for r in ranked(rows, "name", direction="asc")], ["A", "B", "C"])

    def test_an_unknown_sort_is_refused(self):
        with self.assertRaises(ValueError):
            bs.query([], "skater", sort="hits_per_60")


class Goalies(unittest.TestCase):
    def g(self, pid, sid, gp, sv, gaa, wins=10, name="G"):
        return {"player_id": pid, "season_id": sid, "name": name, "team": "BOS", "birth_country": "USA", "hall_of_fame": None,
                "active_season": None, "games_played": gp, "games_started": gp, "wins": wins, "losses": 5, "ot_losses": 1, "shutouts": 2,
                "saves": 900, "shots_against": 1000, "goals_against": 100, "save_pct": sv, "gaa": gaa}

    def test_save_percentage_leaders_need_a_real_workload(self):
        b = bs.goalie_board([self.g(1, 20102011, 60, 0.93, 2.0, name="Starter"), self.g(2, 20102011, 4, 0.96, 1.2, name="Backup")], CURRENT)
        self.assertEqual([r["name"] for r in bs.query(b, "goalie", sort="save_pct")[0]], ["Starter"])

    def test_best_gaa_is_the_lowest_so_the_caller_asks_for_ascending(self):
        b = bs.goalie_board([self.g(1, 20102011, 60, 0.93, 2.4, name="A"), self.g(2, 20112012, 58, 0.92, 1.9, name="B")], CURRENT)
        self.assertEqual([r["name"] for r in bs.query(b, "goalie", sort="gaa", direction="asc")[0]], ["B", "A"])

    def test_the_current_season_and_goalies_with_no_games_are_left_out(self):
        b = bs.goalie_board([self.g(1, CURRENT, 10, 0.9, 2.5), self.g(2, 20102011, 0, None, None)], CURRENT)
        self.assertEqual(b, [])


if __name__ == "__main__":
    unittest.main()
