"""
tests/test_superhit_features.py
Unit tests for the 4 Strategic Superhit Pillars:
1. Bank Offer & Card Discount Intelligence Engine
2. 1-Click Auto-Cart URL Generator
3. Public Web Deal Storefront & Google SEO Schema.org Product Generator
4. Multi-Platform Syndication (WhatsApp & Twitter)
5. On-Demand /deals and /glitch Bot Handlers
"""

import unittest
from unittest.mock import patch, MagicMock
from utils.bank_offers import extract_discount_from_offer_text, get_best_bank_effective_price, format_bank_offer_bulletin
from utils.auto_cart import generate_amazon_auto_cart_url, generate_flipkart_auto_cart_url, get_1click_buy_url
from web.storefront import render_storefront_html, get_live_deals_feed
from deal_engine.syndication import broadcast_to_whatsapp_channel, broadcast_to_twitter_x
from deal_engine.bot_listener import handle_deals_command


class TestSuperhitFeatures(unittest.TestCase):

    # 1. Bank Offer Parser
    def test_bank_offer_parser_percentage_and_cap(self):
        offer = "10% Instant Discount up to ₹1,500 with HDFC Bank Credit Cards"
        disc, desc = extract_discount_from_offer_text(offer, current_price=20000)
        self.assertEqual(disc, 1500.0)
        self.assertIn("10% Off", desc)

        flat_offer = "Flat ₹500 off on ICICI Bank Cards"
        flat_disc, flat_desc = extract_discount_from_offer_text(flat_offer, current_price=5000)
        self.assertEqual(flat_disc, 500.0)
        self.assertIn("Flat ₹500", flat_desc)

    def test_best_bank_effective_price(self):
        offers = [
            "10% Instant Discount up to ₹1,250 on Axis Bank Credit Cards",
            "Flat ₹2,000 Off on SBI Credit Card EMI"
        ]
        eff_price, summary = get_best_bank_effective_price(15000, offers)
        self.assertEqual(eff_price, 13000)
        self.assertIn("Flat ₹2,000 Off", summary)

    # 2. 1-Click Auto-Cart URL Generator
    def test_auto_cart_urls(self):
        amz_url = generate_amazon_auto_cart_url("B09G9BL5CP", "lootraider-21")
        self.assertIn("amazon.in/gp/aws/cart/add.html", amz_url)
        self.assertIn("ASIN.1=B09G9BL5CP", amz_url)
        self.assertIn("tag=lootraider-21", amz_url)

        fk_url = generate_flipkart_auto_cart_url("TSHGGXYZ12345", "aff123")
        self.assertIn("flipkart.com/checkout/init", fk_url)
        self.assertIn("pid=TSHGGXYZ12345", fk_url)

        auto_resolved = get_1click_buy_url("https://www.amazon.in/dp/B08N5WRWNW", "amazon", "lootraider-21")
        self.assertIsNotNone(auto_resolved)
        self.assertIn("ASIN.1=B08N5WRWNW", auto_resolved)

    # 3. Web Storefront & SEO JSON-LD
    def test_storefront_rendering_and_seo(self):
        html = render_storefront_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("application/ld+json", html)
        self.assertIn("schema.org", html)
        self.assertIn("Project Loot Raiders", html)

    # 4. Multi-Platform Syndication
    @patch("requests.post")
    def test_whatsapp_syndication(self, mock_post):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_post.return_value = mock_res

        deal = {
            "title": "Apple iPhone 15 (128 GB) - Blue",
            "price": 65999,
            "mrp": 79900,
            "discount": 17.0,
            "affiliate_url": "https://amzn.to/iphone15"
        }
        settings = {
            "whatsapp_api_token": "valid_token_123",
            "whatsapp_phone_number_id": "1000123456",
            "whatsapp_broadcast_target": "919876543210"
        }
        success = broadcast_to_whatsapp_channel(deal, settings)
        self.assertTrue(success)
        mock_post.assert_called_once()

    # 5. On-Demand /deals Bot Command Handler
    @patch("deal_engine.bot_listener.send_bot_message")
    def test_handle_deals_bot_command(self, mock_send):
        handle_deals_command(bot_token="test_token", chat_id="123456", is_glitch=False)
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        self.assertEqual(args[0], "test_token")
        self.assertEqual(args[1], "123456")


if __name__ == "__main__":
    unittest.main()
