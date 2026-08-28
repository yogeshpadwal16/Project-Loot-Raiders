"""
tests/test_phase6c_analytics_and_heatmap.py
Unit and integration tests for Phase 6C:
- Real-time click analytics & attribution
- Anti-gaming click deduplication & bot filtering
- Telegram link preview detection
- Heatmap analytics aggregation & privacy protection
- Fail-safe redirect even if analytics fails
"""

import os
import sys
import time
import io
import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from deal_engine.analytics import (
    is_bot_user_agent,
    is_qualified_click,
    record_deal_click,
    get_deal_heatmap_analytics,
    hash_ip
)
from deal_engine.scorer import calculate_deal_score
from knowledge_base.models import Product, PriceHistory, ClickLog
from database.db_session import SessionLocal, init_db
from web.server import ScraperAPIHandler


class MockServerRequest:
    def __init__(self, path, client_ip="192.168.1.100", user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0) Mobile/15E148"):
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


class TestPhase6CAnalyticsAndHeatmap(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db = SessionLocal()
        # Clean test products and logs
        self.db.query(ClickLog).filter(ClickLog.product_id.like("test_p6c_%")).delete()
        self.db.query(PriceHistory).filter(PriceHistory.product_id.like("test_p6c_%")).delete()
        self.db.query(Product).filter(Product.id.like("test_p6c_%")).delete()
        self.db.commit()

        # Insert test products
        p_amz = Product(
            id="test_p6c_amz_deal",
            platform="amazon",
            title="Sony WH-1000XM5 Wireless Headphones",
            url="https://www.amazon.in/dp/B09XS7JWHH?tag=lootraiders-21",
            created_at=datetime.utcnow()
        )
        p_fk = Product(
            id="test_p6c_fk_deal",
            platform="flipkart",
            title="Apple iPad 10th Gen 64GB",
            url="https://www.flipkart.com/product/p/itm?pid=TABG123456789&affid=lootraiders",
            created_at=datetime.utcnow()
        )
        self.db.add(p_amz)
        self.db.add(p_fk)
        self.db.commit()

    def tearDown(self):
        self.db.query(ClickLog).filter(ClickLog.product_id.like("test_p6c_%")).delete()
        self.db.query(PriceHistory).filter(PriceHistory.product_id.like("test_p6c_%")).delete()
        self.db.query(Product).filter(Product.id.like("test_p6c_%")).delete()
        self.db.commit()
        self.db.close()

    def test_01_bot_user_agent_detection(self):
        """Test bot user-agent detection for scrapers and preview bots."""
        self.assertTrue(is_bot_user_agent("TelegramBot (like TwitterBot)"))
        self.assertTrue(is_bot_user_agent("facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"))
        self.assertTrue(is_bot_user_agent("python-requests/2.31.0"))
        self.assertTrue(is_bot_user_agent("Mozilla/5.0 HeadlessChrome/110.0.0.0"))
        self.assertTrue(is_bot_user_agent("WhatsApp/2.21.12.21 A"))

        # Real mobile & desktop browsers should NOT be flagged as bots
        self.assertFalse(is_bot_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0"))
        self.assertFalse(is_bot_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"))

    def test_02_qualified_click_and_rapid_click_deduplication(self):
        """Test that rapid repeated clicks from the same IP are marked as unqualified."""
        ip = "203.0.113.45"
        prod = "test_p6c_amz_deal"
        ua = "Mozilla/5.0 (Linux; Android 13; SM-S908B) Chrome/112.0.0.0 Mobile"

        # 1st click -> Qualified
        qual1 = is_qualified_click(prod, ip, ua, cooldown_seconds=60.0)
        self.assertTrue(qual1)

        # 2nd click immediately from same IP on same product -> Unqualified duplicate
        qual2 = is_qualified_click(prod, ip, ua, cooldown_seconds=60.0)
        self.assertFalse(qual2)

        # 3rd click from DIFFERENT IP -> Qualified
        qual3 = is_qualified_click(prod, "203.0.113.99", ua, cooldown_seconds=60.0)
        self.assertTrue(qual3)

    def test_03_privacy_safe_ip_hash(self):
        """Verify IP address is hashed deterministically without leaking raw IP."""
        h1 = hash_ip("192.168.1.1")
        h2 = hash_ip("192.168.1.1")
        h3 = hash_ip("192.168.1.2")

        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertNotIn("192.168", h1)
        self.assertEqual(len(h1), 16)

    def test_04_record_deal_click_stores_tag_correctly(self):
        """Test that record_deal_click writes ClickLog with proper user tag."""
        record_deal_click(
            product_id="test_p6c_amz_deal",
            title="Sony WH-1000XM5",
            client_ip="10.0.0.1",
            user_agent="TelegramBot (like TwitterBot)",
            cta="cart",
            src="telegram"
        )
        click = self.db.query(ClickLog).filter_by(product_id="test_p6c_amz_deal").first()
        self.assertIsNotNone(click)
        self.assertIn(":bot", click.user)
        self.assertIn("telegram:cart", click.user)

    def test_05_deal_heatmap_analytics_generation(self):
        """Test get_deal_heatmap_analytics calculates top deals, velocity, and CTA split."""
        # Insert 3 qualified clicks, 1 bot click, and 1 duplicate click
        now = time.time()
        c1 = ClickLog(product_id="test_p6c_amz_deal", title="Sony WH-1000XM5", ip="1.1.1.1", user="telegram:buy", timestamp=now)
        c2 = ClickLog(product_id="test_p6c_amz_deal", title="Sony WH-1000XM5", ip="1.1.1.2", user="telegram:cart", timestamp=now)
        c3 = ClickLog(product_id="test_p6c_amz_deal", title="Sony WH-1000XM5", ip="1.1.1.3", user="telegram:buy:duplicate", timestamp=now)
        c4 = ClickLog(product_id="test_p6c_amz_deal", title="Sony WH-1000XM5", ip="1.1.1.4", user="telegram:buy:bot", timestamp=now)
        c5 = ClickLog(product_id="test_p6c_fk_deal", title="Apple iPad 10th", ip="2.2.2.1", user="telegram:buy", timestamp=now)
        self.db.add_all([c1, c2, c3, c4, c5])
        self.db.commit()

        # Invalidate cache
        from deal_engine.analytics import _HEATMAP_CACHE
        _HEATMAP_CACHE["last_computed"] = 0.0

        heatmap = get_deal_heatmap_analytics(lookback_hours=24)
        self.assertEqual(heatmap["status"], "success")
        self.assertGreaterEqual(heatmap["total_raw_clicks"], 5)
        self.assertGreaterEqual(heatmap["total_qualified_clicks"], 3)
        self.assertGreaterEqual(heatmap["bot_clicks_filtered"], 1)

        # Check top deals heatmap
        top_deals = heatmap["top_deals_heatmap"]
        self.assertTrue(len(top_deals) > 0)
        top_amz = next((d for d in top_deals if d["product_id"] == "test_p6c_amz_deal"), None)
        self.assertIsNotNone(top_amz)
        self.assertGreaterEqual(top_amz["heat_score"], 5.0)

    def test_06_http_api_analytics_heatmap_endpoint(self):
        """Test HTTP GET /api/v1/analytics/heatmap endpoint returns valid JSON."""
        req = MockServerRequest("/api/v1/analytics/heatmap?hours=12")
        ScraperAPIHandler.do_GET(req)

        self.assertEqual(req.response_code, 200)
        data = json.loads(req.wfile.getvalue().decode("utf-8"))
        self.assertEqual(data["status"], "success")
        self.assertIn("total_qualified_clicks", data)
        self.assertIn("top_deals_heatmap", data)
        self.assertIn("amazon_vs_flipkart_distribution", data)

    def test_07_go_route_with_analytics_and_bot_filtering(self):
        """Test /go/ route handles bot vs human clicks seamlessly."""
        # Bot request to Buy CTA
        bot_req = MockServerRequest(
            "/go/test_p6c_amz_deal?cta=buy&src=telegram",
            client_ip="185.220.101.5",
            user_agent="TelegramBot (like TwitterBot)"
        )
        ScraperAPIHandler.do_GET(bot_req)
        self.assertEqual(bot_req.response_code, 302)
        self.assertIn("amazon.in", bot_req.response_headers.get("Location"))

        # Verify ClickLog tagged with :bot
        click = self.db.query(ClickLog).filter_by(product_id="test_p6c_amz_deal", ip="185.220.101.5").first()
        self.assertIsNotNone(click)
        self.assertIn(":bot", click.user)

    def test_08_scorer_feedback_excludes_bot_and_duplicate_clicks(self):
        """Test calculate_deal_score feedback bonus only counts qualified clicks."""
        prod_id = "test_p6c_amz_deal"
        now = time.time()

        # Add 20 bot clicks
        for i in range(20):
            c = ClickLog(product_id=prod_id, title="Sony", ip=f"10.0.0.{i}", user="telegram:buy:bot", timestamp=now)
            self.db.add(c)
        self.db.commit()

        # Score should NOT get feedback bonus for bot clicks
        score_bot_only = calculate_deal_score(
            platform="amazon", price=19990, mrp=29990, discount=33.3,
            is_verified_low=True, is_lightning=False, product_id=prod_id, title="Sony WH-1000XM5"
        )

        # Add 15 qualified clicks
        for i in range(15):
            c = ClickLog(product_id=prod_id, title="Sony", ip=f"10.1.0.{i}", user="telegram:buy", timestamp=now)
            self.db.add(c)
        self.db.commit()

        score_with_qual = calculate_deal_score(
            platform="amazon", price=19990, mrp=29990, discount=33.3,
            is_verified_low=True, is_lightning=False, product_id=prod_id, title="Sony WH-1000XM5"
        )

        # 15 qualified clicks = (15 // 10) * 2 = +2 points
        self.assertGreater(score_with_qual, score_bot_only)


if __name__ == "__main__":
    unittest.main()
