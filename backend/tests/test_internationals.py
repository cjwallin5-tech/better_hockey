import json
import unittest

import internationals as it

RESULTS = {
    "countries": {"CAN": "Canada", "USA": "United States", "RUS": "Russia", "URS": "Soviet Union", "CZE": "Czechia", "TCH": "Czechoslovakia",
                  "SWE": "Sweden", "EUN": "Unified Team", "FIN": "Finland"},
    "tournaments": {
        "olympics": {"label": "Olympic Games", "tier": 1, "results": {
            "2014": {"gold": "CAN", "silver": "SWE", "bronze": "FIN"}, "1992": {"gold": "EUN", "silver": "CAN", "bronze": "TCH"},
            "1998": {"gold": "CZE", "silver": "RUS", "bronze": "FIN"}}},
        "worlds": {"label": "World Championship", "tier": 1, "results": {"2015": {"gold": "CAN", "silver": "RUS", "bronze": "USA"}}},
        "worldcup": {"label": "World Cup of Hockey / Canada Cup", "tier": 1, "results": {
            "1976": {"gold": "CAN", "silver": "TCH"}, "1981": {"gold": "URS", "silver": "CAN"}}},
        "juniors": {"label": "World Junior Championship", "tier": 2, "results": {"2005": {"gold": "CAN", "silver": "RUS", "bronze": "CZE"}}},
    },
}


def row(league, season, team, games=5, goals=1, assists=2):
    return {"league": league, "season_id": season, "team_name": team, "games": games, "goals": goals, "assists": assists, "points": goals + assists}


def apps(*rows):
    return it.appearances(list(rows), RESULTS)


class Countries(unittest.TestCase):
    def test_names_are_normalised(self):
        self.assertEqual([it.country_code(n) for n in ("USA", "United States", "Canada U20", "USA Olympics", "Czech Republic", "Czechia U20", "Soviet Union")],
                         ["USA", "USA", "CAN", "USA", "CZE", "CZE", "URS"])
        self.assertIsNone(it.country_code("Atlantis"))
        self.assertIsNone(it.country_code(None))

    def test_a_countrys_predecessors_and_successors_share_a_lineage(self):
        for a, b in (("URS", "RUS"), ("EUN", "RUS"), ("CIS", "RUS"), ("TCH", "CZE"), ("FRG", "GER")):
            self.assertEqual(it.lineage(a), it.lineage(b))
        self.assertNotEqual(it.lineage("CAN"), it.lineage("USA"))


class Medals(unittest.TestCase):
    def test_gold_silver_and_bronze_come_from_the_country_and_the_year(self):
        out = apps(row("Olympics", 20132014, "Canada"), row("Olympics", 20132014, "Sweden"), row("Olympics", 20132014, "Finland"),
                   row("Olympics", 20132014, "United States"))
        self.assertEqual({a["country"]: a["medal"] for a in out}, {"Canada": "gold", "Sweden": "silver", "Finland": "bronze", "United States": None})

    def test_a_team_under_its_successors_name_takes_the_medal(self):
        # the Unified Team of 1992 won gold; its players are listed as "Russia"
        self.assertEqual(apps(row("Olympics", 19911992, "Russia"))[0]["medal"], "gold")
        # Czechoslovakia's 1992 bronze, listed under either name
        self.assertEqual(apps(row("Olympics", 19911992, "Czechoslovakia"))[0]["medal"], "bronze")
        self.assertEqual(apps(row("Olympics", 19911992, "Czech Republic"))[0]["medal"], "bronze")

    def test_the_two_olympic_labels_and_the_two_world_labels_are_one_tournament(self):
        out = apps(row("Olympics", 20132014, "Canada", games=6), row("OG", 20132014, "Canada", games=6),
                   row("WC", 20142015, "Canada", games=10), row("WC-A", 20142015, "Canada", games=9))
        self.assertEqual([(a["tournament"], a["year"], a["games"]) for a in out], [("worlds", 2015, 10), ("olympics", 2014, 6)])

    def test_the_september_tournament_is_matched_whichever_season_it_was_filed_under(self):
        # Orr's 1976 Canada Cup appears as "CC" 1975-76 and as "Can-Cup" 1976-77; Gretzky's 1981 one as "CC" 1980-81
        self.assertEqual([(a["year"], a["medal"]) for a in apps(row("CC", 19751976, "Canada"))], [(1976, "gold")])
        self.assertEqual([(a["year"], a["medal"]) for a in apps(row("Can-Cup", 19761977, "Canada"))], [(1976, "gold")])
        self.assertEqual([(a["year"], a["medal"]) for a in apps(row("CC", 19801981, "Canada"))], [(1981, "silver")])
        self.assertEqual(len(apps(row("CC", 19751976, "Canada"), row("Can-Cup", 19761977, "Canada"))), 1)

    def test_a_tournament_with_only_a_final_has_no_bronze(self):
        self.assertIsNone(apps(row("CC", 19751976, "Sweden"))[0]["medal"])

    def test_juniors_match_on_the_season_end_year_and_ignore_the_age_suffix(self):
        out = apps(row("WJC-20", 20042005, "Canada U20"))
        self.assertEqual((out[0]["year"], out[0]["medal"], out[0]["tier"]), (2005, "gold", 2))

    def test_leagues_that_are_not_these_tournaments_or_editions_with_no_result_are_ignored(self):
        self.assertEqual(apps(row("WC-B", 20142015, "Canada"), row("WJ18-A", 20042005, "Canada"), row("NHL", 20142015, "Canada"),
                              row("WC", 20152016, "Canada")), [])  # no 2016 world championship in this small results table

    def test_an_unknown_country_is_still_an_appearance_without_a_medal(self):
        out = apps(row("WC", 20142015, "Atlantis"))
        self.assertEqual((out[0]["country"], out[0]["code"], out[0]["medal"]), ("Atlantis", None, None))

    def test_totals(self):
        out = apps(row("Olympics", 20132014, "Canada"), row("WC", 20142015, "Russia"), row("WC", 20142015, "Canada"),
                   row("WJC-20", 20042005, "Canada U20"))
        self.assertEqual(it.medal_counts(out), {"gold": 3, "silver": 1, "bronze": 0})
        self.assertEqual(it.by_tournament(out)["worlds"], {"label": "World Championship", "tier": 1, "gold": 1, "silver": 1, "bronze": 0, "played": 2})

    def test_newest_first(self):
        out = apps(row("WJC-20", 20042005, "Canada U20"), row("Olympics", 20132014, "Canada"), row("WC", 20142015, "Canada"))
        self.assertEqual([a["year"] for a in out], [2015, 2014, 2005])


class Landing(unittest.TestCase):
    def test_tournament_rows_are_taken_from_the_season_totals(self):
        payload = {"seasonTotals": [
            {"leagueAbbrev": "NHL", "season": 20142015, "teamName": {"default": "Pittsburgh Penguins"}, "gamesPlayed": 77},
            {"leagueAbbrev": "OG", "season": 20132014, "teamName": {"default": "Canada"}, "gamesPlayed": 6, "goals": 3, "assists": 1, "points": 4}]}
        self.assertEqual(it.rows_from_landing(payload), [
            {"league": "OG", "season_id": 20132014, "team_name": "Canada", "games": 6, "goals": 3, "assists": 1, "points": 4}])
        self.assertEqual(it.rows_from_landing(None), [])


class Awards(unittest.TestCase):
    PAYLOAD = {"awards": [
        {"trophy": {"default": "Stanley Cup"}, "seasons": [{"seasonId": 20082009}, {"seasonId": 20152016}]},
        {"trophy": {"default": "Hart Memorial Trophy"}, "seasons": [{"seasonId": 20062007}]},
        {"trophy": {"default": "Lady Byng"}, "seasons": []}]}

    def test_every_award_season_is_a_row(self):
        self.assertEqual(sorted(it.awards_from_landing(self.PAYLOAD)),
                         [("Hart Memorial Trophy", 20062007), ("Stanley Cup", 20082009), ("Stanley Cup", 20152016)])
        self.assertEqual(it.awards_from_landing(None), [])
        self.assertEqual(it.awards_from_landing({}), [])

    def test_stanley_cups_are_the_cup_seasons_oldest_first(self):
        self.assertEqual(it.stanley_cups(it.awards_from_landing(self.PAYLOAD)), [20082009, 20152016])
        self.assertEqual(it.stanley_cups([("Hart Memorial Trophy", 20062007)]), [])


class TripleGold(unittest.TestCase):
    def apps(self, *rows):
        return it.appearances(list(rows), RESULTS)

    def test_the_cup_olympic_gold_and_world_championship_gold_make_a_member(self):
        a = self.apps(row("Olympics", 20132014, "Canada"), row("WC", 20142015, "Canada"))
        self.assertEqual(it.triple_gold(a, [20082009, 20152016]),
                         {"cup": 2009, "olympics": 2014, "worlds": 2015, "completed": 2015, "source": "computed"})

    def test_the_year_completed_is_the_latest_of_the_three_first_wins(self):
        a = self.apps(row("Olympics", 20132014, "Canada"), row("WC", 20142015, "Canada"))
        self.assertEqual(it.triple_gold(a, [20182019])["completed"], 2019)

    def test_any_missing_piece_is_not_a_member(self):
        olympics, worlds = row("Olympics", 20132014, "Canada"), row("WC", 20142015, "Canada")
        self.assertIsNone(it.triple_gold(self.apps(olympics, worlds), []))                                  # no Cup
        self.assertIsNone(it.triple_gold(self.apps(worlds), [20082009]))                                    # no Olympic gold
        self.assertIsNone(it.triple_gold(self.apps(olympics), [20082009]))                                  # no Worlds gold
        self.assertIsNone(it.triple_gold(self.apps(row("Olympics", 20132014, "Sweden"), worlds), [20082009]))  # a silver is not gold

    def test_the_official_roll_covers_a_member_the_nhls_rows_leave_out(self):
        # Lidstrom's NHL page has no 1991 World Championship row, so only the Olympic gold shows
        a = self.apps(row("Olympics", 20132014, "Canada"))
        official = {"cup": 1997, "olympics": 2006, "worlds": 1991, "completed": 2006}
        self.assertEqual(it.triple_gold(a, [19961997], official), {**official, "source": "official"})
        self.assertIsNone(it.triple_gold(a, [19961997]))   # without the roll, he is missed

    def test_a_computed_member_is_reported_as_computed_even_when_the_roll_has_him(self):
        a = self.apps(row("Olympics", 20132014, "Canada"), row("WC", 20142015, "Canada"))
        out = it.triple_gold(a, [20082009], {"cup": 2009, "olympics": 2014, "worlds": 2015, "completed": 2015})
        self.assertEqual(out["source"], "computed")

    def test_names_match_without_accents_and_a_known_alias_is_applied(self):
        self.assertEqual(it.name_key("Jaromír Jágr"), it.name_key("Jaromir Jagr"))
        self.assertIn(it.name_key("Nicklas Lidström"), it.official_club())
        self.assertIn("freddy modin", it.official_club())   # the roll says Fredrik; the NHL says Freddy

    def test_juniors_and_the_world_cup_do_not_count(self):
        a = self.apps(row("WJC-20", 20042005, "Canada U20"), row("CC", 19751976, "Canada"), row("Olympics", 20132014, "Canada"))
        self.assertIsNone(it.triple_gold(a, [20082009]))


AWARDS = {"awards": [
    {"tournament": "olympics", "year": 2014, "award": "forward", "name": "Phil Kessel", "code": "USA"},
    {"tournament": "olympics", "year": 2014, "award": "mvp", "name": "Teemu Selänne", "code": "FIN"},
    {"tournament": "worlds", "year": 2015, "award": "mvp", "name": "Jaromír Jágr", "code": "CZE"},
    {"tournament": "worlds", "year": 2015, "award": "forward", "name": "Jason Spezza", "code": "CAN"},
    {"tournament": "juniors", "year": 2005, "award": "mvp", "name": "Patrice Bergeron", "code": "CAN"}]}


class Honors(unittest.TestCase):
    def test_an_award_is_his_when_the_name_matches_and_he_played_that_tournament_that_year(self):
        a = apps(row("Olympics", 20132014, "United States"))
        out = it.honors("Phil Kessel", "USA", a, AWARDS)
        self.assertEqual([(h["year"], h["award"], h["country"]) for h in out], [(2014, "forward", "United States")])

    def test_names_match_without_accents_and_the_newest_award_comes_first(self):
        a = apps(row("Olympics", 20132014, "Finland"), row("WC", 20142015, "Czechia"))
        self.assertEqual([h["award"] for h in it.honors("Teemu Selanne", "FIN", a, AWARDS)], ["mvp"])
        self.assertEqual(it.honors("Jaromir Jagr", "CZE", a, AWARDS)[0]["year"], 2015)

    def test_a_player_with_no_tournament_rows_still_gets_an_award_for_his_own_country(self):
        # the NHL's rows lack the tournament, but the name and the country agree
        self.assertEqual(len(it.honors("Jason Spezza", "CAN", [], AWARDS)), 1)

    def test_a_namesake_from_another_country_who_did_not_play_there_does_not(self):
        self.assertEqual(it.honors("Jason Spezza", "USA", [], AWARDS), [])

    def test_the_nhls_iso_country_codes_are_read_as_the_iocs(self):
        awards = {"awards": [{"tournament": "worlds", "year": 2024, "award": "defense", "name": "Roman Josi", "code": "SUI"}]}
        self.assertEqual(len(it.honors("Roman Josi", "CHE", [], awards)), 1)

    def test_country_names(self):
        self.assertEqual(it.country_name("BLR", RESULTS), "Belarus")
        self.assertEqual(it.country_name("CAN", RESULTS), "Canada")


class AwardsFile(unittest.TestCase):
    def test_the_shipped_awards_file_is_consistent(self):
        d = it.load_awards()
        results = it.load_results()
        self.assertGreater(len(d["awards"]), 300)
        seen = set()
        for a in d["awards"]:
            self.assertIn(a["award"], it.AWARD_ORDER)
            self.assertIn(a["tournament"], results["tournaments"])
            self.assertRegex(a["code"], r"^[A-Z]{3}$")
            self.assertTrue(a["name"].strip())
            key = (a["tournament"], a["year"], a["award"])
            self.assertNotIn(key, seen)       # one winner per award per edition
            seen.add(key)
            self.assertIn(str(a["year"]), results["tournaments"][a["tournament"]]["results"], f"{a} is for an edition with no results")
        names = {(a["tournament"], a["year"], a["award"]): a["name"] for a in d["awards"]}
        self.assertEqual(names[("olympics", 2014, "goaltender")], "Carey Price")
        self.assertEqual(names[("juniors", 2015, "goaltender")], "Denis Godla")
        self.assertEqual(names[("worlds", 2015, "mvp")], "Jaromír Jágr")
        self.assertEqual(names[("worldcup", 2016, "mvp")], "Sidney Crosby")
        self.assertEqual(names[("fournations", 2025, "mvp")], "Nathan MacKinnon")


class ResultsFile(unittest.TestCase):
    def test_the_shipped_results_file_is_complete_and_consistent(self):
        d = it.load_results()
        self.assertEqual(set(d["tournaments"]), set(it.LEAGUES))
        for key, t in d["tournaments"].items():
            self.assertTrue(t["results"], key)
            for year, r in t["results"].items():
                self.assertIn("gold", r)
                self.assertIn("silver", r)
                for code in r.values():
                    self.assertIn(code, d["countries"], f"{key} {year}")
        olympics = d["tournaments"]["olympics"]["results"]
        self.assertEqual(olympics["1992"], {"gold": "EUN", "silver": "CAN", "bronze": "TCH"})   # the Unified Team's cell is written differently
        self.assertEqual(olympics["2018"], {"gold": "RUS", "silver": "GER", "bronze": "CAN"})   # and so is the Olympic Athletes from Russia's
        self.assertEqual(olympics["2026"], {"gold": "USA", "silver": "CAN", "bronze": "FIN"})


if __name__ == "__main__":
    unittest.main()
