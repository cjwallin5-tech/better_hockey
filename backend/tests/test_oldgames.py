import unittest

import oldgames as og


def game(gid, home, away, hs, as_, state="OFF", gtype=2, outcome="REG", season=20052006):
    return {"id": gid, "season": season, "gameType": gtype, "gameState": state, "gameDate": "2005-11-01",
            "homeTeam": {"abbrev": home, "score": hs}, "awayTeam": {"abbrev": away, "score": as_},
            "gameOutcome": {"lastPeriodType": outcome}}


class Codes(unittest.TestCase):
    def test_old_codes_become_todays_franchises(self):
        self.assertEqual([og.current_code(c) for c in ("ATL", "PHX", "ARI", "TOR")], ["WPG", "UTA", "UTA", "TOR"])

    def test_the_code_to_ask_the_nhl_for_in_each_era(self):
        self.assertEqual(og.code_in_season("WPG", 20052006), "ATL")
        self.assertEqual(og.code_in_season("WPG", 20112012), "WPG")
        self.assertEqual(og.code_in_season("UTA", 20132014), "PHX")
        self.assertEqual(og.code_in_season("UTA", 20142015), "ARI")
        self.assertEqual(og.code_in_season("UTA", 20242025), "UTA")
        self.assertEqual(og.code_in_season("TOR", 20052006), "TOR")


class Schedule(unittest.TestCase):
    def test_only_finished_regular_season_games_with_scores(self):
        data = {"games": [game(1, "TOR", "ATL", 4, 2), game(2, "TOR", "MTL", 1, 2, outcome="SO"),
                          game(3, "TOR", "MTL", 0, 0, state="FUT"), game(4, "TOR", "MTL", 3, 1, gtype=3),
                          game(5, "TOR", "MTL", None, None)]}
        out = og.parse_schedule(data)
        self.assertEqual([g["game_id"] for g in out], [1, 2])
        self.assertEqual(out[0]["away"], "WPG")                       # the Thrashers' code is today's Jets
        self.assertEqual((out[1]["last_period"], out[1]["home_score"]), ("SO", 1))

    def test_empty_response(self):
        self.assertEqual(og.parse_schedule({}), [])


class GameLog(unittest.TestCase):
    def test_skater_games(self):
        data = {"gameLog": [{"gameId": 9, "gameDate": "2006-04-18", "opponentAbbrev": "PHX", "goals": 1, "assists": 2, "toi": "20:05"}]}
        out = og.parse_game_log(data, 20052006, goalie=False)
        self.assertEqual((out[0]["opponent"], out[0]["goals"], out[0]["assists"], out[0]["toi_sec"]), ("UTA", 1, 2, 1205))

    def test_goalie_games_need_ice_time_and_carry_shots_and_goals(self):
        data = {"gameLog": [{"gameId": 1, "gameDate": "2006-04-18", "opponentAbbrev": "OTT", "shotsAgainst": 32, "goalsAgainst": 5, "toi": "60:00"},
                            {"gameId": 2, "gameDate": "2006-04-19", "opponentAbbrev": "OTT", "shotsAgainst": 0, "goalsAgainst": 0, "toi": "00:00"}]}
        out = og.parse_game_log(data, 20052006, goalie=True)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["shots_against"], out[0]["goals_against"]), (32, 5))

    def test_a_missing_log(self):
        self.assertEqual(og.parse_game_log({}, 20052006, goalie=False), [])


class Seasons(unittest.TestCase):
    def test_nhl_regular_seasons_in_range(self):
        landing = {"seasonTotals": [
            {"season": 20032004, "leagueAbbrev": "NHL", "gameTypeId": 2},    # before the first season we cover
            {"season": 20052006, "leagueAbbrev": "NHL", "gameTypeId": 2}, {"season": 20052006, "leagueAbbrev": "NHL", "gameTypeId": 3},
            {"season": 20062007, "leagueAbbrev": "AHL", "gameTypeId": 2},
            {"season": 20212022, "leagueAbbrev": "NHL", "gameTypeId": 2}, {"season": 20222023, "leagueAbbrev": "NHL", "gameTypeId": 2}]}
        self.assertEqual(og.nhl_seasons(landing, 20222023), [20052006, 20212022])


if __name__ == "__main__":
    unittest.main()
