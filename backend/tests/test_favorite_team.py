import unittest

import auth


class CleanTeam(unittest.TestCase):
    def test_abbreviations_are_upper_cased_and_trimmed(self):
        self.assertEqual(auth.clean_team("edm"), "EDM")
        self.assertEqual(auth.clean_team(" Nyr "), "NYR")

    def test_empty_and_missing_give_none(self):
        self.assertIsNone(auth.clean_team(None))
        self.assertIsNone(auth.clean_team(""))
        self.assertIsNone(auth.clean_team("   "))

    def test_anything_not_shaped_like_an_abbreviation_is_rejected(self):
        for bad in ("E", "EDMX", "E1M", "ED M", "<script>", "'; DROP TABLE app_user;--"):
            self.assertIsNone(auth.clean_team(bad), bad)


if __name__ == "__main__":
    unittest.main()
