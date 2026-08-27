"""
tests/test_flipkart_monetization.py
Targeted test suite for Flipkart Affiliate Monetization:
- PID extraction across query params, standard path, itm paths, and variable length IDs
- Fallback affiliate tagging when unconfigured or using placeholder
- Direct affiliate URL structure
- Direct Add-To-Cart generation
- Safe preservation of non-PID URLs
"""

import unittest
from utils.parser import extract_flipkart_pid as parser_extract_pid
from utils.normalizer import extract_flipkart_pid as normalizer_extract_pid
from utils.affiliate import get_best_affiliate_url, generate_auto_cart_url
from utils.monetizer import convert_to_monetized_url
import asyncio

class TestFlipkartMonetization(unittest.TestCase):

    def test_pid_extraction_variants(self):
        """Test Flipkart PID extraction across various URL structures and lengths."""
        test_urls = [
            ("https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm1234567890abc?pid=MOBFWBYZ8GUJTGQN", "MOBFWBYZ8GUJTGQN"),
            ("https://www.flipkart.com/product/p/itm?pid=TSHG4V2NDFEYDKTG", "TSHG4V2NDFEYDKTG"),
            ("https://www.flipkart.com/p/ACCFWXYZ1234", "ACCFWXYZ1234"),
            ("https://dl.flipkart.com/dl/p/itm987654321012?pid=MOB123456789", "MOB123456789"),
            ("https://www.flipkart.com/item/itm1a2b3c4d5e6f", "itm1a2b3c4d5e6f")
        ]
        for url, expected_pid in test_urls:
            self.assertEqual(parser_extract_pid(url), expected_pid)
            self.assertEqual(normalizer_extract_pid(url), expected_pid)

    def test_affiliate_tagging_with_configured_affid(self):
        """Verify Flipkart links receive configured affid."""
        settings = {"flipkart_affid": "custompartner"}
        url = "https://www.flipkart.com/product/p/itm?pid=MOBFWBYZ8GUJTGQN"
        aff_url = get_best_affiliate_url(url, "flipkart", settings)
        self.assertEqual(aff_url, "https://www.flipkart.com/product/p/itm?pid=MOBFWBYZ8GUJTGQN&affid=custompartner")

    def test_affiliate_tagging_with_placeholder_or_empty_affid(self):
        """Verify Flipkart links fall back to default 'lootraiders' tag when placeholder is set."""
        settings = {"flipkart_affid": "YOUR_FLIPKART_AFFILIATE_ID"}
        url = "https://www.flipkart.com/product/p/itm?pid=TSHG4V2NDFEYDKTG"
        aff_url = get_best_affiliate_url(url, "flipkart", settings)
        self.assertEqual(aff_url, "https://www.flipkart.com/product/p/itm?pid=TSHG4V2NDFEYDKTG&affid=lootraiders")

    def test_auto_cart_url_generation(self):
        """Verify direct Add-to-Cart URL formatting for Flipkart."""
        settings = {"flipkart_affid": "customcartid"}
        url = "https://www.flipkart.com/product/p/itm?pid=MOBFWBYZ8GUJTGQN"
        cart_url = generate_auto_cart_url(url, "flipkart", settings)
        self.assertEqual(cart_url, "https://www.flipkart.com/co/add-to-cart?pid=MOBFWBYZ8GUJTGQN&affid=customcartid")

    def test_non_pid_flipkart_url_safe_tagging(self):
        """Verify deals without direct PIDs preserve path & params and append affid."""
        settings = {"flipkart_affid": "partner123"}
        url = "https://www.flipkart.com/offers-list/super-deals?category=fashion"
        aff_url = get_best_affiliate_url(url, "flipkart", settings)
        self.assertIn("affid=partner123", aff_url)
        self.assertIn("category=fashion", aff_url)

    def test_async_monetizer_flipkart(self):
        """Verify async convert_to_monetized_url formats Flipkart product links."""
        url = "https://www.flipkart.com/product/p/itm?pid=MOBFWBYZ8GUJTGQN"
        result = asyncio.run(convert_to_monetized_url(url))
        self.assertIn("pid=MOBFWBYZ8GUJTGQN", result)
        self.assertIn("affid=", result)

if __name__ == "__main__":
    unittest.main()
