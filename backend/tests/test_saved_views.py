import unittest

import auth


class CleanQuery(unittest.TestCase):
    def test_filters_are_sorted_and_the_page_number_is_dropped(self):
        self.assertEqual(auth._clean_query("?sort=points&position=D&page=4&min_gp=300"),
                         "min_gp=300&position=D&sort=points")

    def test_blank_values_are_dropped(self):
        self.assertEqual(auth._clean_query("q=&sort=goals"), "sort=goals")

    def test_oversized_keys_and_values_are_dropped(self):
        long_key = "k" * (auth.MAX_KEY + 1)
        long_value = "v" * (auth.MAX_VALUE + 1)
        self.assertEqual(auth._clean_query(f"{long_key}=1&x={long_value}&ok=1"), "ok=1")

    def test_only_so_many_pairs_are_kept(self):
        q = "&".join(f"k{i:02d}=1" for i in range(auth.MAX_QUERY_PAIRS + 10))
        self.assertEqual(len(auth._clean_query(q).split("&")), auth.MAX_QUERY_PAIRS)

    def test_markup_is_encoded_not_kept_raw(self):
        out = auth._clean_query("sort=<script>alert(1)</script>")
        self.assertNotIn("<", out)
        self.assertTrue(out.startswith("sort="))

    def test_empty_is_fine(self):
        self.assertEqual(auth._clean_query(""), "")
        self.assertEqual(auth._clean_query("?"), "")

    def test_only_the_leaderboards_can_be_saved(self):
        self.assertEqual(auth.VIEW_PATHS, {"/skaters", "/goalies", "/alltime", "/alltime/skaters", "/alltime/goalies"})


class CleanWatch(unittest.TestCase):
    def test_players_need_a_numeric_id(self):
        self.assertEqual(auth.clean_watch(auth.WatchIn(kind="player", ref="8478402", name="  Connor   McDavid ")),
                         ("player", "8478402", "Connor McDavid"))
        self.assertIsNone(auth.clean_watch(auth.WatchIn(kind="player", ref="abc", name="x")))
        self.assertEqual(auth.clean_watch(auth.WatchIn(kind="prospect", ref="8485034", name="Joel Svensson")), ("prospect", "8485034", "Joel Svensson"))
        self.assertIsNone(auth.clean_watch(auth.WatchIn(kind="prospect", ref="abc", name="x")))

    def test_teams_are_uppercased_abbreviations(self):
        self.assertEqual(auth.clean_watch(auth.WatchIn(kind="team", ref="tor", name="Toronto")), ("team", "TOR", "Toronto"))
        self.assertIsNone(auth.clean_watch(auth.WatchIn(kind="team", ref="TORONTO", name="x")))

    def test_other_kinds_and_blank_names_are_rejected(self):
        self.assertIsNone(auth.clean_watch(auth.WatchIn(kind="coach", ref="1", name="x")))
        self.assertIsNone(auth.clean_watch(auth.WatchIn(kind="team", ref="TOR", name="   ")))


if __name__ == "__main__":
    unittest.main()
