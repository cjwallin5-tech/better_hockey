import datetime as dt
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import config
import digest

UTC = dt.timezone.utc


def entry(name, team, opp, home, start, kind="skater", goalie=None):
    e = {"name": name, "team": team, "kind": kind, "game": {"opp": opp, "home": home, "start": start}}
    if goalie is not None:
        e["start"] = goalie
    return e


def day(playing=(), idle=(), hot=(), watch=(), size=None):
    return {"today": dt.date(2026, 12, 3), "roster_size": size or len(playing) + len(idle),
            "playing": list(playing), "idle": list(idle), "hot": list(hot), "watch": list(watch)}


class Render(unittest.TestCase):
    def test_nothing_to_say_sends_nothing(self):
        self.assertIsNone(digest.render(day(idle=[{"name": "A"}])))

    def test_games_are_listed_in_start_order_with_eastern_times(self):
        late = entry("Late Guy", "COL", "DAL", True, dt.datetime(2026, 12, 4, 1, 30, tzinfo=UTC))
        early = entry("Early Guy", "WSH", "MTL", True, dt.datetime(2026, 12, 4, 0, 0, tzinfo=UTC))
        subject, body = digest.render(day(playing=[late, early], idle=[{"name": "Rested"}]))
        self.assertEqual(subject, "NHL roster: 2 of 3 play today")
        self.assertLess(body.index("Early Guy"), body.index("Late Guy"))
        self.assertIn("Early Guy (WSH) vs MTL, 7:00 PM ET", body)
        self.assertIn("NO GAME TODAY: Rested", body)
        self.assertIn("Thursday, December 3", body)
        self.assertIn(config.PUBLIC_URL + "/account", body)

    def test_away_games_use_an_at_sign(self):
        _, body = digest.render(day(playing=[entry("Road Guy", "DAL", "COL", False, dt.datetime(2026, 12, 4, 0, 30, tzinfo=UTC))]))
        self.assertIn("Road Guy (DAL) @ COL", body)

    def test_goalie_notes(self):
        t = dt.datetime(2026, 12, 4, 0, 30, tzinfo=UTC)
        confirmed = entry("G One", "DAL", "COL", False, t, "goalie", goalie=(1.0, True))
        guess = entry("G Two", "MTL", "WSH", False, t, "goalie", goalie=(0.88, False))
        unknown = entry("G Three", "EDM", "UTA", True, t, "goalie")
        _, body = digest.render(day(playing=[confirmed, guess, unknown]))
        self.assertIn("G One (DAL) @ COL, 7:30 PM ET - confirmed starter", body)
        self.assertIn("likely starter (88%, a guess)", body)
        self.assertIn("G Three (EDM) vs UTA, 7:30 PM ET - starter unclear", body)

    def test_game_without_a_start_time(self):
        _, body = digest.render(day(playing=[entry("No Time", "BOS", "TOR", True, None)]))
        self.assertIn("time TBD", body)

    def test_hot_and_watch_sections(self):
        hot = {"name": "D Hot", "recent_points": 9, "recent_games": 10, "recent_pace": 74.0, "pace": 52.0}
        _, body = digest.render(day(hot=[hot], watch=["E Hurt (BOS) hasn't played in the last 4 team games."], idle=[{"name": "x"}]))
        self.assertIn("D Hot: 9 points in the last 10 games (a 74-point pace vs 52 for the season)", body)
        self.assertIn("WATCH", body)

    def test_a_day_with_only_a_streak_still_sends_a_generic_subject(self):
        subject, _ = digest.render(day(hot=[{"name": "H", "recent_points": 5, "recent_games": 5, "recent_pace": 60.0, "pace": 40.0}], idle=[{"name": "x"}]))
        self.assertEqual(subject, "NHL roster update")


class ProspectBlock(unittest.TestCase):
    def test_prospects_and_call_ups_appear_in_the_watchlist_block(self):
        w = {"playing": [], "idle": [], "teams": [], "prospects": [{
            "name": "A Prospect", "team": "EDM", "position": "C", "goalie": False, "league": "OHL", "games": 20, "goals": 10,
            "assists": 14, "points": 24, "wins": None, "save_pct": None, "gaa": None, "ppg": 1.2, "prior_ppg": None, "change": None}],
            "called_up": ["B Prospect has reached the NHL with TOR: 2 NHL games, 1 point so far. He is now followed like any other player."]}
        lines = digest.watch_lines(w)
        self.assertIn("Prospects", lines)
        self.assertTrue(any("A Prospect (EDM prospect, C): 10-14-24 in 20 games in the OHL" in l for l in lines))
        self.assertIn("Reached the NHL", lines)

    def test_a_prospect_only_watchlist_is_enough_for_an_email(self):
        w = {"playing": [], "idle": [], "teams": [], "prospects": [{
            "name": "A Prospect", "team": "EDM", "position": "C", "goalie": False, "league": None, "games": 0, "goals": None,
            "assists": None, "points": None, "wins": None, "save_pct": None, "gaa": None, "ppg": None, "prior_ppg": None, "change": None}]}
        d = {"today": dt.date(2026, 12, 3), "roster_size": 0, "playing": [], "idle": [], "hot": [], "watch": []}
        out = digest.render(d, w)
        self.assertIsNotNone(out)
        self.assertIn("no games on record this season yet", out[1])


class SendRetry(unittest.TestCase):
    def test_retries_until_the_network_is_back(self):
        waits = []
        with mock.patch.object(digest.mail, "send", side_effect=[False, False, True]) as send:
            ok = digest.send_with_retry("a@b.c", "s", "b", attempts=5, wait=10, sleep=waits.append)
        self.assertTrue(ok)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(waits, [10, 20])

    def test_gives_up_after_the_last_attempt_without_a_trailing_wait(self):
        waits = []
        with mock.patch.object(digest.mail, "send", return_value=False) as send:
            ok = digest.send_with_retry("a@b.c", "s", "b", attempts=3, wait=10, sleep=waits.append)
        self.assertFalse(ok)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(waits, [10, 20])


class LuckSection(unittest.TestCase):
    def alert(self, name, kind="skater", flag="hot", z=3.0, actual=16, expected=9.0):
        return {"name": name, "kind": kind, "flag": flag, "z": z, "actual": actual, "expected": expected}

    def test_hot_skater_line(self):
        self.assertEqual(digest.luck_line(self.alert("A Hot")),
                         "A Hot has 16 points against about 9 expected from the shots (z +3.0). Some of it may cool off.")

    def test_cold_skater_line(self):
        line = digest.luck_line(self.alert("B Cold", flag="cold", z=-2.1, actual=3, expected=7.2))
        self.assertIn("3 points against about 7 expected", line)
        self.assertIn("z -2.1", line)
        self.assertIn("bounce back", line)

    def test_goalie_lines_talk_about_goals_allowed(self):
        hot = digest.luck_line(self.alert("G Hot", kind="goalie", z=2.0, actual=5, expected=9.4))
        cold = digest.luck_line(self.alert("G Cold", kind="goalie", flag="cold", z=-2.5, actual=14, expected=8.0))
        self.assertIn("allowed 5 goals against about 9 expected", hot)
        self.assertIn("cool off", hot)
        self.assertIn("better stretch", cold)

    def test_the_section_appears_in_the_email(self):
        _, body = digest.render(day(playing=[entry("P", "COL", "DAL", True, None)]) | {"luck": [self.alert("A Hot")]})
        self.assertIn("LUCK CHECK", body)
        self.assertIn("A Hot has 16 points", body)

    def test_a_day_with_only_a_luck_flag_still_sends(self):
        out = digest.render(day(idle=[{"name": "x"}]) | {"luck": [self.alert("A Hot")]})
        self.assertIsNotNone(out)
        self.assertEqual(out[0], "NHL roster update")

    def test_no_luck_section_without_alerts(self):
        _, body = digest.render(day(playing=[entry("P", "COL", "DAL", True, None)]))
        self.assertNotIn("LUCK CHECK", body)


class RoleSection(unittest.TestCase):
    def alert(self, name="A Skater", **kw):
        base = {"name": name, "team": "WPG", "window": 5, "pp_change": "up", "pp_label": "Promoted to PP1",
                "pp_base": 67.0, "pp": 165.0, "ev_change": None, "ev_base": 1093.0, "ev": 1190.0}
        return {**base, **kw}

    def test_a_power_play_promotion(self):
        self.assertEqual(digest.role_line(self.alert()),
                         "A Skater (WPG): Promoted to PP1 (1:07 to 2:45 of power play a game). Last 5 games vs the rest of the season.")

    def test_an_ice_time_change_on_its_own(self):
        line = digest.role_line(self.alert(pp_change=None, pp_label=None, ev_change="down", ev_base=900.0, ev=765.0))
        self.assertIn("less even-strength time (15:00 to 12:45 a game)", line)
        self.assertNotIn("power play", line)

    def test_both_changes_in_one_sentence(self):
        line = digest.role_line(self.alert(ev_change="up"))
        self.assertIn("Promoted to PP1", line)
        self.assertIn("; more even-strength time", line)

    def test_the_section_appears_in_the_email(self):
        _, body = digest.render(day(playing=[entry("P", "COL", "DAL", True, None)]) | {"roles": [self.alert()]})
        self.assertIn("ROLE CHANGES", body)
        self.assertIn("A Skater (WPG): Promoted to PP1", body)

    def test_a_day_with_only_a_role_change_still_sends(self):
        out = digest.render(day(idle=[{"name": "x"}]) | {"roles": [self.alert()]})
        self.assertIsNotNone(out)
        self.assertEqual(out[0], "NHL roster update")

    def test_no_section_without_changes(self):
        _, body = digest.render(day(playing=[entry("P", "COL", "DAL", True, None)]))
        self.assertNotIn("ROLE CHANGES", body)



class RestNotes(unittest.TestCase):
    def test_a_tired_game_is_flagged_in_the_game_line(self):
        e = entry("Tired Guy", "OTT", "SJS", True, dt.datetime(2026, 12, 4, 0, 0, tzinfo=UTC))
        e["game"]["rest"] = "tired"
        _, body = digest.render(day(playing=[e]))
        self.assertIn("Tired Guy (OTT) vs SJS, 7:00 PM ET - second night of a back-to-back vs a rested team", body)

    def test_the_rested_side_is_told_about_the_edge(self):
        self.assertEqual(digest.rest_note({"rest": "edge"}), " - opponent is on the second night of a back-to-back")

    def test_normal_games_get_no_note(self):
        self.assertEqual(digest.rest_note({"rest": None}), "")
        self.assertEqual(digest.rest_note({}), "")


class Watchlist(unittest.TestCase):
    TODAY = dt.date(2026, 12, 3)

    def ms(self):
        return {
            "reached": [
                {"player_id": 1, "name": "Fresh", "label": "Goals", "milestone": 500, "date": dt.date(2026, 12, 2)},
                {"player_id": 1, "name": "Old", "label": "Goals", "milestone": 300, "date": dt.date(2026, 11, 20)},
                {"player_id": 9, "name": "Unwatched", "label": "Goals", "milestone": 100, "date": dt.date(2026, 12, 3)},
            ],
            "upcoming": [
                {"player_id": 2, "name": "Close", "label": "Points", "milestone": 1000, "remaining": 4, "games_needed": 3},
                {"player_id": 2, "name": "Far", "label": "Goals", "milestone": 400, "remaining": 30, "games_needed": 40},
                {"player_id": 9, "name": "Unwatched", "label": "Goals", "milestone": 100, "remaining": 1, "games_needed": 1},
            ],
        }

    def test_milestones_for_watched_players_only_recent_or_near(self):
        out = digest.milestone_alerts(self.ms(), {1, 2}, self.TODAY)
        self.assertEqual([(a["name"], a["reached"]) for a in out], [("Fresh", True), ("Close", False)])

    def test_milestone_lines(self):
        a, b = digest.milestone_alerts(self.ms(), {1, 2}, self.TODAY)
        self.assertEqual(digest.milestone_line(a), "Fresh reached 500 career goals.")
        self.assertEqual(digest.milestone_line(b), "Close is 4 points from 1,000 career, about 3 games away at the current pace.")

    def test_watch_block_lists_games_and_milestones(self):
        game = {"opp": "MTL", "home": True, "start": dt.datetime(2026, 12, 4, 0, 0, tzinfo=UTC)}
        w = {"playing": [entry("Star Guy", "WSH", "MTL", True, game["start"])], "idle": [{"name": "Rested"}],
             "teams": [{"team": "TOR", "game": game}, {"team": "BOS", "game": None}],
             "milestones": digest.milestone_alerts(self.ms(), {1, 2}, self.TODAY)}
        text = "\n".join(digest.watch_lines(w))
        self.assertIn("Star Guy (WSH) vs MTL, 7:00 PM ET", text)
        self.assertIn("TOR vs MTL, 7:00 PM ET", text)
        self.assertIn("No game today: Rested, BOS", text)
        self.assertIn("Fresh reached 500 career goals.", text)

    def test_watchlist_alone_is_enough_for_an_email(self):
        w = {"milestones": digest.milestone_alerts(self.ms(), {1}, self.TODAY)}
        subject, body = digest.render(day(size=0), w)
        self.assertEqual(subject, "NHL watchlist update")
        self.assertIn("WATCHLIST", body)
        self.assertIn("Your NHL watchlist for", body)

    def test_an_empty_watchlist_adds_nothing(self):
        self.assertIsNone(digest.render(day(idle=[{"name": "A"}]), {"milestones": []}))

if __name__ == "__main__":
    unittest.main()
