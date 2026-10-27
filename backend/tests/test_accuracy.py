import datetime as dt
import random
import unittest

import accuracy as ac

D = dt.date


class Scores(unittest.TestCase):
    def test_brier_log_loss_and_pick(self):
        self.assertAlmostEqual(ac.brier(0.7, 1), 0.09)
        self.assertAlmostEqual(ac.brier(0.7, 0), 0.49)
        self.assertAlmostEqual(ac.log_loss(0.5, 1), 0.693147, places=5)
        self.assertGreater(ac.log_loss(0.0, 1), ac.log_loss(0.1, 1))        # clipped, not infinite
        self.assertEqual(ac.pick_credit(0.6, 1), 1.0)
        self.assertEqual(ac.pick_credit(0.4, 1), 0.0)
        self.assertEqual(ac.pick_credit(0.5, 1), 0.5)

    def test_a_coin_flip_scores_a_quarter(self):
        s = ac.summarize([(0.5, 1), (0.5, 0), (0.5, 1), (0.5, 0)])
        self.assertAlmostEqual(s["brier"], 0.25)
        self.assertAlmostEqual(s["accuracy"], 0.5)
        self.assertEqual(ac.summarize([])["n"], 0)

    def test_paired_difference_and_its_interval(self):
        self.assertIsNone(ac.paired([1.0], [2.0]))
        better = ac.paired([0.2] * 50, [0.3] * 50)
        self.assertAlmostEqual(better["mean"], -0.1)
        self.assertEqual((better["low"], better["high"]), (better["mean"], better["mean"]))   # no spread
        noisy = ac.paired([0.1, 0.5, 0.2, 0.4], [0.3, 0.3, 0.3, 0.3])
        self.assertLess(noisy["low"], 0)
        self.assertGreater(noisy["high"], 0)                                                  # can't tell them apart

    def test_calibration_bins(self):
        preds = [(0.42, 1), (0.43, 0), (0.58, 1), (0.52, 1), (0.52, 0), (0.0, 0), (1.0, 1)]
        bins = ac.calibration(preds)
        by = {(b["lo"], b["hi"]): b for b in bins}
        self.assertEqual(by[(0.40, 0.45)]["n"], 2)
        self.assertAlmostEqual(by[(0.40, 0.45)]["rate"], 0.5)
        self.assertEqual(by[(0.50, 0.55)]["n"], 2)
        self.assertEqual(by[(0.60, 1.0)]["n"], 1)      # a prediction of exactly 1.0 lands in the top bin
        self.assertEqual(by[(0.0, 0.40)]["n"], 1)


def season(n_days=14, seed=1):
    """A little league: 4 teams, 2 games a day, with a strong team A. Returns (games, shots)."""
    rnd = random.Random(seed)
    teams = ["A", "B", "C", "D"]
    strength = {"A": 1.4, "B": 1.0, "C": 1.0, "D": 0.7}
    games, shots, gid = [], {}, 1
    for day in range(n_days):
        order = teams[:]
        rnd.shuffle(order)
        for home, away in ((order[0], order[1]), (order[2], order[3])):
            hx, ax = 3.0 * strength[home] / strength[away] ** 0.5, 3.0 * strength[away] / strength[home] ** 0.5
            hs, as_ = int(rnd.random() < hx / (hx + ax)) * 2 + rnd.randint(0, 2), rnd.randint(0, 3)
            if hs == as_:
                hs += 1
            games.append({"game_id": gid, "date": D(2026, 10, 1) + dt.timedelta(days=day), "home": home, "away": away, "home_score": hs, "away_score": as_})
            shots[(gid, home)] = {"xgf": hx, "xga": ax}
            shots[(gid, away)] = {"xgf": ax, "xga": hx}
            shots[(gid, None)] = {"goals": hs + as_, "sog": 56}
            gid += 1
    return games, shots


class WinReplay(unittest.TestCase):
    def test_games_without_enough_history_are_not_predicted(self):
        games, shots = season()
        rows = ac.win_replay(games, shots, min_games=4)
        self.assertTrue(rows)
        first_predicted = min(r["date"] for r in rows)
        self.assertGreater(first_predicted, games[0]["date"])
        self.assertLess(len(rows), len(games))

    def test_no_peeking_a_prediction_ignores_everything_after_its_day(self):
        games, shots = season(n_days=14)
        full = {r["game_id"]: r for r in ac.win_replay(games, shots)}
        cut_day = D(2026, 10, 9)
        early = [g for g in games if g["date"] <= cut_day]
        part = {r["game_id"]: r for r in ac.win_replay(early, shots)}
        self.assertTrue(part)
        for gid, r in part.items():
            for k in ("model", "home_ice", "goals_model"):
                self.assertAlmostEqual(full[gid][k], r[k], msg=f"game {gid} {k}")

    def test_changing_a_games_own_result_does_not_change_its_prediction(self):
        games, shots = season()
        base = {r["game_id"]: r["model"] for r in ac.win_replay(games, shots)}
        target = next(g for g in games if g["game_id"] in base)
        altered = [dict(g, home_score=g["home_score"] + 5) if g["game_id"] == target["game_id"] else g for g in games]
        changed = {r["game_id"]: r["model"] for r in ac.win_replay(altered, shots)}
        self.assertAlmostEqual(base[target["game_id"]], changed[target["game_id"]])

    def test_stronger_team_is_favored_and_baselines_are_present(self):
        games, shots = season(n_days=20)
        rows = ac.win_replay(games, shots)
        a_home = [r["model"] for r in rows if r["home"] == "A" and r["away"] == "D"]
        d_home = [r["model"] for r in rows if r["home"] == "D" and r["away"] == "A"]
        if a_home and d_home:
            self.assertGreater(min(a_home), max(d_home))
        for r in rows:
            self.assertEqual(r["coin"], 0.5)
            self.assertTrue(0 < r["home_ice"] < 1 and 0 < r["goals_model"] < 1 and 0 < r["model"] < 1)

    def test_report_has_every_model_and_a_paired_comparison(self):
        games, shots = season(n_days=20)
        rep = ac.win_report(ac.win_replay(games, shots))
        self.assertEqual(set(rep["models"]), {"model", "coin", "home_ice", "goals_model"})
        self.assertAlmostEqual(rep["models"]["coin"]["brier"], 0.25)
        self.assertEqual(set(rep["vs"]), {"coin", "home_ice", "goals_model"})
        self.assertGreater(rep["games"], 0)
        self.assertTrue(ac.win_report([])["games"] == 0)


def starts(plan):
    """plan: {team: [starter per day]} -> team_games rows, one game a day from 2026-10-01."""
    out = []
    for t, (team, seq) in enumerate(plan.items()):
        for i, s in enumerate(seq):
            out.append({"game_id": t * 100 + i + 1, "date": D(2026, 10, 1) + dt.timedelta(days=i), "team": team, "starter": s})
    return out


class GoalieReplay(unittest.TestCase):
    def test_a_clear_number_one_is_predicted(self):
        plan = {"AAA": [1, 1, 1, 1, 1, 1, 1, 1], "BBB": [2, 2, 2, 2, 2, 2, 2, 2]}
        rows = ac.goalie_replay(starts(plan))
        self.assertTrue(rows)
        self.assertTrue(all(r["top"] == r["starter"] for r in rows))

    def test_the_first_games_are_not_predicted(self):
        rows = ac.goalie_replay(starts({"AAA": [1, 1, 1, 1, 1]}), min_history=3)
        self.assertEqual(len(rows), 2)

    def test_a_new_goalie_the_model_never_saw_gets_no_probability(self):
        rows = ac.goalie_replay(starts({"AAA": [1, 1, 1, 1, 9]}))
        last = rows[-1]
        self.assertEqual(last["starter"], 9)
        self.assertEqual(last["p_actual"], 0.0)
        self.assertNotEqual(last["top"], 9)

    def test_back_to_backs_are_flagged_from_the_previous_days_game(self):
        rows = ac.goalie_replay(starts({"AAA": [1, 1, 1, 2, 1, 1]}))
        self.assertTrue(all(r["tired"] for r in rows))             # a game every day

    def test_no_peeking(self):
        plan = {"AAA": [1, 1, 2, 1, 1, 2, 1, 1, 1, 2], "BBB": [3, 3, 3, 4, 3, 3, 3, 4, 3, 3]}
        full = {r["game_id"]: r for r in ac.goalie_replay(starts(plan))}
        cut = {team: seq[:7] for team, seq in plan.items()}
        part = ac.goalie_replay(starts(cut))
        self.assertTrue(part)
        for r in part:
            self.assertEqual(r["top"], full[r["game_id"]]["top"])
            self.assertAlmostEqual(r["p_actual"], full[r["game_id"]]["p_actual"])

    def test_report_splits_back_to_backs_and_rested(self):
        plan = {"AAA": [1, 1, 1, 1, 1, 1], "BBB": [2, 2, 2, 2, 2, 2]}
        rep = ac.goalie_report(ac.goalie_replay(starts(plan)))
        self.assertEqual(rep["games"], rep["all"]["n"])
        self.assertEqual(rep["all"]["n"], rep["back_to_back"]["n"] + rep["rested"]["n"])
        self.assertEqual(rep["all"]["top_correct"], 1.0)
        self.assertEqual(ac.goalie_report([])["games"], 0)


if __name__ == "__main__":
    unittest.main()
