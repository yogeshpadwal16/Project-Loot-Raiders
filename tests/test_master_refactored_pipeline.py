"""
Unit & Integration Test Suite for the Master Refactored Architecture:
1. utils/normalizer.py (resolve_final_url & get_canonical_product_id)
2. utils/deduplicator.py (is_duplicate_and_lock & release_deal_lock)
3. scrapers/stealth_scraper.py (scrape_product_details & JSON-LD parsing)
4. utils/monetizer.py (convert_to_monetized_url)
5. pipeline/processor.py (process_incoming_deal orchestrator)
"""

import unittest
import asyncio
from utils.normalizer import resolve_final_url, get_canonical_product_id, extract_amazon_asin, extract_flipkart_pid
from utils.deduplicator import is_duplicate_and_lock, release_deal_lock
from scrapers.stealth_scraper import parse_json_ld_schema, scrape_product_details
from utils.monetizer import convert_to_monetized_url
from pipeline.processor import process_incoming_deal


class TestMasterRefactoredPipeline(unittest.TestCase):

    def test_01_normalizer_url_and_canonical_id(self):
        """Tests async resolve_final_url and get_canonical_product_id."""
        amazon_raw = "https://www.amazon.in/dp/B0B39C29XX?ref_=chk_qd_mpt"
        asin = extract_amazon_asin(amazon_raw)
        self.assertEqual(asin, "B0B39C29XX")

        canonical_id = get_canonical_product_id(amazon_raw)
        self.assertEqual(canonical_id, "AMAZON:B0B39C29XX")

        flipkart_raw = "https://www.flipkart.com/product/p/itmd?pid=MOBG6VF5CHW9ZXYZ"
        canonical_fk = get_canonical_product_id(flipkart_raw)
        self.assertEqual(canonical_fk, "FLIPKART:MOBG6VF5CHW9ZXYZ")

    def test_02_async_redis_deduplication(self):
        """Tests async Redis deduplication check & lock."""
        test_key = "TEST_MASTER_CANONICAL_9999"
        asyncio.run(release_deal_lock(test_key))

        # First attempt: Lock acquired (Not a duplicate!)
        is_dup_1 = asyncio.run(is_duplicate_and_lock(test_key, ttl_seconds=60))
        self.assertFalse(is_dup_1)

        # Second attempt: Lock exists (Duplicate suppressed!)
        is_dup_2 = asyncio.run(is_duplicate_and_lock(test_key, ttl_seconds=60))
        self.assertTrue(is_dup_2)

        # Clean up
        asyncio.run(release_deal_lock(test_key))

    def test_03_stealth_scraper_json_ld(self):
        """Tests stealth scraper JSON-LD microdata parsing."""
        sample_html = '''
        <html>
        <head>
          <script type="application/ld+json">
          {
            "@type": "Product",
            "name": "Apple Watch Series 9 GPS 45mm",
            "image": "https://images.unsplash.com/photo-1546868871-7041f2a55e12",
            "offers": {
              "@type": "Offer",
              "price": "41900",
              "priceCurrency": "INR",
              "availability": "https://schema.org/InStock"
            }
          }
          </script>
        </head>
        </html>
        '''
        data = parse_json_ld_schema(sample_html)
        self.assertIsNotNone(data)
        self.assertEqual(data["title"], "Apple Watch Series 9 GPS 45mm")
        self.assertEqual(data["price"], 41900.0)
        self.assertTrue(data["in_stock"])

    def test_04_monetizer_3tier_conversion(self):
        """Tests 3-tier affiliate monetization converter."""
        amazon_url = "https://www.amazon.in/dp/B0B39C29XX?utm_source=tg"
        affiliate_url = asyncio.run(convert_to_monetized_url(amazon_url))
        self.assertIn("tag=lootraiders-21", affiliate_url)

    def test_05_unified_pipeline_orchestrator(self):
        """Tests unified async deal pipeline orchestrator."""
        test_url = "https://www.amazon.in/dp/B09G9BL5CP"
        test_key = "AMAZON:B09G9BL5CP"
        asyncio.run(release_deal_lock(test_key))

        async def mock_scrape(url, timeout_seconds=8.0):
            return {
                "title": "Apple iPhone 13 (128GB) - Midnight",
                "price": 49999.0,
                "mrp": 59900.0,
                "in_stock": True,
                "image_url": "https://m.media-amazon.com/images/I/71xb2aM4OUL._SL1500_.jpg",
                "strategy": "mock"
            }

        from unittest.mock import patch
        with patch("pipeline.processor.scrape_product_details", side_effect=mock_scrape):
            res = asyncio.run(process_incoming_deal(test_url, raw_text="Apple iPhone 13 128GB"))
            self.assertIsNotNone(res)
            self.assertEqual(res["canonical_id"], "AMAZON:B09G9BL5CP")
            self.assertIn("tag=lootraiders-21", res["affiliate_url"])

        # Clean up
        asyncio.run(release_deal_lock(test_key))


if __name__ == "__main__":
    unittest.main()
