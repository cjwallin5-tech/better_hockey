import unittest

import franchise

NOW = 20262027


def row(season, **kw):
    base = {"seasonId": season, "gameTypeId": 2, "gamesPlayed": 82, "wins": 41, "losses": 30, "ties": None, "overtimeLosses": 11, "points": 93,
            "inPlayoffs": False, "decision": None, "playoffRound": None, "finalPlayoffRound": None, "seriesTitle": None,
            "divisionSequence": 2, "conferenceSequence": 5, "leagueSequence": 14, "teamName": "Edmonton Oilers"}
    return {**base, **kw}


class PlayoffResultTest(unittest.TestCase):
    def test_missed_the_playoffs(self):
        self.assertEqual(franchise.playoff_result(row(20192020), NOW)["text"], "Missed the playoffs")

    def test_winning_the_last_series_of_the_playoffs_wins_the_cup(self):
        won = row(19871988, inPlayoffs=True, decision="W", playoffRound=4, finalPlayoffRound=4, seriesTitle="Stanley Cup Final")
        out = franchise.playoff_result(won, NOW)
        self.assertEqual((out["champion"], out["text"]), (True, "Won the Stanley Cup"))

    def test_an_era_with_two_rounds_still_has_a_final(self):
        won = row(19621963, inPlayoffs=True, decision="W", playoffRound=2, finalPlayoffRound=2, seriesTitle="Stanley Cup Final")
        self.assertTrue(franchise.playoff_result(won, NOW)["champion"])

    def test_a_loss_names_the_series(self):
        lost = row(20212022, inPlayoffs=True, decision="L", playoffRound=1, finalPlayoffRound=4, seriesTitle="1st Round")
        out = franchise.playoff_result(lost, NOW)
        self.assertEqual((out["champion"], out["text"]), (False, "Lost in the 1st Round"))

    def test_the_season_in_progress_has_no_result(self):
        self.assertEqual(franchise.playoff_result(row(NOW), NOW), {"made": None, "champion": False, "text": None})


class RecordTextTest(unittest.TestCase):
    def test_overtime_losses_era(self):
        self.assertEqual(franchise.record_text(row(20232024)), "41-30-11")

    def test_ties_era(self):
        self.assertEqual(franchise.record_text(row(19731974, ties=12, overtimeLosses=None)), "41-30-12")

    def test_both_ties_and_overtime_losses(self):
        self.assertEqual(franchise.record_text(row(20002001, ties=8, overtimeLosses=4)), "41-30-8-4")


class HistoryTest(unittest.TestCase):
    def test_summary_and_newest_first(self):
        f = {"id": 25, "fullName": "Edmonton Oilers", "firstSeasonId": 19791980, "lastSeasonId": None}
        totals = [{"gameTypeId": 2, "gamesPlayed": 3668, "wins": 1723, "losses": 1476, "ties": 262, "overtimeLosses": 207, "points": 3915, "cups": 5},
                  {"gameTypeId": 3, "gamesPlayed": 353, "wins": 205, "losses": 148, "ties": None, "overtimeLosses": 0, "points": 74, "cups": 5}]
        out = franchise.history(f, totals, {"stanleyCupWins": 5, "playoffSeasons": 28, "stanleyCupAppearances": 7},
                                [row(20232024), row(20242025), row(20242025, gameTypeId=3)], NOW)
        self.assertEqual([s["season_id"] for s in out["by_season"]], [20242025, 20232024])
        self.assertEqual((out["cups"], out["playoff_appearances"], out["seasons"]), (5, 28, 2))
        self.assertEqual(out["regular"]["wins"], 1723)
        self.assertEqual(out["playoffs"]["wins"], 205)

    def test_ranks_are_none_when_the_era_had_none(self):
        s = franchise.season_view(row(19331934, divisionSequence=0, conferenceSequence=0), NOW)
        self.assertEqual((s["division_rank"], s["conference_rank"], s["league_rank"]), (None, None, 14))

    def test_cups_fall_back_to_the_totals(self):
        out = franchise.history({"fullName": "X", "firstSeasonId": 1}, [{"gameTypeId": 2, "cups": 3}], None, [], NOW)
        self.assertEqual(out["cups"], 3)


class CaptainsAndRetiredNumbersTest(unittest.TestCase):
    CAPTAINS = ('<ul class="striped-list">\r\n\t<li>Nick Suzuki: Oct. 12, 2022 &ndash; Present</li>\r\n'
                '\t<li><em>(No Captain): Oct. 3 &ndash; Nov. 24, 2018</em></li>\r\n'
                '\t<li>Sprague Cleghorn, Newsy Lalonde (co-captains): Dec. 1, 1920 &ndash; March 8, 1921</li>\r\n'
                '\t<li>* Date range indicates first and last games served as captain</li></ul>')
    RETIRED = ('<ul><li>1 &ndash;&nbsp;Jacques Plante (1952-63)</li><li>1 &ndash; Turk Broda (1936-43, 1945-52)</li>'
               '<li>99 &ndash; Wayne Gretzky (1979-88)*</li><li>* Includes time with the WHA team</li><li>Honoured members</li></ul>')

    def test_list_items_strips_markup_and_entities(self):
        self.assertEqual(franchise.list_items(self.CAPTAINS)[0], "Nick Suzuki: Oct. 12, 2022 – Present")
        self.assertEqual(franchise.list_items(None), [])

    def test_captains_newest_first_with_gaps_and_notes(self):
        out = franchise.captains(self.CAPTAINS)
        self.assertEqual(out["entries"][0], {"name": "Nick Suzuki", "dates": "Oct. 12, 2022 – Present", "none": False})
        self.assertEqual(out["entries"][1], {"name": None, "dates": "Oct. 3 – Nov. 24, 2018", "none": True})
        self.assertEqual(out["entries"][2]["name"], "Sprague Cleghorn, Newsy Lalonde (co-captains)")
        self.assertEqual(len(out["entries"]), 3)
        self.assertEqual(out["notes"], ["Date range indicates first and last games served as captain"])

    def test_retired_numbers_share_a_number_and_keep_odd_lines(self):
        out = franchise.retired_numbers(self.RETIRED)
        self.assertEqual([(e["number"], e["name"]) for e in out["entries"]],
                         [(1, "Jacques Plante"), (1, "Turk Broda"), (99, "Wayne Gretzky")])
        self.assertEqual(out["entries"][1]["years"], "1936-43, 1945-52")
        self.assertTrue(out["entries"][2]["starred"])
        self.assertFalse(out["entries"][0]["starred"])
        self.assertEqual(out["notes"], ["Includes time with the WHA team", "Honoured members"])

    def test_nothing_published(self):
        self.assertEqual(franchise.captains(None), {"entries": [], "notes": []})
        self.assertEqual(franchise.retired_numbers(None), {"entries": [], "notes": []})
