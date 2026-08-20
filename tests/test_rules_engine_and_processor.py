"""
tests/test_rules_engine_and_processor.py
Unit tests for India Free Stuff Rules Engine & Fail-Safe Resilient Processor.
"""

import unittest
import asyncio
from unittest.mock import patch
from utils.rules_engine import evaluate_deal_eligibility
from pipeline.processor import process_incoming_deal, extract_price_from_text, extract_title_from_text
from utils.deduplicator import release_deal_lock


class TestRulesEngineAndProcessor(unittest.TestCase):

    def test_01_rules_engine_evaluation(self):
        # Loot deal (80%+ off)
        res_loot = evaluate_deal_eligibility(mrp=10000.0, current_price=1200.0, category="general")
        self.assertTrue(res_loot["approved"])
        self.assertEqual(res_loot["tier"], "LOOT_DEAL")
        self.assertTrue(res_loot["is_loot"])

        # Category threshold (Electronics 25% min required)
        res_elec_pass = evaluate_deal_eligibility(mrp=5000.0, current_price=3000.0, category="electronics")
        self.assertTrue(res_elec_pass["approved"])

        res_elec_fail = evaluate_deal_eligibility(mrp=5000.0, current_price=4800.0, category="electronics")
        self.assertFalse(res_elec_fail["approved"])

        # Seller trap (< 3.5 rating)
        res_seller = evaluate_deal_eligibility(mrp=1000.0, current_price=200.0, seller_rating=2.8)
        self.assertFalse(res_seller["approved"])

    def test_02_text_extraction(self):
        sample_text = "🔥 HOT LOOT DEAL 🔥\nSamsung Galaxy S24 Ultra 5G\nPrice: Rs. 99,990 (MRP: Rs. 139,990)\nBuy Now: https://amzn.to/test"
        title = extract_title_from_text(sample_text)
        price = extract_price_from_text(sample_text)

        self.assertEqual(title, "Samsung Galaxy S24 Ultra 5G")
        self.assertEqual(price, 99990.0)

    def test_03_resilient_processor_text_fallback(self):
        # Raw deal with shortlink and text fallback payload
        test_text = "Apple AirPods Pro (2nd Gen)\nPrice: ₹18,990 (MRP: ₹26,900)\nGrab: https://amzn.to/3xyz"
        raw_url = "https://www.amazon.in/dp/B09G9BL5CP"

        asyncio.run(release_deal_lock("AMAZON:B09G9BL5CP"))

        # Mock scraper failure to force Text Fallback Mode
        async def mock_scrape_fail(url, timeout_seconds=8.0):
            return None

        with patch("pipeline.processor.scrape_product_details", side_effect=mock_scrape_fail):
            result = asyncio.run(process_incoming_deal(raw_url, raw_text=test_text))
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "APPROVED")
            self.assertIn("AirPods", result["title"])
            self.assertTrue(result["price"] > 0)
            self.assertIn("tag=lootraiders-21", result["affiliate_url"])

        asyncio.run(release_deal_lock("AMAZON:B09G9BL5CP"))


if __name__ == "__main__":
    unittest.main()
