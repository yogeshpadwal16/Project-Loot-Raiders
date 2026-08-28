"""
tests/test_phase6b_conversion_and_cart.py
Unit and integration tests for Phase 6B:
- Amazon & Flipkart 1-Click Add-to-Cart URL Generation
- Unsupported retailer fallback (only BUY NOW)
- Malformed ASIN/PID handling
- Telegram Notifier Dual-CTA Button construction
- Cloaker /go/{unique_id} redirect with ?cta=buy and ?cta=cart
- Non-blocking ClickLog persistence and fail-safe redirect on DB error
- 404 on invalid deal ID
"""

import os
import sys
import time
import io
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.affiliate import get_best_affiliate_url, generate_auto_cart_url
from deal_engine.notifier import send_deal_notification, send_telegram_alert
from knowledge_base.models import Product, PriceHistory, ClickLog
from database.db_session import SessionLocal, init_db
from web.server import ScraperAPIHandler


class MockServerRequest:
    def __init__(self, path, client_ip="127.0.0.1", user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"):
        self.path = path
        self.client_address = (client_ip, 12345)
        self.headers = {"User-Agent": user_agent}
        self.wfile = io.BytesIO()
        self.response_code = None
        self.response_headers = {}

    def send_response(self, code):
        self.response_code = code

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass

    def is_authorized(self):
        return True


class TestPhase6BConversionAndCart(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db = SessionLocal()
        self.settings = {
            "telegram_bot_token": "TEST_MOCK_TOKEN",
            "telegram_chat_id": "@test_channel",
            "amazon_tag": "lootraiders-21",
            "flipkart_affid": "lootraiders",
            "cuelinks_pub_id": "",
            "earnkaro_pub_id": "",
            "enable_auto_cart_button": True
        }
        # Clean test products
        self.db.query(ClickLog).filter(ClickLog.product_id.like("test_p6b_%")).delete()
        self.db.query(PriceHistory).filter(PriceHistory.product_id.like("test_p6b_%")).delete()
        self.db.query(Product).filter(Product.id.like("test_p6b_%")).delete()
        self.db.commit()

        # Insert test product
        p = Product(
            id="test_p6b_amz_item",
            platform="amazon",
            title="Amazon Wireless Earbuds",
            url="https://www.amazon.in/dp/B0D1234567?tag=lootraiders-21",
            created_at=datetime.utcnow()
        )
        self.db.add(p)
        self.db.commit()

    def tearDown(self):
        self.db.query(ClickLog).filter(ClickLog.product_id.like("test_p6b_%")).delete()
        self.db.query(PriceHistory).filter(PriceHistory.product_id.like("test_p6b_%")).delete()
        self.db.query(Product).filter(Product.id.like("test_p6b_%")).delete()
        self.db.commit()
        self.db.close()

    def test_01_amazon_buy_now_and_add_to_cart_urls(self):
        """Verify Amazon generates valid direct affiliate BUY NOW and ADD TO CART URLs."""
        raw_url = "https://www.amazon.in/dp/B0D1234567"
        buy_url = get_best_affiliate_url(raw_url, "amazon", self.settings)
        cart_url = generate_auto_cart_url(raw_url, "amazon", self.settings)

        self.assertIn("tag=lootraiders-21", buy_url)
        self.assertIn("/dp/B0D1234567", buy_url)
        self.assertIsNotNone(cart_url)
        self.assertIn("ASIN.1=B0D1234567", cart_url)
        self.assertIn("tag=lootraiders-21", cart_url)
        self.assertIn("/gp/aws/cart/add.html", cart_url)

    def test_02_flipkart_buy_now_and_add_to_cart_urls(self):
        """Verify Flipkart generates valid direct affiliate BUY NOW and ADD TO CART URLs."""
        raw_url = "https://www.flipkart.com/product/p/itm?pid=MOBG123456789ABC"
        buy_url = get_best_affiliate_url(raw_url, "flipkart", self.settings)
        cart_url = generate_auto_cart_url(raw_url, "flipkart", self.settings)

        self.assertIn("affid=lootraiders", buy_url)
        self.assertIn("pid=MOBG123456789ABC", buy_url)
        self.assertIsNotNone(cart_url)
        self.assertIn("pid=MOBG123456789ABC", cart_url)
        self.assertIn("affid=lootraiders", cart_url)
        self.assertIn("/co/add-to-cart", cart_url)

    def test_03_unsupported_retailer_returns_none_for_cart(self):
        """Unsupported retailers (Myntra/Ajio) return None for add-to-cart."""
        myntra_url = "https://www.myntra.com/shoes/nike/123456/buy"
        cart_url = generate_auto_cart_url(myntra_url, "myntra", self.settings)
        self.assertIsNone(cart_url)

        ajio_url = "https://www.ajio.com/puma-sneakers/p/461234567_white"
        cart_url = generate_auto_cart_url(ajio_url, "ajio", self.settings)
        self.assertIsNone(cart_url)

    def test_04_malformed_asin_or_pid_handled_safely(self):
        """Malformed product URLs safely return None for auto cart without raising exceptions."""
        malformed_amazon = "https://www.amazon.in/some-invalid-page"
        cart_url = generate_auto_cart_url(malformed_amazon, "amazon", self.settings)
        self.assertIsNone(cart_url)

        malformed_flipkart = "https://www.flipkart.com/view-all"
        cart_url = generate_auto_cart_url(malformed_flipkart, "flipkart", self.settings)
        self.assertIsNone(cart_url)

    def test_05_telegram_notifier_exposes_dual_cta_for_amazon(self):
        """send_deal_notification should attach inline keyboard with BUY NOW and ADD TO CART for Amazon."""
        deal_payload = {
            "id": "test_p6b_amz_1",
            "title": "Amazon Deal with Dual CTA",
            "price": 1499.0,
            "mrp": 3999.0,
            "discount": 62.5,
            "platform": "amazon",
            "affiliate_url": "https://www.amazon.in/dp/B0D1234567?tag=lootraiders-21"
        }

        with patch("deal_engine.notifier.load_settings", return_value=self.settings),              patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_post.return_value = mock_resp

            success = send_deal_notification(deal_payload)
            self.assertTrue(success)
            self.assertTrue(mock_post.called)

            args, kwargs = mock_post.call_args
            payload = kwargs.get("json", {})
            reply_markup = payload.get("reply_markup", {})
            buttons = reply_markup.get("inline_keyboard", [[]])[0]

            self.assertEqual(len(buttons), 2)
            self.assertIn("BUY NOW", buttons[0]["text"])
            self.assertIn("ADD TO CART", buttons[1]["text"])
            self.assertIn("/gp/aws/cart/add.html", buttons[1]["url"])

    def test_06_telegram_notifier_single_cta_for_unsupported_retailer(self):
        """send_deal_notification attaches single BUY NOW CTA for Myntra/Ajio."""
        deal_payload = {
            "id": "test_p6b_myntra_1",
            "title": "Myntra Deal with Single CTA",
            "price": 899.0,
            "mrp": 1999.0,
            "discount": 55.0,
            "platform": "myntra",
            "affiliate_url": "https://www.myntra.com/tshirt/123456"
        }

        with patch("deal_engine.notifier.load_settings", return_value=self.settings),              patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_post.return_value = mock_resp

            success = send_deal_notification(deal_payload)
            self.assertTrue(success)

            args, kwargs = mock_post.call_args
            payload = kwargs.get("json", {})
            reply_markup = payload.get("reply_markup", {})
            buttons = reply_markup.get("inline_keyboard", [[]])[0]

            self.assertEqual(len(buttons), 1)
            self.assertIn("BUY NOW", buttons[0]["text"])

    def test_07_send_telegram_alert_routes_cloaker_buttons_when_configured(self):
        """When cloaker_domain is set, send_telegram_alert routes inline buttons through /go/."""
        settings_with_cloaker = dict(self.settings)
        settings_with_cloaker["cloaker_domain"] = "https://deals.lootraiders.in"

        with patch("deal_engine.notifier.load_settings", return_value=settings_with_cloaker),              patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_post.return_value = mock_resp

            success = send_telegram_alert(
                bot_token="TEST_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Apple MacBook Air M2",
                price=79990,
                mrp=99900,
                discount=20.0,
                img_url="https://m.media-amazon.com/images/I/71.jpg",
                final_url="https://www.amazon.in/dp/B0D1234567?tag=lootraiders-21",
                is_verified_low=True,
                deal_score=85.0,
                unique_id="test_p6b_amz_macbook"
            )
            self.assertTrue(success)

            call_found = False
            for c in mock_post.call_args_list:
                kwargs = c[1]
                data = kwargs.get("data") or kwargs.get("json") or {}
                rm = data.get("reply_markup")
                if rm:
                    call_found = True
                    import json
                    if isinstance(rm, str):
                        rm = json.loads(rm)
                    buttons = rm.get("inline_keyboard", [[]])[0]
                    self.assertEqual(len(buttons), 2)
                    self.assertIn("https://deals.lootraiders.in/go/test_p6b_amz_macbook?cta=buy&src=telegram", buttons[0]["url"])
                    self.assertIn("https://deals.lootraiders.in/go/test_p6b_amz_macbook?cta=cart&src=telegram", buttons[1]["url"])
            self.assertTrue(call_found)

    def test_08_go_route_records_click_and_redirects_buy(self):
        """HTTP GET /go/{id}?cta=buy logs click with user='telegram:buy' and returns HTTP 302 to product URL."""
        req = MockServerRequest("/go/test_p6b_amz_item?cta=buy&src=telegram")
        ScraperAPIHandler.do_GET(req)

        self.assertEqual(req.response_code, 302)
        self.assertEqual(req.response_headers.get("Location"), "https://www.amazon.in/dp/B0D1234567?tag=lootraiders-21")

        # Verify ClickLog in DB
        click = self.db.query(ClickLog).filter_by(product_id="test_p6b_amz_item").first()
        self.assertIsNotNone(click)
        self.assertEqual(click.user, "telegram:buy")

    def test_09_go_route_records_click_and_redirects_cart(self):
        """HTTP GET /go/{id}?cta=cart logs click with user='telegram:cart' and returns HTTP 302 to cart URL."""
        req = MockServerRequest("/go/test_p6b_amz_item?cta=cart&src=telegram", client_ip="127.0.0.2")
        ScraperAPIHandler.do_GET(req)

        self.assertEqual(req.response_code, 302)
        self.assertIn("/gp/aws/cart/add.html", req.response_headers.get("Location"))
        self.assertIn("ASIN.1=B0D1234567", req.response_headers.get("Location"))

        # Verify ClickLog in DB
        clicks = self.db.query(ClickLog).filter_by(product_id="test_p6b_amz_item").all()
        self.assertTrue(any(c.user.startswith("telegram:cart") for c in clicks))

    def test_10_go_route_failsafe_redirects_even_if_db_fails(self):
        """If ClickLog database write fails, /go/ STILL returns HTTP 302 to target URL."""
        req = MockServerRequest("/go/test_p6b_amz_item?cta=buy&src=telegram")
        with patch.object(ClickLog, "__init__", side_effect=Exception("Database lock error")):
            ScraperAPIHandler.do_GET(req)

        self.assertEqual(req.response_code, 302)
        self.assertEqual(req.response_headers.get("Location"), "https://www.amazon.in/dp/B0D1234567?tag=lootraiders-21")

    def test_11_go_route_returns_404_on_invalid_deal(self):
        """HTTP GET /go/non_existent_id returns HTTP 404."""
        req = MockServerRequest("/go/non_existent_99999")
        ScraperAPIHandler.do_GET(req)

        self.assertEqual(req.response_code, 404)


if __name__ == "__main__":
    unittest.main()
