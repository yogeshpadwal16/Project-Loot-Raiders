"""
tests/test_performance_phase1.py
Unit and integration tests for Phase 1 Performance Optimization:
- Shared Playwright Browser Lifecycle
- Multi-ASIN Store & Search URL Decomposition
- Lightweight HTTP Fast-Path with Playwright Fallback
- Generic Search URL Early Skip
- Deal Qualification & Rules Integrity
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

from utils.parser import extract_amazon_asin, extract_amazon_asins_from_url, is_valid_asin
from utils.playwright_adapter import (
    get_playwright_driver,
    shutdown_shared_browser,
    _get_shared_browser,
    PlaywrightSeleniumAdapter
)
from deal_engine.mirroring.processor import DealMirrorProcessor
from deal_engine.mirroring.schemas import NormalizedMessage
from core.engine import scrape_product_details
from utils.rules_engine import evaluate_deal_eligibility
from deal_engine.scorer import calculate_deal_score


class TestPerformancePhase1(unittest.TestCase):

    def setUp(self):
        mock_queue = MagicMock()
        self.processor = DealMirrorProcessor(queue=mock_queue)

    # 1. Amazon direct ASIN URL
    def test_amazon_direct_dp_asin(self):
        url = "https://www.amazon.in/Samsung-Galaxy-Storage-Purchased-Separately/dp/B0D25Z6ZHC?th=1&tag=aff-21"
        asin = extract_amazon_asin(url)
        self.assertEqual(asin, "B0D25Z6ZHC")
        asins = extract_amazon_asins_from_url(url)
        self.assertEqual(asins, ["B0D25Z6ZHC"])

    # 2. Amazon /gp/product/ASIN
    def test_amazon_gp_product_asin(self):
        url = "https://www.amazon.in/gp/product/B091MJRMXQ?ref=ppx_pt2_dt_b_prod_image"
        asin = extract_amazon_asin(url)
        self.assertEqual(asin, "B091MJRMXQ")
        asins = extract_amazon_asins_from_url(url)
        self.assertEqual(asins, ["B091MJRMXQ"])

    # 3. Amazon multi-ASIN store URL
    def test_amazon_multi_asin_store_url(self):
        url = "https://www.amazon.in/stores/page/preview?isPreview=1&isSlp=1&asins=B0CQGH5DFF,B0GCMDS3X1,B0DGGYS38S&tag=sahasulata-21"
        asins = extract_amazon_asins_from_url(url)
        self.assertEqual(asins, ["B0CQGH5DFF", "B0GCMDS3X1", "B0DGGYS38S"])

    # 4. Multiple ASINs from hidden-keywords query parameter
    def test_amazon_hidden_keywords_multi_asin(self):
        url = "https://www.amazon.in/s?s=price-asc-rank&hidden-keywords=B0F2F8DZ76%2B|B0FJXKZ35N&qid=1786114923"
        asins = extract_amazon_asins_from_url(url)
        self.assertEqual(asins, ["B0F2F8DZ76", "B0FJXKZ35N"])

    # 5. Duplicate ASINs in query string
    def test_duplicate_asins_deduplicated(self):
        url = "https://www.amazon.in/stores/page/preview?asins=B0CQGH5DFF,B0CQGH5DFF,B0GCMDS3X1,B0CQGH5DFF"
        asins = extract_amazon_asins_from_url(url)
        self.assertEqual(asins, ["B0CQGH5DFF", "B0GCMDS3X1"])

    # 6. Malformed ASIN rejection
    def test_malformed_asin_rejected(self):
        self.assertFalse(is_valid_asin("INVALID_ASIN_TOO_LONG"))
        self.assertFalse(is_valid_asin("SHORT"))
        self.assertFalse(is_valid_asin("!@#$%^&*()"))
        self.assertFalse(is_valid_asin(None))
        self.assertTrue(is_valid_asin("B0CQGH5DFF"))
        self.assertTrue(is_valid_asin("0123456789"))

    # 7. Empty asins parameter handling
    def test_empty_asins_parameter(self):
        url = "https://www.amazon.in/stores/page/preview?asins=&tag=test-21"
        asins = extract_amazon_asins_from_url(url)
        self.assertEqual(asins, [])

    # 8. Amazon search URL without ASINs (Early skip without browser)
    def test_generic_amazon_search_url_skipped_without_browser(self):
        url = "https://www.amazon.in/s?k=running+shoes+for+men&crid=123"
        platform, pid = self.processor._parse_url_metadata(url)
        self.assertIsNone(pid)
        asins = extract_amazon_asins_from_url(url)
        self.assertEqual(asins, [])

    # 9. Direct product HTTP fast-path success
    @patch("deal_engine.deal_processor.scrape_product_lightweight")
    def test_direct_product_http_fast_path_success(self, mock_lightweight):
        mock_lightweight.return_value = {
            "title": "Fast Path Headphones",
            "price": 1499,
            "mrp": 2999,
            "image_url": "https://m.media-amazon.com/images/I/71xyz.jpg",
            "rating": 4.2,
            "reviews": 320
        }
        res = scrape_product_details("https://www.amazon.in/dp/B0D25Z6ZHC")
        self.assertEqual(res["title"], "Fast Path Headphones")
        self.assertEqual(res["price"], 1499)
        self.assertEqual(res["mrp"], 2999)
        mock_lightweight.assert_called_once()

    # 10. HTTP fast-path failure -> Playwright fallback
    @patch("deal_engine.deal_processor.scrape_product_lightweight")
    @patch("core.engine._scrape_product_details_fallback")
    def test_http_fast_path_failure_falls_back_to_playwright(self, mock_fallback, mock_lightweight):
        mock_lightweight.return_value = None  # HTTP fast-path failed
        mock_fallback.return_value = {
            "title": "Fallback Scraped Headphones",
            "price": 1499,
            "mrp": 2999,
            "image_url": "https://m.media-amazon.com/images/I/71xyz.jpg"
        }
        res = scrape_product_details("https://www.amazon.in/dp/B0D25Z6ZHC")
        self.assertEqual(res["title"], "Fallback Scraped Headphones")
        mock_fallback.assert_called_once()

    # 11. Browser recovery / singleton reuse without spawning multiple browser processes
    @patch("utils.playwright_adapter.sync_playwright")
    def test_shared_browser_singleton_lifecycle(self, mock_sync_pw):
        mock_pw_inst = MagicMock()
        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        mock_context1 = MagicMock()
        mock_page1 = MagicMock()
        mock_context2 = MagicMock()
        mock_page2 = MagicMock()

        mock_browser.new_context.side_effect = [mock_context1, mock_context2]
        mock_context1.new_page.return_value = mock_page1
        mock_context2.new_page.return_value = mock_page2
        mock_pw_inst.chromium.launch.return_value = mock_browser
        mock_sync_pw.return_value.start.return_value = mock_pw_inst

        # Reset global state for test
        import utils.playwright_adapter as pa
        pa._SHARED_PLAYWRIGHT = None
        pa._SHARED_BROWSER = None

        # First driver request -> launches Chromium 1 time
        driver1 = get_playwright_driver()
        self.assertEqual(mock_pw_inst.chromium.launch.call_count, 1)

        # Quitting driver1 closes context/page but leaves browser open
        driver1.quit()
        mock_page1.close.assert_called_once()
        mock_context1.close.assert_called_once()
        mock_browser.close.assert_not_called()

        # Second driver request -> reuses existing Chromium instance without launching another
        driver2 = get_playwright_driver()
        self.assertEqual(mock_pw_inst.chromium.launch.call_count, 1)  # Still 1, NOT 2!
        driver2.quit()
        mock_page2.close.assert_called_once()
        mock_context2.close.assert_called_once()
        mock_browser.close.assert_not_called()

        # Explicit shutdown closes browser and stops playwright
        shutdown_shared_browser()
        mock_browser.close.assert_called_once()
        mock_pw_inst.stop.assert_called_once()

    # 12. Qualification and Scoring Pipeline Unchanged
    def test_qualification_rules_and_scoring_unchanged(self):
        # Category threshold test
        res_approved = evaluate_deal_eligibility(mrp=20000.0, current_price=15000.0, category="smartphones", seller_rating=4.0)
        self.assertTrue(res_approved["approved"])
        self.assertEqual(res_approved["tier"], "STANDARD")

        res_rejected = evaluate_deal_eligibility(mrp=1000.0, current_price=960.0, category="electronics", seller_rating=4.0)
        self.assertFalse(res_rejected["approved"])

        # Deal score calculation test
        score = calculate_deal_score(
            platform="amazon",
            price=19490,
            mrp=27000,
            discount=27.8,
            is_verified_low=True,
            is_lightning=False,
            product_id="B0D25Z6ZHC",
            title="Samsung Galaxy M34 5G",
            rating=4.2,
            reviews=1500,
            has_bank_offer=False
        )
        self.assertGreater(score, 60.0)


if __name__ == "__main__":
    unittest.main()
