import unittest

import prospects


def pros(pid, name, year=2026, overall=10, team="NYR"):
    return {"player_id": pid, "name": name, "draft_year": year, "draft_round": 1, "draft_pick": overall, "draft_overall": overall, "draft_team": team}


class MatchKey(unittest.TestCase):
    def test_accents_punctuation_case_and_suffixes_are_ignored(self):
        self.assertEqual(prospects.match_key("Zachary L'Heureux Jr."), prospects.match_key("zachary lheureux"))
        self.assertEqual(prospects.match_key("Pyotr Kochetkov"), "pyotr kochetkov")
        self.assertEqual(prospects.match_key("Jesper Bratt"), prospects.match_key("JESPER  BRATT"))
        self.assertEqual(prospects.match_key("Mathieu Perreault"), prospects.match_key("Mathieu Perréault"))

    def test_hyphens_split_words(self):
        self.assertEqual(prospects.match_key("Jean-Luc Foudy"), "jean luc foudy")

    def test_empty(self):
        self.assertEqual(prospects.match_key(None), "")


class LinkRankings(unittest.TestCase):
    def test_a_ranked_name_matching_one_prospect_of_that_class_is_linked_with_its_draft_slot(self):
        rows = [{"name": "Ivan Demidov"}, {"name": "Someone Else"}]
        n = prospects.link_rankings(rows, [pros(1, "Ivan Demidov", overall=5, team="MTL")], 2026)
        self.assertEqual(n, 1)
        self.assertEqual(rows[0]["prospect_id"], 1)
        self.assertEqual(rows[0]["draft"]["overall"], 5)
        self.assertEqual(rows[0]["draft"]["team"], "MTL")
        self.assertNotIn("prospect_id", rows[1])

    def test_a_prospect_from_another_draft_year_is_not_a_match(self):
        rows = [{"name": "Ivan Demidov"}]
        self.assertEqual(prospects.link_rankings(rows, [pros(1, "Ivan Demidov", year=2024)], 2026), 0)
        self.assertNotIn("prospect_id", rows[0])

    def test_two_prospects_with_one_name_in_a_class_are_left_unlinked(self):
        rows = [{"name": "Sam Smith"}]
        self.assertEqual(prospects.link_rankings(rows, [pros(1, "Sam Smith"), pros(2, "Sam Smith")], 2026), 0)

    def test_two_ranked_rows_with_one_name_are_left_unlinked(self):
        rows = [{"name": "Sam Smith"}, {"name": "Sam Smith"}]
        self.assertEqual(prospects.link_rankings(rows, [pros(1, "Sam Smith")], 2026), 0)

    def test_a_missing_year_links_nothing(self):
        rows = [{"name": "Ivan Demidov"}]
        self.assertEqual(prospects.link_rankings(rows, [pros(1, "Ivan Demidov")], None), 0)


if __name__ == "__main__":
    unittest.main()
