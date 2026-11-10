import datetime as dt
import io
import unittest
from unittest import mock

import config
import previews as pv

UTC = dt.timezone.utc

SKATER = {"name": "Connor McDavid", "team": "EDM", "position": "C", "games_played": 16, "goals": 9, "assists": 31, "points": 40}
GOALIE = {"name": "Pyotr Kochetkov", "team": "CAR", "games_played": 11, "wins": 10, "losses": 1, "ot_losses": 0,
          "save_pct": 0.9221, "gaa": 1.64, "shutouts": 2}
TEAM = {"name": "Edmonton Oilers", "abbrev": "EDM", "conference": "Western", "division": "Pacific", "league_rank": 2, "division_rank": 1,
        "games_played": 16, "wins": 11, "losses": 2, "ot_losses": 3, "points": 25, "goals_for": 56, "goals_against": 37, "goal_diff": 19}


class Routes(unittest.TestCase):
    def test_player_goalie_prospect_and_game_ids(self):
        self.assertEqual(pv.parse_route("/player/8478402")[:2], ("player", 8478402))
        self.assertEqual(pv.parse_route("/goalie/8481611")[:2], ("goalie", 8481611))
        self.assertEqual(pv.parse_route("/prospect/8484799")[:2], ("prospect", 8484799))
        self.assertEqual(pv.parse_route("/game/2026020123")[:2], ("game", 2026020123))

    def test_team_codes_are_upper_cased(self):
        self.assertEqual(pv.parse_route("/team/edm")[:2], ("team", "EDM"))

    def test_compare_keeps_its_query(self):
        kind, _, query = pv.parse_route("/compare?ids=1,2")
        self.assertEqual((kind, pv.compare_ids(query)), ("compare", [1, 2]))

    def test_static_private_and_unknown_pages(self):
        self.assertEqual(pv.parse_route("/standings")[:2], ("page", "/standings"))
        self.assertEqual(pv.parse_route("/")[:2], ("page", "/"))
        for p in ("/account", "/reset-password?token=abc", "/fantasy", "/league/7", "/watchlist"):
            self.assertEqual(pv.parse_route(p)[0], "private", p)
        self.assertEqual(pv.parse_route("/no/such/page")[0], "default")

    def test_odd_input_never_matches_a_specific_page(self):
        for p in ("/player/12abc", '/player/1"><script>', "/player/", "/player/99999999999999999", "/team/EDMX", "/team/ED1", "", None):
            self.assertIn(pv.parse_route(p)[0], ("default", "page"), p)

    def test_compare_ids_are_digits_only_and_capped_at_four(self):
        self.assertEqual(pv.compare_ids({"ids": ["1,2,3,4,5,6"]}), [1, 2, 3, 4])
        self.assertEqual(pv.compare_ids({"ids": ['7"><script>8']}), [7, 8])
        self.assertEqual(pv.compare_ids({}), [])

    def test_unknown_addresses_share_one_key_so_they_cannot_fill_the_cache(self):
        keys = {pv.route_key(*pv.parse_route(u)) for u in ("/a", "/b?x=1", "/c/d/e", "/zzz")}
        self.assertEqual(len(keys), 1)
        self.assertNotEqual(pv.route_key(*pv.parse_route("/compare?ids=1,2")), pv.route_key(*pv.parse_route("/compare?ids=1,3")))


class Words(unittest.TestCase):
    def test_helpers(self):
        self.assertEqual(pv.season_label(20262027), "2026-27")
        self.assertEqual(pv.season_label(20992100), "2099-00")
        self.assertEqual(pv.num(1487), "1,487")
        self.assertEqual(pv.num(None), "–")
        self.assertEqual(pv.plural(1, "goal"), "1 goal")
        self.assertEqual(pv.plural(9, "goal"), "9 goals")
        self.assertEqual([pv.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 111)], ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "111th"])
        self.assertEqual(pv.last_team("NYI,TOR"), "TOR")
        self.assertEqual(pv.initials("Connor McDavid"), "CM")
        self.assertEqual(pv.accent_for("NYI,TOR"), pv.TEAM_COLORS["TOR"])
        self.assertEqual(pv.accent_for("???"), pv.DEFAULT_ACCENT)

    def test_headshots_use_the_season_and_team_folder_and_need_all_parts(self):
        self.assertEqual(pv.headshot_url(20262027, "EDM", 8478402), "https://assets.nhle.com/mugs/nhl/20262027/EDM/8478402.png")
        self.assertIsNone(pv.headshot_url(None, "EDM", 1))
        self.assertIsNone(pv.headshot_url(20262027, "", 1))


class Builders(unittest.TestCase):
    def test_a_skater(self):
        m = pv.skater_meta(SKATER, 20262027, 84, 8478402)
        self.assertEqual(m["title"], "Connor McDavid (Center, EDM)")
        self.assertIn("40 points in 16 games (a 210-point pace)", m["description"])
        self.assertEqual(m["stats"], [("GP", "16"), ("G", "9"), ("A", "31"), ("P", "40")])
        self.assertTrue(m["photo"].endswith("/20262027/EDM/8478402.png"))
        self.assertEqual(m["accent"], pv.TEAM_COLORS["EDM"])

    def test_a_traded_skater_uses_the_latest_team_for_color_and_picture(self):
        m = pv.skater_meta(dict(SKATER, team="NYI,TOR"), 20262027, 84, 5)
        self.assertEqual(m["accent"], pv.TEAM_COLORS["TOR"])
        self.assertIn("/TOR/", m["photo"])

    def test_a_retired_skater_gets_career_numbers_and_the_years(self):
        row = {"name": "Wayne Gretzky", "position": "C", "games_played": 1487, "goals": 894, "assists": 1963, "points": 2857,
               "first_season": 19791980, "active_season": None}
        m = pv.career_skater_meta(row, 19981999, "NYR", 8447400)
        self.assertIn("2,857 points in 1,487 games (1979-80 to 1998-99)", m["description"])
        self.assertEqual(m["stats"][-1], ("P", "2,857"))
        self.assertIn("/19981999/NYR/", m["photo"])

    def test_a_career_with_no_known_last_season_has_no_picture(self):
        row = {"name": "Old Timer", "position": "D", "games_played": 5, "goals": 0, "assists": 1, "points": 1, "first_season": None, "active_season": None}
        m = pv.career_skater_meta(row, None, None, 9)
        self.assertIsNone(m["photo"])

    def test_a_goalie(self):
        m = pv.goalie_meta(GOALIE, 20262027, 8481611)
        self.assertIn("10-1-0, .922 save percentage, 1.64 goals-against average and 2 shutouts in 11 games", m["description"])
        self.assertEqual([s[0] for s in m["stats"]], ["GP", "W-L-OTL", "SV%", "GAA", "SO"])

    def test_a_goalie_with_missing_numbers_does_not_crash(self):
        m = pv.goalie_meta(dict(GOALIE, save_pct=None, ot_losses=None, shutouts=None), 20262027, 1)
        self.assertIn("–", m["description"])

    def test_a_team(self):
        m = pv.team_meta(TEAM)
        self.assertEqual(m["title"], "Edmonton Oilers (11-2-3)")
        self.assertIn("25 points, 2nd in the league (1st in the Pacific division)", m["description"])
        self.assertEqual(m["stats"][-1], ("Goal diff", "+19"))
        self.assertEqual(m["badge"], "EDM")

    def test_a_finished_game_names_the_winner_first(self):
        row = {"home": "EDM", "away": "ANA", "home_score": 2, "away_score": 4, "state": "FINAL", "last_period": "REG",
               "game_date": dt.date(2026, 11, 5), "start_time": None}
        self.assertEqual(pv.game_meta(row)["title"], "ANA 4, EDM 2 (Final)")
        row.update(home_score=5, away_score=4, last_period="OT")
        self.assertEqual(pv.game_meta(row)["title"], "EDM 5, ANA 4 (Final/OT)")

    def test_an_upcoming_game_shows_the_eastern_start_time(self):
        row = {"home": "EDM", "away": "ANA", "home_score": None, "away_score": None, "state": "FUT", "last_period": None,
               "game_date": dt.date(2026, 11, 5), "start_time": dt.datetime(2026, 11, 6, 1, 0, tzinfo=UTC)}
        m = pv.game_meta(row)
        self.assertEqual(m["title"], "ANA at EDM, Nov 5, 8:00 PM ET")
        self.assertEqual(m["stats"], [])

    def test_a_prospect_with_and_without_a_season(self):
        row = {"name": "Michael Hage", "team": "MTL", "position": "C", "draft_year": 2024, "draft_round": 1, "draft_overall": 21,
               "draft_team": "MTL", "headshot": "https://assets.nhle.com/mugs/x.png"}
        season = {"season_id": 20262027, "league": "NCAA", "team_name": "Univ. of Michigan", "games": 9, "points": 20}
        m = pv.prospect_meta(row, season, 1, 20262027)
        self.assertIn("2024 draft, round 1, #21 overall by MTL", m["description"])
        self.assertIn("NCAA Univ. of Michigan, 9 games, 20 points", m["description"])
        self.assertEqual(m["photo"], row["headshot"])
        bare = pv.prospect_meta(dict(row, draft_year=None, headshot=None), None, 1, 20262027)
        self.assertNotIn("draft", bare["description"])
        self.assertEqual(bare["stats"], [])

    def test_a_comparison(self):
        m = pv.compare_meta([{"name": "Connor McDavid", "team": "EDM", "points": 40, "games_played": 16},
                             {"name": "Nathan MacKinnon", "team": "COL", "points": 27, "games_played": 16}])
        self.assertEqual(m["headline"], "McDavid vs MacKinnon")
        self.assertEqual(m["stats"], [("McDavid", "40 P"), ("MacKinnon", "27 P")])
        self.assertEqual(pv.compare_meta([])["headline"], "Compare players")

    def test_a_leaderboard_adds_its_top_lines(self):
        m = pv.leaders_meta("/skaters", "Skater stats", "Every skater.", [("McDavid", "40 P"), ("Draisaitl", "29 P"), ("MacKinnon", "27 P"), ("X", "1 P")])
        self.assertIn("McDavid 40 P, Draisaitl 29 P, MacKinnon 27 P.", m["description"])
        self.assertEqual(len(m["stats"]), 4)


class Tags(unittest.TestCase):
    def test_the_tags_name_the_page_the_picture_and_the_card_type(self):
        meta = pv.skater_meta(SKATER, 20262027, 84, 8478402)
        tags = pv.head_html(meta, "/player/8478402")
        self.assertIn("<title>Connor McDavid (Center, EDM) · NHL Stats</title>", tags)
        for needle in ('property="og:title"', 'property="og:description"', 'property="og:image"', 'property="og:url"',
                       'name="twitter:card" content="summary_large_image"', 'rel="canonical"', 'name="description"',
                       'content="1200"', 'content="630"'):
            self.assertIn(needle, tags)
        self.assertIn(f'content="{config.PUBLIC_URL}/player/8478402"', tags)
        self.assertIn(f"{config.PUBLIC_URL}/api/share/image.png?url=%2Fplayer%2F8478402", tags)
        self.assertNotIn("noindex", tags)

    def test_the_site_title_is_not_doubled(self):
        self.assertIn("<title>NHL Stats</title>", pv.head_html(pv.default_meta(), "/"))

    def test_the_tab_title_matches_the_page_title_tag(self):
        meta = pv.team_meta(TEAM)
        self.assertEqual(pv.page_title(meta), "Edmonton Oilers (11-2-3) · NHL Stats")
        self.assertIn(f"<title>{pv.page_title(meta)}</title>", pv.head_html(meta, "/team/EDM"))
        self.assertEqual(pv.page_title(pv.default_meta()), "NHL Stats")

    def test_private_pages_ask_not_to_be_indexed(self):
        self.assertIn('name="robots" content="noindex"', pv.head_html(pv._meta(pv.SITE, pv.GENERIC, noindex=True), "/account"))

    def test_hostile_text_is_escaped_everywhere(self):
        meta = pv._meta('Evil "name" <script>alert(1)</script>', 'desc "x" <b>', headline='h"><img src=x>')
        tags = pv.head_html(meta, "/player/1")
        self.assertNotIn("<script>", tags)
        self.assertNotIn("<img", tags)
        self.assertNotIn('"><', tags.replace('" />\n    <', ""))
        self.assertIn("&lt;script&gt;", tags)

    def test_a_reset_token_or_any_other_query_never_reaches_the_tags(self):
        for url in ("/reset-password?token=SECRETTOKEN", "/account?token=SECRETTOKEN", "/player/5?token=SECRETTOKEN",
                    "/team/EDM?session=SECRETTOKEN", "/skaters?q=SECRETTOKEN"):
            meta = pv.default_meta() if "reset" in url or "account" in url else pv.skater_meta(SKATER, 20262027, 84, 5)
            self.assertNotIn("SECRETTOKEN", pv.head_html(meta, url), url)
            self.assertNotIn("SECRETTOKEN", pv.page_url(url), url)

    def test_the_comparison_address_is_cleaned_to_ids(self):
        self.assertEqual(pv.page_url('/compare?ids=1,2"><script>'), config.PUBLIC_URL + "/compare?ids=1,2")
        self.assertEqual(pv.page_url("/player/5?utm=x"), config.PUBLIC_URL + "/player/5")
        self.assertEqual(pv.page_url("/totally/unknown"), config.PUBLIC_URL)


class Picture(unittest.TestCase):
    def png_size(self, data):
        from PIL import Image
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        return Image.open(io.BytesIO(data)).size

    def test_every_kind_of_card_is_a_1200_by_630_png(self):
        metas = [pv.skater_meta(SKATER, 20262027, 84, 1), pv.goalie_meta(GOALIE, 20262027, 2), pv.team_meta(TEAM),
                 pv.default_meta(), pv.compare_meta([dict(SKATER, points=1)] * 4),
                 pv._meta("Standings", pv.PAGES["/standings"][1], headline="NHL standings")]
        for m in metas:
            self.assertEqual(self.png_size(pv.render_card(m)), (1200, 630), m["title"])

    def test_a_headshot_is_used_and_a_broken_one_falls_back_to_the_badge(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGBA", (168, 168), (200, 30, 30, 255)).save(buf, "PNG")
        meta = pv.skater_meta(SKATER, 20262027, 84, 1)
        with_photo = pv.render_card(meta, buf.getvalue())
        with self.assertLogs("uvicorn.error", level="WARNING"):
            broken = pv.render_card(meta, b"this is not an image")
        self.assertEqual(self.png_size(with_photo), (1200, 630))
        self.assertEqual(self.png_size(broken), (1200, 630))
        self.assertNotEqual(with_photo, broken)

    def test_a_very_long_name_and_text_do_not_break_the_card(self):
        m = pv._meta("x", "word " * 200, headline="Averyveryverylongsurname-Anotherlongsurname " * 3, subline="detail " * 40)
        self.assertEqual(self.png_size(pv.render_card(m)), (1200, 630))

    def test_wrapping_stops_at_the_line_limit_with_an_ellipsis(self):
        from PIL import Image, ImageDraw
        d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        f = pv._font(30)
        lines = pv._wrap(d, "lorem ipsum dolor sit amet " * 30, f, 600, 3)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[-1].endswith("…"))
        self.assertTrue(all(d.textlength(ln, font=f) <= 600 for ln in lines))
        self.assertEqual(pv._wrap(d, "short text", f, 600, 3), ["short text"])


class CacheAndPhotos(unittest.TestCase):
    def setUp(self):
        pv._CACHE.clear()

    def test_only_the_nhl_picture_host_is_ever_fetched(self):
        with mock.patch.object(pv.requests, "get") as get:
            self.assertIsNone(pv.fetch_photo("https://evil.example/x.png"))
            self.assertIsNone(pv.fetch_photo("http://169.254.169.254/latest/meta-data"))
            self.assertIsNone(pv.fetch_photo(None))
        get.assert_not_called()

    def test_a_picture_is_fetched_once_and_a_miss_is_remembered(self):
        ok = mock.Mock(ok=True, content=b"PNGDATA", headers={"content-type": "image/png"})
        with mock.patch.object(pv.requests, "get", return_value=ok) as get:
            url = "https://assets.nhle.com/mugs/nhl/20262027/EDM/1.png"
            self.assertEqual(pv.fetch_photo(url), b"PNGDATA")
            self.assertEqual(pv.fetch_photo(url), b"PNGDATA")
        self.assertEqual(get.call_count, 1)
        miss = mock.Mock(ok=False, content=b"", headers={"content-type": "text/html"})
        with mock.patch.object(pv.requests, "get", return_value=miss) as get:
            self.assertIsNone(pv.fetch_photo("https://assets.nhle.com/mugs/nhl/2/E/2.png"))
            self.assertIsNone(pv.fetch_photo("https://assets.nhle.com/mugs/nhl/2/E/2.png"))
        self.assertEqual(get.call_count, 1)

    def test_a_network_error_is_a_miss_not_a_crash(self):
        with mock.patch.object(pv.requests, "get", side_effect=pv.requests.ConnectionError("down")):
            self.assertIsNone(pv.fetch_photo("https://assets.nhle.com/mugs/nhl/3/E/3.png"))

    def test_the_cache_stays_bounded_and_expires(self):
        for i in range(pv.MAX_ENTRIES * 2):
            pv._cached(("k", i), lambda i=i: i)
        self.assertLessEqual(len(pv._CACHE), pv.MAX_ENTRIES)
        calls = []
        with mock.patch.object(pv.time, "time", return_value=1000.0):
            pv._cached("fresh", lambda: calls.append(1) or "v", ttl=60)
            pv._cached("fresh", lambda: calls.append(1) or "v", ttl=60)
        with mock.patch.object(pv.time, "time", return_value=1100.0):
            pv._cached("fresh", lambda: calls.append(1) or "v", ttl=60)
        self.assertEqual(len(calls), 2)

    def test_a_database_failure_gives_the_generic_preview(self):
        with mock.patch.object(pv.psycopg, "connect", side_effect=RuntimeError("db down")), \
                self.assertLogs("uvicorn.error", level="WARNING"):
            self.assertEqual(pv.meta_for("/player/123456")["title"], pv.SITE)


if __name__ == "__main__":
    unittest.main()
