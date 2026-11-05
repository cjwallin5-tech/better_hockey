import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import config
import ingest
import rollover as ro

CONFIG = """import os

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=hockey_stats")
SEASON_ID = int(os.environ.get("SEASON_ID", "20262027"))
GAME_TYPE = 2
"""


class Seasons(unittest.TestCase):
    def test_a_valid_season_id(self):
        self.assertEqual(ro.parse_season("20272028"), 20272028)

    def test_rejects_malformed_or_non_consecutive_ids(self):
        for bad in ("2027", "2027-28", "20272029", "20282027", "", None, "2027202x"):
            with self.assertRaises(ValueError):
                ro.parse_season(bad)

    def test_the_previous_season(self):
        self.assertEqual(ro.previous_season(20272028), 20262027)


class RewriteConfig(unittest.TestCase):
    def test_changes_only_the_default_and_reports_the_old_one(self):
        text, old = ro.rewrite_config(CONFIG, 20272028)
        self.assertEqual(old, 20262027)
        self.assertIn('SEASON_ID = int(os.environ.get("SEASON_ID", "20272028"))', text)
        self.assertEqual(text.replace("20272028", "20262027"), CONFIG)

    def test_running_it_again_is_harmless(self):
        once, _ = ro.rewrite_config(CONFIG, 20272028)
        twice, old = ro.rewrite_config(once, 20272028)
        self.assertEqual(once, twice)
        self.assertEqual(old, 20272028)

    def test_a_config_without_the_line_is_an_error(self):
        with self.assertRaises(ValueError):
            ro.rewrite_config("DATABASE_URL = 'x'\n", 20272028)

    def test_the_real_config_has_the_line(self):
        text = (ro.HERE / "config.py").read_text()
        self.assertIsInstance(ro.rewrite_config(text, 20272028)[1], int)


class CheckFinished(unittest.TestCase):
    def test_a_complete_finished_season_has_no_problems(self):
        self.assertEqual(ro.check_finished(1344, 1344, 1344, True), [])

    def test_unfinished_games_are_a_problem(self):
        self.assertTrue(any("not final" in p for p in ro.check_finished(1344, 1200, 1344, True)))

    def test_a_short_schedule_is_a_problem(self):
        self.assertTrue(any("a full season is 1344" in p for p in ro.check_finished(1300, 1300, 1344, True)))

    def test_nothing_stored_is_a_problem(self):
        self.assertEqual(len(ro.check_finished(0, 0, 1344)), 1)

    def test_stats_refreshed_before_the_last_game_are_a_problem_but_unknown_is_not(self):
        self.assertTrue(any("nightly ingest" in p for p in ro.check_finished(1344, 1344, 1344, False)))
        self.assertEqual(ro.check_finished(1344, 1344, 1344, None), [])


class CheckHistory(unittest.TestCase):
    def test_full_counts_have_no_warnings(self):
        full = {"team_rows": 2688, "skater_games": 1344, "shot_games": 1344, "onice_games": 1344}
        self.assertEqual(ro.check_history(full, 1344), [])

    def test_short_counts_are_named(self):
        out = ro.check_history({"team_rows": 2688, "skater_games": 1344, "shot_games": 900, "onice_games": 0}, 1344)
        self.assertEqual(len(out), 2)
        self.assertTrue(any(w.startswith("shot_games: 900") for w in out))
        self.assertTrue(any(w.startswith("onice_games: 0") for w in out))


class Plan(unittest.TestCase):
    def test_default_order_runs_shots_before_the_passes_that_annotate_them(self):
        names = ro.plan()
        self.assertEqual(names[0], "ingest")
        self.assertLess(names.index("shots"), names.index("shot-locations"))
        self.assertLess(names.index("shots"), names.index("shot-times"))
        self.assertEqual(names[-1], "markers")

    def test_skip_and_only(self):
        self.assertNotIn("edge", ro.plan(skip={"edge"}))
        self.assertEqual(ro.plan(only="onice"), ["onice"])
        self.assertEqual(ro.plan(skip={"onice"}, only="onice"), [])

    def test_every_step_names_a_real_ingest_command(self):
        import re
        src = (ro.HERE / "ingest.py").read_text()
        for name, args, _ in ro.STEPS:
            if args:
                self.assertIn(f'"{args[0]}"', src)


class RunStep(unittest.TestCase):
    def fake_ingest(self, body):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        Path(d.name, "ingest.py").write_text(body)
        return Path(d.name)

    def test_the_new_season_reaches_the_step_and_its_output_is_logged(self):
        here = self.fake_ingest('import os, sys\nprint("season", os.environ["SEASON_ID"], "args", sys.argv[1:])\n')
        log = io.StringIO()
        with mock.patch.object(ro, "HERE", here), mock.patch("sys.stdout", new=io.StringIO()):
            rc = ro.run_step("shots", ["backfill-shots"], 20272028, log)
        self.assertEqual(rc, 0)
        self.assertIn("season 20272028 args ['backfill-shots']", log.getvalue())

    def test_a_failing_step_returns_its_exit_code(self):
        here = self.fake_ingest("import sys\nprint('boom')\nsys.exit(3)\n")
        with mock.patch.object(ro, "HERE", here), mock.patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(ro.run_step("x", [], 20272028, io.StringIO()), 3)


class ScheduleLength(unittest.TestCase):
    def test_82_game_seasons_up_to_2025_26_and_84_after(self):
        self.assertEqual(config.regular_season_games(20252026), 1312)
        self.assertEqual(config.regular_season_games(20262027), 1344)
        self.assertEqual(config.regular_season_games(20272028), 1344)
        self.assertEqual(1344, 32 * config.GAMES_PER_SEASON // 2)

    def test_history_windows_cover_every_game_of_an_84_game_season(self):
        windows = ingest.game_windows(config.regular_season_games(20262027))
        covered = {n for lo, hi in windows for n in range(lo, hi)}
        self.assertTrue(set(range(1, 1345)) <= covered)
        self.assertEqual(windows[0][0], 1)
        # the old fixed 1312-game range would have missed the last 32 games
        old = {n for lo, hi in ingest.game_windows(1312) for n in range(lo, hi)}
        self.assertFalse(set(range(1313, 1345)) <= old)

    def test_windows_do_not_overlap(self):
        windows = ingest.game_windows(1344)
        for (_, hi), (lo, _) in zip(windows, windows[1:]):
            self.assertEqual(hi, lo)


if __name__ == "__main__":
    unittest.main()
