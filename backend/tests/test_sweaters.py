import unittest

import sweaters


def player(pid, first, last, number, pos="C"):
    return {"id": pid, "firstName": {"default": first}, "lastName": {"default": last}, "sweaterNumber": number, "positionCode": pos}


class RosterRowsTest(unittest.TestCase):
    def test_every_group_is_read_and_players_without_a_number_are_skipped(self):
        payload = {"forwards": [player(1, "A", "One", 9)], "defensemen": [player(2, "B", "Two", None, "D")], "goalies": [player(3, "C", "Three", 30, "G")]}
        self.assertEqual(sweaters.roster_rows(payload, 20242025, "EDM"),
                         [(1, 20242025, "EDM", 9, "A One", "C"), (3, 20242025, "EDM", 30, "C Three", "G")])

    def test_a_missing_group_is_fine(self):
        self.assertEqual(sweaters.roster_rows({}, 19171918, "MTL"), [])


class StintsTest(unittest.TestCase):
    def test_consecutive_seasons_with_one_team_make_one_stint(self):
        self.assertEqual(sweaters.stints([(20002001, "PIT"), (20012002, "PIT"), (20022003, "PIT")]),
                         [{"team": "PIT", "from": 20002001, "to": 20022003}])

    def test_a_gap_or_a_new_team_starts_a_new_stint(self):
        got = sweaters.stints([(20012002, "PIT"), (20002001, "PIT"), (20042005, "PIT"), (20052006, "BOS")])
        self.assertEqual([(s["team"], s["from"], s["to"]) for s in got],
                         [("PIT", 20002001, 20012002), ("PIT", 20042005, 20042005), ("BOS", 20052006, 20052006)])


class WearersTest(unittest.TestCase):
    def test_players_are_grouped_and_ordered_by_first_season(self):
        rows = [(2, 20102011, "EDM", "Late Guy", "C"), (1, 19901991, "EDM", "Early Guy", "C"), (1, 19911992, "EDM", "Early Guy", "C")]
        got = sweaters.wearers(rows)
        self.assertEqual([w["name"] for w in got], ["Early Guy", "Late Guy"])
        self.assertEqual(got[0]["stints"], [{"team": "EDM", "from": 19901991, "to": 19911992}])


if __name__ == "__main__":
    unittest.main()
