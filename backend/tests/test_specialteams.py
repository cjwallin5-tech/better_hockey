import unittest

import specialteams as st


def pl(name, pos, games=8, pp=None, pk=None):
    return {"name": name, "position": pos, "games": games, "pp_share": pp, "pk_share": pk}


class PowerPlay(unittest.TestCase):
    def test_top_unit_then_second_unit_by_share(self):
        players = [pl("A", "C", pp=0.8), pl("B", "L", pp=0.7), pl("C", "R", pp=0.6), pl("D1", "D", pp=0.6), pl("D2", "D", pp=0.5),
                   pl("E", "C", pp=0.3), pl("F", "L", pp=0.2), pl("G", "D", pp=0.1)]
        units = st.power_play_units(players)
        self.assertEqual([u["unit"] for u in units], ["PP1", "PP2"])
        self.assertEqual([p["name"] for p in units[0]["players"]], ["A", "B", "C", "D1", "D2"])
        self.assertEqual([p["name"] for p in units[1]["players"]], ["E", "F"])   # G is below the second-unit cut-off

    def test_a_top_unit_is_capped_at_five_and_overflow_drops_to_the_second(self):
        players = [pl(str(i), "C", pp=0.9 - i * 0.01) for i in range(7)]
        units = st.power_play_units(players)
        self.assertEqual(len(units[0]["players"]), 5)
        self.assertEqual(len(units[1]["players"]), 2)

    def test_call_ups_and_players_with_no_power_play_time_are_left_out(self):
        players = [pl("Call-up", "C", games=1, pp=0.9), pl("Never", "C", pp=0), pl("Real", "C", pp=0.7)]
        units = st.power_play_units(players)
        self.assertEqual([p["name"] for p in units[0]["players"]], ["Real"])
        self.assertEqual(len(units), 1)

    def test_nobody_gives_no_units(self):
        self.assertEqual(st.power_play_units([]), [])


class PenaltyKill(unittest.TestCase):
    def test_forwards_and_defense_are_ranked_separately_two_per_unit(self):
        players = [pl("F1", "C", pk=0.5), pl("F2", "L", pk=0.45), pl("F3", "R", pk=0.3), pl("F4", "C", pk=0.25),
                   pl("D1", "D", pk=0.6), pl("D2", "D", pk=0.5), pl("D3", "D", pk=0.4), pl("D4", "D", pk=0.3)]
        units = st.penalty_kill_units(players)
        self.assertEqual([p["name"] for p in units[0]["players"]], ["F1", "F2", "D1", "D2"])
        self.assertEqual([p["name"] for p in units[1]["players"]], ["F3", "F4", "D3", "D4"])

    def test_a_player_below_the_floor_is_not_in_a_unit(self):
        players = [pl("F1", "C", pk=0.5), pl("F2", "L", pk=0.45), pl("F3", "R", pk=0.05), pl("D1", "D", pk=0.6)]
        units = st.penalty_kill_units(players)
        self.assertEqual(len(units), 1)
        self.assertEqual([p["name"] for p in units[0]["players"]], ["F1", "F2", "D1"])


class TeamFigures(unittest.TestCase):
    def test_per_60_rates_and_per_game_time(self):
        line = st.team_line({"games": 10, "pp_sec": 3000.0, "sh_sec": 2400.0, "pp_xg": 5.0, "pp_goals": 4, "pp_shots": 50,
                             "pk_xg": 3.0, "pk_goals": 2, "pk_shots": 30})
        self.assertAlmostEqual(line["pp_toi_pg"], 300)
        self.assertAlmostEqual(line["pp_xgf60"], 6.0)    # 5 xG in 50 minutes
        self.assertAlmostEqual(line["pk_xga60"], 4.5)    # 3 xG against in 40 minutes
        self.assertAlmostEqual(line["pk_ga60"], 3.0)

    def test_no_time_means_no_rate(self):
        line = st.team_line({"games": 0, "pp_sec": 0.0, "sh_sec": 0.0, "pp_xg": 0, "pp_goals": 0, "pp_shots": 0,
                             "pk_xg": 0, "pk_goals": 0, "pk_shots": 0})
        self.assertIsNone(line["pp_xgf60"])
        self.assertIsNone(line["pp_toi_pg"])


class Ranks(unittest.TestCase):
    def test_rank_one_is_best_in_either_direction(self):
        rows = [{"a": 1.0, "b": 5.0}, {"a": 3.0, "b": 2.0}, {"a": None, "b": 9.0}]
        st.rank_by(rows, "a", high_is_good=True)
        st.rank_by(rows, "b", high_is_good=False)
        self.assertEqual([r["a_rank"] for r in rows], [2, 1, None])
        self.assertEqual([r["b_rank"] for r in rows], [2, 1, 3])


if __name__ == "__main__":
    unittest.main()
