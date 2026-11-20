import unittest

import seasonpages


def team(abbrev, tid):
    return {"id": tid, "abbrev": abbrev, "name": {"default": abbrev + " name"}}


class EndDate(unittest.TestCase):
    def test_finds_the_season(self):
        payload = {"seasons": [{"id": 20222023, "standingsEnd": "2023-04-14"}]}
        self.assertEqual(seasonpages.end_date(payload, 20222023), "2023-04-14")

    def test_unlisted_season_is_none(self):
        self.assertIsNone(seasonpages.end_date({"seasons": []}, 20042005))


class Standings(unittest.TestCase):
    def row(self, abbrev, pts, league, **kw):
        return {"teamAbbrev": {"default": abbrev}, "teamName": {"default": abbrev + " name"}, "points": pts, "leagueSequence": league,
                "gamesPlayed": 82, "wins": 40, "losses": 30, "otLosses": 12, **kw}

    def test_sorted_by_league_rank(self):
        out = seasonpages.standings({"standings": [self.row("B", 90, 2), self.row("A", 100, 1)]})
        self.assertEqual([r["abbrev"] for r in out], ["A", "B"])

    def test_missing_rank_falls_back_to_points(self):
        out = seasonpages.standings({"standings": [self.row("B", 90, 0), self.row("A", 100, 0)]})
        self.assertEqual([r["abbrev"] for r in out], ["A", "B"])
        self.assertIsNone(out[0]["league_rank"])

    def test_zero_rank_fields_become_none(self):
        row = seasonpages.standings_row(self.row("A", 100, 1, divisionSequence=0, conferenceSequence=0))
        self.assertIsNone(row["division_rank"])
        self.assertIsNone(row["conference_rank"])

    def test_empty(self):
        self.assertEqual(seasonpages.standings({"standings": []}), [])


class Playoffs(unittest.TestCase):
    def series(self, rnd, letter, top, bottom, won, title="Round"):
        return {"playoffRound": rnd, "seriesLetter": letter, "seriesTitle": title, "winningTeamId": won,
                "topSeedTeam": top, "bottomSeedTeam": bottom, "topSeedWins": 4, "bottomSeedWins": 2,
                "topSeedRankAbbrev": "D1", "bottomSeedRankAbbrev": "WC1"}

    def test_rounds_in_order_and_champion(self):
        a, b = team("AAA", 1), team("BBB", 2)
        payload = {"series": [self.series(2, "C", a, b, 1, "Final"), self.series(1, "B", b, a, 2), self.series(1, "A", a, b, 1)]}
        out = seasonpages.playoffs(payload)
        self.assertEqual([r["round"] for r in out["rounds"]], [1, 2])
        self.assertEqual([s["letter"] for s in out["rounds"][0]["series"]], ["A", "B"])
        self.assertEqual(out["rounds"][0]["series"][1]["winner"], "BBB")
        self.assertEqual(out["champion"], "AAA name")

    def test_no_bracket(self):
        self.assertEqual(seasonpages.playoffs({"series": []}), {"rounds": [], "champion": None})

    def test_unfinished_series_has_no_winner(self):
        a, b = team("AAA", 1), team("BBB", 2)
        out = seasonpages.playoffs({"series": [self.series(1, "A", a, b, None)]})
        self.assertIsNone(out["rounds"][0]["series"][0]["winner"])
        self.assertIsNone(out["champion"])


if __name__ == "__main__":
    unittest.main()
