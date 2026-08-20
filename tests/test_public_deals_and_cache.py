import unittest
import time
import json
import os
from unittest.mock import patch, MagicMock
from web.server import (
    ScraperAPIHandler,
    _PUBLIC_DEALS_CACHE,
    _PUBLIC_DEALS_LOCK,
    get_cached_public_deals
)

class TestPublicDealsAndCache(unittest.TestCase):

    def setUp(self):
        # Reset cache before each test
        with _PUBLIC_DEALS_LOCK:
            _PUBLIC_DEALS_CACHE["data"] = None
            _PUBLIC_DEALS_CACHE["file_mtime"] = 0.0
            _PUBLIC_DEALS_CACHE["last_checked"] = 0.0

    def test_is_authorized_allows_public_deals(self):
        handler = MagicMock()
        handler.path = "/api/deals/public?limit=10"
        handler.headers = {}
        is_auth = ScraperAPIHandler.is_authorized(handler)
        self.assertTrue(is_auth, "/api/deals/public must be authorized without credentials")

    def test_is_authorized_rejects_unauthenticated_admin_deals(self):
        handler = MagicMock()
        handler.path = "/api/deals"
        handler.headers = {}
        is_auth = ScraperAPIHandler.is_authorized(handler)
        self.assertFalse(is_auth, "/api/deals should require authentication")

    def test_is_authorized_rejects_unauthenticated_settings(self):
        handler = MagicMock()
        handler.path = "/api/settings"
        handler.headers = {}
        is_auth = ScraperAPIHandler.is_authorized(handler)
        self.assertFalse(is_auth, "/api/settings must require authentication")

    def test_reads_precomputed_snapshot_without_sqlite(self):
        sample_deals = [
            {"id": "DEAL1", "platform": "amazon", "title": "Deal 1", "price": 100, "deal_score": 85},
            {"id": "DEAL2", "platform": "flipkart", "title": "Deal 2", "price": 200, "deal_score": 90}
        ]

        # Ensure SessionLocal (SQLite) is NOT called on get_cached_public_deals()
        with patch("web.server.SessionLocal", side_effect=AssertionError("SQLite must NEVER be called")):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getmtime", return_value=12345.0):
                    with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(sample_deals))):
                        res = get_cached_public_deals()
                        self.assertEqual(len(res), 2)
                        self.assertEqual(res[0]["id"], "DEAL1")
                        self.assertEqual(res[1]["id"], "DEAL2")

    def test_in_memory_cache_hit_performance(self):
        sample_deals = [{"id": "D1", "platform": "amazon", "title": "D1", "price": 50}]

        with _PUBLIC_DEALS_LOCK:
            _PUBLIC_DEALS_CACHE["data"] = sample_deals
            _PUBLIC_DEALS_CACHE["last_checked"] = time.time()

        t0 = time.time()
        res = get_cached_public_deals()
        dt_ms = (time.time() - t0) * 1000

        self.assertEqual(len(res), 1)
        self.assertLess(dt_ms, 2.0, "Cache hit must complete in < 2ms")

    def test_missing_or_corrupted_snapshot_fails_safely(self):
        # Scenario A: File does not exist
        with patch("os.path.exists", return_value=False):
            res = get_cached_public_deals()
            self.assertEqual(res, [], "Must return empty list if snapshot is missing")

        # Scenario B: File contains invalid JSON
        with patch("os.path.exists", return_value=True):
            with patch("os.path.getmtime", return_value=99999.0):
                with patch("builtins.open", unittest.mock.mock_open(read_data="INVALID_JSON")):
                    res = get_cached_public_deals()
                    self.assertEqual(res, [], "Must return empty list gracefully on parse error")

if __name__ == "__main__":
    unittest.main()
