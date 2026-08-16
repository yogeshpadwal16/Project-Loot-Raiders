import unittest
import time
import json
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
            _PUBLIC_DEALS_CACHE["cached_at"] = 0.0

    def test_is_authorized_allows_public_deals(self):
        handler = MagicMock()
        handler.path = "/api/deals/public?limit=50"
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

    def test_cache_population_and_reuse(self):
        sample_deals = [
            {"id": "TEST1", "platform": "amazon", "title": "Deal 1", "price": 100, "deal_score": 85},
            {"id": "TEST2", "platform": "flipkart", "title": "Deal 2", "price": 200, "deal_score": 90}
        ]
        
        # Populate cache directly or simulate DB retrieval
        with _PUBLIC_DEALS_LOCK:
            _PUBLIC_DEALS_CACHE["data"] = sample_deals
            _PUBLIC_DEALS_CACHE["cached_at"] = time.time()

        cached_data = get_cached_public_deals()
        self.assertEqual(len(cached_data), 2)
        self.assertEqual(cached_data[0]["id"], "TEST1")

    def test_stale_while_revalidate_on_error(self):
        initial_deals = [{"id": "STALE1", "platform": "amazon", "title": "Stale Deal", "price": 500, "deal_score": 80}]
        
        # Set cache with expired timestamp
        with _PUBLIC_DEALS_LOCK:
            _PUBLIC_DEALS_CACHE["data"] = initial_deals
            _PUBLIC_DEALS_CACHE["cached_at"] = time.time() - 100.0  # Expired

        # Simulate database exception during refresh
        with patch("web.server.SessionLocal", side_effect=Exception("Database locked")):
            res = get_cached_public_deals()
            # Must return the stale cache safely rather than raising an error or returning []
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["id"], "STALE1")

    def test_snapshot_fallback_when_cache_empty_and_db_fails(self):
        with _PUBLIC_DEALS_LOCK:
            _PUBLIC_DEALS_CACHE["data"] = None
            _PUBLIC_DEALS_CACHE["cached_at"] = 0.0

        snapshot_mock = [{"id": "SNAP1", "platform": "amazon", "title": "Snapshot Deal", "price": 99}]
        
        with patch("web.server.SessionLocal", side_effect=Exception("Database locked")):
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(snapshot_mock))):
                    res = get_cached_public_deals()
                    self.assertEqual(len(res), 1)
                    self.assertEqual(res[0]["id"], "SNAP1")

if __name__ == "__main__":
    unittest.main()
