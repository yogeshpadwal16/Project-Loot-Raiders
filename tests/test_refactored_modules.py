"""
Comprehensive Unit & Integration Test Suite for the 5 Refactored Enterprise Modules:
1. URL Unshortener & Normalizer (utils/normalizer.py)
2. Atomic Redis Deduplication (database/deduplicator.py)
3. Multi-Tier Monetization Converter (utils/converter.py)
4. Anti-Bot Playwright/JSON-LD Scraper (scrapers/anti_bot_scraper.py)
5. Async Queue Manager & Decoupler (deal_engine/queue_manager.py)
"""

import unittest
import asyncio
from utils.normalizer import resolve_final_url, get_canonical_product_id, extract_amazon_asin, extract_flipkart_pid
from database.deduplicator import is_duplicate_and_lock, release_lock
from utils.converter import monetize_url
from scrapers.anti_bot_scraper import extract_json_ld_microdata, scrape_product_live
from deal_engine.queue_manager import process_deal_job


class TestRefactoredModules(unittest.TestCase):

    def test_01_url_unshortening_and_canonical_id(self):
        """Tests URL expansion, ASIN, PID extraction, and canonical key creation."""
        # Amazon ASIN Extraction
        amazon_url = "https://www.amazon.in/dp/B0B39C29XX?ref_=chk_qd_mpt"
        asin = extract_amazon_asin(amazon_url)
        self.assertEqual(asin, "B0B39C29XX")

        canonical_key, platform = get_canonical_product_id(amazon_url)
        self.assertEqual(canonical_key, "AMAZON:B0B39C29XX")
        self.assertEqual(platform, "amazon")

        # Flipkart PID Extraction
        flipkart_url = "https://www.flipkart.com/product/p/itmd?pid=MOBG6VF5CHW9ZXYZ"
        pid = extract_flipkart_pid(flipkart_url)
        self.assertEqual(pid, "MOBG6VF5CHW9ZXYZ")

        canonical_fk, platform_fk = get_canonical_product_id(flipkart_url)
        self.assertEqual(canonical_fk, "FLIPKART:MOBG6VF5CHW9ZXYZ")
        self.assertEqual(platform_fk, "flipkart")

    def test_02_atomic_deduplication(self):
        """Tests atomic deduplication locking (SET NX logic)."""
        from unittest.mock import patch
        with patch("database.deduplicator._get_redis_client", return_value=None):
            test_key = "test_asin_unique_9999"
            release_lock(test_key)

            # First acquisition must return False (Not a duplicate!)
            is_dup_1 = is_duplicate_and_lock(test_key, ttl_seconds=60)
            self.assertFalse(is_dup_1)

            # Second acquisition must return True (Duplicate suppressed!)
            is_dup_2 = is_duplicate_and_lock(test_key, ttl_seconds=60)
            self.assertTrue(is_dup_2)

            # Clean up
            release_lock(test_key)

    def test_03_multitier_monetization_converter(self):
        """Tests 3-tier fallback monetization engine."""
        amazon_raw = "https://www.amazon.in/dp/B09G9BL5CP?utm_source=telegram&ref=bad"
        monetized_url, platform, auto_cart = monetize_url(amazon_raw)
        
        self.assertIn("tag=lootraiders-21", monetized_url)
        self.assertEqual(platform, "amazon")
        self.assertIsNotNone(auto_cart)
        self.assertIn("ASIN.1=B09G9BL5CP", auto_cart)

    def test_04_json_ld_microdata_parsing(self):
        """Tests JSON-LD microdata extraction from structured HTML."""
        sample_html = '''
        <html>
        <head>
          <script type="application/ld+json">
          {
            "@type": "Product",
            "name": "Sony WH-1000XM5 Noise Cancelling Headphones",
            "image": "https://images.unsplash.com/photo-1505740420928",
            "brand": {"name": "Sony"},
            "offers": {
              "@type": "Offer",
              "price": "24990",
              "priceCurrency": "INR",
              "availability": "https://schema.org/InStock"
            }
          }
          </script>
        </head>
        </html>
        '''
        data = extract_json_ld_microdata(sample_html)
        self.assertIsNotNone(data)
        self.assertEqual(data["title"], "Sony WH-1000XM5 Noise Cancelling Headphones")
        self.assertEqual(data["price"], 24990.0)
        self.assertTrue(data["in_stock"])

    def test_05_async_queue_job_processing(self):
        """Tests async queue job processing end-to-end workflow."""
        from unittest.mock import patch
        with patch("database.deduplicator._get_redis_client", return_value=None), \
             patch("deal_engine.queue_manager.scrape_product_live_async", return_value={"title": "Apple MacBook Air", "price": 69990.0, "in_stock": True}):
            test_payload = {
                "raw_url": "https://www.amazon.in/dp/B08N5WRWNW",
                "title": "Apple MacBook Air Laptop M1",
                "price": 69990.0,
                "mrp": 99900.0
            }

            # Clear any lock
            release_lock("AMAZON:B08N5WRWNW")

            res = asyncio.run(process_deal_job(test_payload))
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["canonical_id"], "AMAZON:B08N5WRWNW")
            self.assertIn("tag=lootraiders-21", res["monetized_url"])

            # Clean up
            release_lock("AMAZON:B08N5WRWNW")


if __name__ == "__main__":
    unittest.main()
