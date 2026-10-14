import datetime as dt
import unittest
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


if __name__ == "__main__":
    unittest.main()
