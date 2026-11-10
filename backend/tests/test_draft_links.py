import unittest

import prospects


def pros(pid, name, year=2026, overall=10, team="NYR", born=None):
    return {"player_id": pid, "name": name, "draft_year": year, "draft_round": 1, "draft_pick": overall, "draft_overall": overall,
            "draft_team": team, "birth_date": born}


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

    def test_a_different_spelling_of_the_first_name_links_by_birth_date_and_last_name(self):
        import datetime as dt
        rows = [{"name": "Ilya Morozov", "birth_date": "2008-03-01"}, {"name": "Teddy Lechner", "birth_date": "2007-11-09"}]
        known = [pros(1, "Ilia Morozov", overall=20, born=dt.date(2008, 3, 1)), pros(2, "Theodore Lechner", overall=152, born=dt.date(2007, 11, 9))]
        self.assertEqual(prospects.link_rankings(rows, known, 2026), 2)
        self.assertEqual([r["prospect_id"] for r in rows], [1, 2])
        self.assertEqual(rows[0]["draft"]["overall"], 20)

    def test_a_transliterated_last_name_links_when_the_birth_date_agrees(self):
        import datetime as dt
        rows = [{"name": "Oleg Kulebyakin", "birth_date": "2008-01-11"}, {"name": "Danay Shayikov", "birth_date": "2007-04-13"}]
        known = [pros(1, "Oleg Kulebiakin", overall=52, born=dt.date(2008, 1, 11)), pros(2, "Danai Shaiikov", overall=67, born=dt.date(2007, 4, 13))]
        self.assertEqual(prospects.link_rankings(rows, known, 2026), 2)

    def test_people_who_only_share_a_birthday_are_not_linked(self):
        import datetime as dt
        rows = [{"name": "Cameron Allard", "birth_date": "2008-01-11"}, {"name": "Ivan Matta", "birth_date": "2008-01-11"}]
        known = [pros(1, "Oleg Kulebiakin", overall=52, born=dt.date(2008, 1, 11))]
        self.assertEqual(prospects.link_rankings(rows, known, 2026), 0)

    def test_two_equally_good_candidates_are_left_unlinked(self):
        import datetime as dt
        rows = [{"name": "Max Smith", "birth_date": "2008-01-11"}]
        known = [pros(1, "Max Smyth", overall=5, born=dt.date(2008, 1, 11)), pros(2, "Max Smeth", overall=6, born=dt.date(2008, 1, 11))]
        self.assertEqual(prospects.link_rankings(rows, known, 2026), 0)

    def test_same_person_compares_last_names_then_overall_similarity(self):
        self.assertTrue(prospects.same_person("Ilya Morozov", "Ilia Morozov"))
        self.assertTrue(prospects.same_person("Oleg Kulebyakin", "Oleg Kulebiakin"))
        self.assertFalse(prospects.same_person("Cameron Allard", "Oleg Kulebiakin"))
        self.assertFalse(prospects.same_person("", "Oleg Kulebiakin"))

    def test_the_same_last_name_with_a_different_birth_date_is_a_different_person(self):
        import datetime as dt
        rows = [{"name": "Reed Brown", "birth_date": "2008-01-02"}, {"name": "Nathan Brown", "birth_date": "2008-02-03"}]
        known = [pros(9, "Ryan Brown", overall=155, born=dt.date(2007, 12, 25))]
        self.assertEqual(prospects.link_rankings(rows, known, 2026), 0)
        self.assertNotIn("prospect_id", rows[0])

    def test_one_prospect_is_never_linked_to_two_rows(self):
        import datetime as dt
        rows = [{"name": "Zac Olsen", "birth_date": "2008-04-05"}, {"name": "Zack Olsen", "birth_date": "2008-04-05"}]
        known = [pros(5, "Zach Olsen", overall=73, born=dt.date(2008, 4, 5))]
        self.assertEqual(prospects.link_rankings(rows, known, 2026), 1)
        self.assertEqual(sum(1 for r in rows if r.get("prospect_id")), 1)

    def test_an_exact_name_wins_over_a_birth_date_match(self):
        import datetime as dt
        rows = [{"name": "Ivan Demidov", "birth_date": "2008-01-01"}]
        known = [pros(1, "Ivan Demidov", overall=5, born=dt.date(2008, 1, 1)), pros(2, "Ivar Demidov", overall=6, born=dt.date(2008, 1, 1))]
        self.assertEqual(prospects.link_rankings(rows, known, 2026), 1)
        self.assertEqual(rows[0]["prospect_id"], 1)

    def test_rows_without_a_birth_date_or_prospects_without_one_cannot_use_the_second_pass(self):
        rows = [{"name": "Ilya Morozov"}]
        self.assertEqual(prospects.link_rankings(rows, [pros(1, "Ilia Morozov", born=None)], 2026), 0)
        self.assertEqual(prospects.link_rankings([{"name": "Ilya Morozov", "birth_date": "2008-03-01"}], [pros(1, "Ilia Morozov", born=None)], 2026), 0)

    def test_a_missing_year_links_nothing(self):
        rows = [{"name": "Ivan Demidov"}]
        self.assertEqual(prospects.link_rankings(rows, [pros(1, "Ivan Demidov")], None), 0)


if __name__ == "__main__":
    unittest.main()
