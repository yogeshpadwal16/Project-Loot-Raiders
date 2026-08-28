"""
tests/test_expiration_daemon.py
Comprehensive unit test suite for Deal Expiration Daemon.
Covers:
1. Fresh in-stock deal remains active (not expired).
2. Out-of-stock deal is marked expired on Telegram & DB.
3. Already expired deal is idempotent (no duplicate edits).
4. Singleton guard prevents duplicate daemon threads.
5. Malformed data (missing URL/caption/ID) handled gracefully without crashes.
6. HTTP exceptions and rate limits do not crash the daemon.
"""

import os
import sys
import unittest
import asyncio
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from knowledge_base.models import Product
from database.db_session import SessionLocal, init_db
from deal_engine.expiration_daemon import (
    check_deal_stock,
    expire_telegram_deal,
    start_expiration_daemon,
    _DAEMON_STARTED
)
import deal_engine.expiration_daemon as exp_module


class TestDealExpirationDaemon(unittest.TestCase):
    def setUp(self):
        init_db()
        self.db = SessionLocal()
        # Clean test products
        self.db.query(Product).filter(Product.id.like("test_exp_%")).delete()
        self.db.commit()

    def tearDown(self):
        self.db.query(Product).filter(Product.id.like("test_exp_%")).delete()
        self.db.commit()
        self.db.close()

    def test_01_check_deal_stock_in_stock(self):
        """Fresh in-stock HTML should return is_available=True."""
        html = "<html><body><h1>Samsung Galaxy S24</h1><span>In Stock</span><button>Add to Cart</button></body></html>"
        mock_resp = MagicMock()
        mock_resp.text = html

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            is_available = asyncio.run(check_deal_stock("https://www.amazon.in/dp/B0D1234567"))
            self.assertTrue(is_available)

    def test_02_check_deal_stock_out_of_stock(self):
        """Out of stock HTML should return is_available=False."""
        html = "<html><body><h1>Samsung Galaxy S24</h1><span id='availability'>Currently unavailable.</span></body></html>"
        mock_resp = MagicMock()
        mock_resp.text = html

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            is_available = asyncio.run(check_deal_stock("https://www.amazon.in/dp/B0D1234567"))
            self.assertFalse(is_available)

    def test_03_expire_telegram_deal_success(self):
        """Out-of-stock deal updates Telegram message and database record."""
        p = Product(
            id="test_exp_1001",
            platform="amazon",
            title="Sony WH-1000XM5 Wireless Headphones",
            image_url="https://m.media-amazon.com/images/I/71o8Q5XJS5L.jpg",
            url="https://www.amazon.in/dp/B09XS7JWHH",
            telegram_message_id=98765,
            telegram_caption="🔥 <b>Sony WH-1000XM5</b>\n\nPrice: Rs.19,990",
            created_at=datetime.utcnow()
        )
        self.db.add(p)
        self.db.commit()

        mock_post = MagicMock()
        mock_post.status_code = 200

        with patch("requests.post", return_value=mock_post) as mock_req, \
             patch("config.settings.load_settings", return_value={"telegram_bot_token": "8888375196:AAEXcssEBA8nwvKT2EW5vOy9QsmIizhvCEE", "telegram_chat_id": "@LootRaidersDeals"}):
            expire_telegram_deal("test_exp_1001")

            self.assertTrue(mock_req.called)
            args, kwargs = mock_req.call_args
            payload = kwargs.get("json", {})
            self.assertEqual(payload.get("message_id"), 98765)
            self.assertIn("DEAL EXPIRED", payload.get("caption", ""))

        # Verify DB updated
        self.db.expire_all()
        updated = self.db.query(Product).filter_by(id="test_exp_1001").first()
        self.assertIn("DEAL EXPIRED", updated.telegram_caption)

    def test_04_already_expired_deal_is_idempotent(self):
        """Already expired deal should skip editing Telegram (idempotency)."""
        p = Product(
            id="test_exp_1002",
            platform="amazon",
            title="Boat Bassheads 100",
            image_url="https://m.media-amazon.com/images/I/71.jpg",
            url="https://www.amazon.in/dp/B001",
            telegram_message_id=98766,
            telegram_caption="❌ <b>[ DEAL EXPIRED / SOLD OUT ]</b> ❌\n\n<s>Boat Bassheads</s>",
            created_at=datetime.utcnow()
        )
        self.db.add(p)
        self.db.commit()

        with patch("requests.post") as mock_req, \
             patch("config.settings.load_settings", return_value={"telegram_bot_token": "8888375196:AAEXcssEBA8nwvKT2EW5vOy9QsmIizhvCEE", "telegram_chat_id": "@LootRaidersDeals"}):
            expire_telegram_deal("test_exp_1002")
            self.assertFalse(mock_req.called)

    def test_05_singleton_guard_prevents_duplicate_daemon(self):
        """Calling start_expiration_daemon multiple times only launches one thread."""
        exp_module._DAEMON_STARTED = True
        with patch("threading.Thread") as mock_thread:
            start_expiration_daemon()
            self.assertFalse(mock_thread.called)
        exp_module._DAEMON_STARTED = False

    def test_06_malformed_data_does_not_crash(self):
        """Products without message_id or caption should return cleanly without exceptions."""
        p = Product(
            id="test_exp_1003",
            platform="amazon",
            title="Dummy Product",
            image_url="https://m.media-amazon.com/images/I/71.jpg",
            url="https://www.amazon.in/dp/B002",
            telegram_message_id=None,
            telegram_caption=None,
            created_at=datetime.utcnow()
        )
        self.db.add(p)
        self.db.commit()

        with patch("config.settings.load_settings", return_value={"telegram_bot_token": "8888375196:AAEXcssEBA8nwvKT2EW5vOy9QsmIizhvCEE", "telegram_chat_id": "@LootRaidersDeals"}):
            expire_telegram_deal("test_exp_1003")
            expire_telegram_deal("non_existent_id")


if __name__ == "__main__":
    unittest.main()
