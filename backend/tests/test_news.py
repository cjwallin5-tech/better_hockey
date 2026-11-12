import unittest
from datetime import datetime, timedelta, timezone

import news

TEAMS = [
    {"abbrev": "EDM", "name": "Edmonton Oilers", "common_name": "Oilers"},
    {"abbrev": "MIN", "name": "Minnesota Wild", "common_name": "Wild"},
    {"abbrev": "MTL", "name": "Montréal Canadiens", "common_name": "Canadiens"},
    {"abbrev": "NJD", "name": "New Jersey Devils", "common_name": "Devils"},
    {"abbrev": "TOR", "name": "Toronto Maple Leafs", "common_name": "Maple Leafs"},
]
PLAYERS = [
    {"player_id": 1, "name": "Leon Draisaitl", "team": "EDM"},
    {"player_id": 2, "name": "Connor McDavid", "team": "EDM"},
    {"player_id": 3, "name": "Dougie Hamilton", "team": "NJD"},
    {"player_id": 4, "name": "Elias Pettersson", "team": "VAN"},   # two players share this name
    {"player_id": 5, "name": "Elias Pettersson", "team": "PIT"},
    {"player_id": 6, "name": "Jack Hughes", "team": "NJD,TOR"},    # traded: the last team is the current one
    {"player_id": 7, "name": "Auston Matthews", "team": "TOR"},
]

RSS = """<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
<item>
  <title>
      Oilers sign Draisaitl to an extension &amp; more  </title>
  <link>
      https://example.com/a?utm=1
  </link>
  <description>&lt;p&gt;A long &lt;b&gt;deal&lt;/b&gt; for the star.&lt;/p&gt;</description>
  <pubDate>Mon, 9 Nov 2026 23:22:33 EST</pubDate>
  <dc:creator>Someone</dc:creator>
</item>
<item><title>No date here</title><link>https://example.com/b</link></item>
<item><title>Not a link</title><link>nope</link><pubDate>Mon, 9 Nov 2026 23:22:33 GMT</pubDate></item>
</channel></rss>"""


def story(title, source="X", summary="", url=None, detail="", when=None):
    return {"url": url or f"https://example.com/{abs(hash(title))}", "title": title, "summary": summary, "source": source,
            "source_detail": detail, "published": when or datetime(2026, 11, 10, 12, tzinfo=timezone.utc)}


class Parsing(unittest.TestCase):
    def test_reads_title_link_excerpt_and_date_and_skips_incomplete_items(self):
        items = news.parse_feed(RSS.encode(), "Feed")
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["title"], "Oilers sign Draisaitl to an extension & more")
        self.assertEqual(it["url"], "https://example.com/a?utm=1")
        self.assertEqual(it["summary"], "A long deal for the star.")
        self.assertEqual(it["source"], "Feed")
        self.assertEqual(it["published"], datetime(2026, 11, 10, 4, 22, 33, tzinfo=timezone.utc))  # 23:22 EST

    def test_a_broken_feed_gives_nothing(self):
        self.assertEqual(news.parse_feed(b"<html>not a feed", "Feed"), [])

    def test_yahoo_credits_the_original_outlet_and_names_the_team(self):
        xml = RSS.replace("<dc:creator>", "<source>The Hockey News - Columbus Blue Jackets</source><dc:creator>")
        it = news.parse_feed(xml.encode(), "Yahoo Sports")[0]
        self.assertEqual((it["source"], it["source_detail"]), ("The Hockey News", "Columbus Blue Jackets"))

    def test_emoji_are_removed_from_headlines(self):
        self.assertEqual(news.clean("⚡ Seven teams that could trade for Kucherov"), "Seven teams that could trade for Kucherov")

    def test_long_excerpts_are_cut_at_a_word(self):
        out = news.clean("word " * 100, 20)
        self.assertTrue(out.endswith("…") and len(out) <= 21 and "wor…" not in out)


class Filtering(unittest.TestCase):
    def test_betting_and_auto_previews_are_dropped(self):
        for title in ("Devils vs. Jets Tuesday NHL odds, picks", "Best bets for tonight", "Blue Jackets vs. Panthers Game Preview"):
            self.assertFalse(news.keep(story(title)), title)
        self.assertTrue(news.keep(story("Devils beat Jets 3-2")))
        self.assertFalse(news.keep(story("A fine title", url="https://cbssports.com/betting/news/x")))

    def test_the_same_story_from_two_feeds_is_kept_once_newest_first(self):
        a = story("Same story", url="https://a.com/x/?utm=1", when=datetime(2026, 11, 10, 9, tzinfo=timezone.utc))
        b = story("Same story", url="https://a.com/x", when=datetime(2026, 11, 10, 8, tzinfo=timezone.utc))
        c = story("Other story", when=datetime(2026, 11, 10, 11, tzinfo=timezone.utc))
        out = news.merge([[a], [b, c]])
        self.assertEqual([i["title"] for i in out], ["Other story", "Same story"])
        self.assertEqual(out[1]["url"], a["url"])


class Tagging(unittest.TestCase):
    def setUp(self):
        self.t = news.Tagger(TEAMS, PLAYERS)

    def test_teams_by_full_name_nickname_and_accented_name(self):
        self.assertEqual(self.t.tag(story("Montreal Canadiens fall to the Edmonton Oilers"))[0], ["EDM", "MTL"])
        self.assertEqual(self.t.tag(story("Habs and Leafs meet again"))[0], ["MTL", "TOR"])
        self.assertEqual(self.t.tag(story("Oilers win", detail="Edmonton Oilers"))[0], ["EDM"])

    def test_wild_card_and_lower_case_wild_are_not_the_team(self):
        self.assertEqual(self.t.tag(story("Wild Card race heats up"))[0], [])
        self.assertEqual(self.t.tag(story("A wild night in Calgary"))[0], [])
        self.assertEqual(self.t.tag(story("Wild beat the Devils"))[0], ["MIN", "NJD"])

    def test_full_names_tag_the_player_and_their_team(self):
        teams, players, in_head = self.t.tag(story("Leon Draisaitl signs"))
        self.assertEqual((teams, players, in_head), (["EDM"], [1], [1]))

    def test_names_ignore_accents_and_punctuation(self):
        tagger = news.Tagger(TEAMS, [{"player_id": 9, "name": "J.T. Miller", "team": "NYR"}, {"player_id": 10, "name": "Jesperi Kotkaniemi", "team": "CAR"}])
        self.assertEqual(tagger.tag(story("J.T. Miller scores"))[1], [9])
        self.assertEqual(tagger.tag(story("Jesperi Kötkaniemi scores"))[1], [10])  # accents don't matter
        self.assertEqual(tagger.tag(story("Jesperi Kotkaniemi’s goal"))[1], [10])

    def test_two_players_with_one_name_are_not_guessed_between(self):
        self.assertEqual(self.t.tag(story("Elias Pettersson scores"))[1], [])

    def test_a_surname_alone_counts_when_the_players_team_is_in_the_story(self):
        self.assertEqual(self.t.tag(story("Draisaitl scores twice as Oilers win"))[1], [1])
        self.assertEqual(self.t.tag(story("Draisaitl scores twice"))[1], [])  # no team named: too risky to guess

    def test_a_city_that_is_also_a_surname_is_not_the_player(self):
        # Hamilton is a PWHL team; Dougie Hamilton plays for New Jersey, which the story never mentions
        self.assertEqual(self.t.tag(story("PWHL unveils Hamilton and Detroit branding"))[1], [])

    def test_a_headline_player_adds_their_current_team(self):
        self.assertEqual(self.t.tag(story("Auston Matthews returns"))[0], ["TOR"])
        self.assertEqual(self.t.tag(story("Jack Hughes returns"))[0], ["TOR"])  # traded: the last team in the list

    def test_a_player_in_the_excerpt_only_does_not_pull_in_their_team(self):
        teams, players, in_head = self.t.tag(story("Big night in Edmonton", summary="Auston Matthews also scored"))
        self.assertEqual((teams, players, in_head), ([], [7], []))


NO_TAGS = ([], [], [])


def scores(items, tags=None, stars=()):
    return news.score_all(items, tags or [NO_TAGS] * len(items), set(stars))


def at(hours):
    return datetime(2026, 11, 10, 12, tzinfo=timezone.utc) + timedelta(hours=hours)


class BigStories(unittest.TestCase):
    def top(self, *items, tags=None, stars=()):
        return [s >= news.MIN_TOP for s in scores(list(items), tags, stars)]

    def test_a_trade_or_firing_is_big_on_its_own(self):
        self.assertEqual(self.top(story("Devils trade a defenseman to Calgary")), [True])
        self.assertEqual(self.top(story("Sharks fire their coach")), [True])

    def test_a_signing_or_injury_needs_a_second_signal(self):
        self.assertEqual(self.top(story("Rangers sign a depth forward")), [False])
        self.assertEqual(self.top(story("Rangers sign a depth forward", source="ESPN")), [True])  # ESPN's editors led with it
        self.assertEqual(self.top(story("Oilers star out for six weeks with an injury"), tags=[([], [2], [2])], stars=[2]), [True])

    def test_a_star_in_the_headline_counts_more_than_one_in_the_excerpt(self):
        head, text = story("Oilers sign a forward"), story("Oilers sign a forward")
        in_head, in_text = scores([head], [([], [2], [2])], [2])[0], scores([text], [([], [2], [])], [2])[0]
        self.assertGreater(in_head, in_text)

    def test_game_recaps_are_not_big_however_many_outlets_or_stars(self):
        recaps = [story("Draisaitl scores twice as Oilers beat Rangers 3-1", source=s, when=at(0)) for s in ("AP", "Yahoo", "CBS", "ESPN")]
        tags = [([], [1], [1])] * 4
        self.assertEqual(self.top(*recaps, tags=tags, stars=[1]), [False] * 4)

    def test_speculation_opinion_and_viewing_guides_are_not_big(self):
        for title in ("Seven teams that could trade for Kucherov", "Should the Leafs trade Marner?", "Power rankings: who is hot after trades",
                      "How to watch the Hall of Fame induction ceremony"):
            self.assertEqual(self.top(story(title), tags=[([], [1], [1])], stars=[1]), [False], title)

    def test_hockey_outside_the_nhl_is_marked_down(self):
        self.assertEqual(self.top(story("PWHL unveils names for new expansion teams", source="ESPN")), [False])

    def test_other_outlets_carrying_a_story_raise_its_score_but_an_outlets_own_repeat_does_not(self):
        a = story("Rangers waive goalie Reimer after one start", source="ESPN", when=at(0))
        b = story("Rangers put goalie Reimer on waivers", source="Yahoo", when=at(1))
        c = story("Rangers put goalie Reimer on waivers again", source="ESPN", when=at(2))
        tags = [([], [5], [5])] * 3
        alone = scores([a], [tags[0]])[0]
        with_b = scores([a, b], tags[:2])[0]
        self.assertEqual(with_b - alone, news.EXTRA_OUTLET)
        self.assertEqual(scores([a, c], [tags[0], tags[2]])[0], alone)  # same outlet: not another outlet

    def test_stories_far_apart_in_time_are_not_the_same_story(self):
        a = story("Rangers put goalie Reimer on waivers", source="ESPN", when=at(0))
        b = story("Rangers put goalie Reimer on waivers", source="Yahoo", when=at(news.SAME_STORY_HOURS + 5))
        self.assertFalse(news.same_story(a, b, ([], [5], [5]), ([], [5], [5])))

    def test_two_versions_from_one_outlet_show_once_in_the_top_list_but_do_not_count_as_coverage(self):
        a = story("Devils trade Hellebuyck back to Winnipeg", source="The Athletic", when=at(0))
        b = story("Devils trade goalie Hellebuyck back to the Winnipeg Jets", source="The Athletic", when=at(1))
        tags = [([], [3], [3])] * 2
        s = scores([a, b], tags)
        self.assertEqual(sum(x >= news.MIN_TOP for x in s), 1)
        self.assertEqual(max(s), scores([a], [tags[0]])[0])  # no extra-outlet bonus for the repeat

    def test_only_the_best_version_of_a_story_stays_in_the_top_list(self):
        best = story("Devils trade Hellebuyck to Winnipeg", source="ESPN", when=at(0))
        other = story("Devils trade goalie Hellebuyck to the Winnipeg Jets", source="CBS", when=at(1))
        tags = [([], [3], [3])] * 2
        s = scores([best, other], tags)
        self.assertGreaterEqual(max(s), news.MIN_TOP)
        self.assertLess(min(s), news.MIN_TOP)


if __name__ == "__main__":
    unittest.main()
