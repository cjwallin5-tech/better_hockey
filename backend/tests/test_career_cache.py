import unittest
from datetime import datetime, timedelta, timezone

import api

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


class CareerCacheStale(unittest.TestCase):
    def test_fresh_and_nothing_newer_is_kept(self):
        self.assertFalse(api.career_cache_stale(NOW - timedelta(hours=3), NOW, NOW - timedelta(hours=5)))

    def test_older_than_the_ttl_is_refetched(self):
        self.assertTrue(api.career_cache_stale(NOW - timedelta(hours=25), NOW))

    def test_season_stats_updated_after_the_fetch_force_a_refetch(self):
        # fetched at 9:00, the nightly ingest rewrote the season row at 10:00
        self.assertTrue(api.career_cache_stale(NOW - timedelta(hours=3), NOW, NOW - timedelta(hours=2)))

    def test_no_season_row_falls_back_to_the_ttl_alone(self):
        self.assertFalse(api.career_cache_stale(NOW - timedelta(hours=3), NOW, None))


if __name__ == "__main__":
    unittest.main()
