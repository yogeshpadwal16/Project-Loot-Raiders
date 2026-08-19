"""
P0-3 Regression Tests — Silent Deal Loss on Image Failure
=========================================================

These tests verify the text-only sendMessage fallback when
photo-based delivery fails for any image-related reason.
"""

import unittest
import time
import json
import os
import sys
import logging
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db_session import Base
from knowledge_base.models import Product, PriceHistory, PendingNotification
from deal_engine.notifier import send_telegram_alert


class MockResponse:
    def __init__(self, status_code, message_id=None):
        self.status_code = status_code
        self._data = {"ok": status_code == 200}
        if message_id is not None:
            self._data["result"] = {"message_id": message_id}
        elif status_code == 200:
            self._data["result"] = {}
        self.text = json.dumps(self._data)

    def json(self):
        return self._data


def _create_test_db():
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)
    return test_engine, TestSession


class TestImageFallback(unittest.TestCase):
    """
    Verify text-only fallback on image/photo-based Telegram failure.
    """

    def setUp(self):
        self.test_engine, self.TestSession = _create_test_db()
        self.db = self.TestSession()

        # Seed a test product
        self.test_product = Product(
            id="IMG_FAIL_001",
            platform="amazon",
            title="Image Failure Test Product",
            image_url="https://example.com/dead-image.jpg",
            url="https://www.amazon.in/dp/IMG_FAIL_001",
            last_published_at=0.0,
            last_published_price=0,
            daily_post_count=0,
            daily_post_date=""
        )
        self.db.add(self.test_product)
        
        ph = PriceHistory(
            product_id="IMG_FAIL_001",
            price=999,
            mrp=1999,
            discount=50.0,
            is_verified_low=True,
            deal_score=80.0,
            timestamp=time.time()
        )
        self.db.add(ph)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _read_product(self):
        return self.db.query(Product).filter_by(id="IMG_FAIL_001").first()

    def test_01_photo_success_does_not_send_text_fallback(self):
        """
        TEST 1: Photo delivery succeeds -> text fallback is NOT called.
        """
        # Mock: requests.get succeeds to download image, requests.post succeeds for sendPhoto
        mock_get_res = MagicMock()
        mock_get_res.status_code = 200
        mock_get_res.content = b"fake-raw-image-bytes"

        mock_post_res = MockResponse(200, message_id=55555)

        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', return_value=mock_post_res) as mock_post, \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/sample.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertTrue(result, "Should return True on successful photo send")
        
        # Verify database state
        prod = self._read_product()
        self.assertEqual(prod.telegram_message_id, 55555)
        self.assertGreater(prod.last_published_at, 0.0)

        # Check mock calls: requests.post should have been called only once (for sendPhoto)
        # and NOT for sendMessage (text fallback)
        endpoints = [args[0] for args, kwargs in mock_post.call_args_list]
        self.assertEqual(len(endpoints), 1)
        self.assertTrue(endpoints[0].endswith("sendPhoto"))
        self.assertFalse(any("sendMessage" in ep for ep in endpoints))

    def test_02_image_download_timeout_triggers_text_fallback(self):
        """
        TEST 2: Image download throws timeout -> text fallback succeeds.
        """
        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)  # Remote URL photo dispatch fails
            elif "sendMessage" in url:
                return MockResponse(200, message_id=66666)
            return MockResponse(500)

        # Mock: requests.get throws Exception (timeout), requests.post for sendMessage succeeds
        with patch('requests.get', side_effect=Exception("Timeout")), \
             patch('requests.post', side_effect=mock_post_side_effect) as mock_post, \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/sample.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertTrue(result, "Should return True on text fallback success")
        
        prod = self._read_product()
        self.assertEqual(prod.telegram_message_id, 66666)
        self.assertGreater(prod.last_published_at, 0.0)

        # Verify that requests.post was called for sendMessage
        endpoints = [args[0] for args, kwargs in mock_post.call_args_list]
        self.assertTrue(any("sendMessage" in ep for ep in endpoints))

    def test_03_image_404_triggers_text_fallback(self):
        """
        TEST 3: Image download returns 404 -> text fallback succeeds.
        """
        mock_get_res = MagicMock()
        mock_get_res.status_code = 404

        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)
            elif "sendMessage" in url:
                return MockResponse(200, message_id=77777)
            return MockResponse(500)

        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', side_effect=mock_post_side_effect) as mock_post, \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/sample.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertTrue(result)
        prod = self._read_product()
        self.assertEqual(prod.telegram_message_id, 77777)

    def test_04_image_403_triggers_text_fallback(self):
        """
        TEST 4: Image download returns 403 -> text fallback succeeds.
        """
        mock_get_res = MagicMock()
        mock_get_res.status_code = 403

        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)
            elif "sendMessage" in url:
                return MockResponse(200, message_id=88888)
            return MockResponse(500)

        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', side_effect=mock_post_side_effect) as mock_post, \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/sample.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertTrue(result)
        prod = self._read_product()
        self.assertEqual(prod.telegram_message_id, 88888)

    def test_05_invalid_image_triggers_text_fallback(self):
        """
        TEST 5: Image URL format is invalid -> text fallback succeeds.
        """
        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)
            elif "sendMessage" in url:
                return MockResponse(200, message_id=99999)
            return MockResponse(500)

        with patch('requests.post', side_effect=mock_post_side_effect) as mock_post, \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="invalid-image-url",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertTrue(result)
        prod = self._read_product()
        self.assertEqual(prod.telegram_message_id, 99999)

    def test_06_sendphoto_failure_triggers_text_fallback(self):
        """
        TEST 6: Telegram sendPhoto returns HTTP 400 -> text fallback succeeds.
        """
        # Mock requests.get to succeed (local download ok)
        mock_get_res = MagicMock()
        mock_get_res.status_code = 200
        mock_get_res.content = b"fake-image-bytes"

        # Mock requests.post to return 400 for sendPhoto, and 200 for sendMessage fallback
        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)
            elif "sendMessage" in url:
                return MockResponse(200, message_id=11223)
            return MockResponse(500)

        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', side_effect=mock_post_side_effect), \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/image.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertTrue(result)
        prod = self._read_product()
        self.assertEqual(prod.telegram_message_id, 11223)
        self.assertGreater(prod.last_published_at, 0.0)

    def test_07_text_fallback_failure_does_not_mark_published(self):
        """
        TEST 7: Both photo and text fallback fail -> returns False, state remains unchanged.
        """
        mock_get_res = MagicMock()
        mock_get_res.status_code = 404

        # Mock: requests.post returns 400 for everything
        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', return_value=MockResponse(400)), \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/image.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertFalse(result, "Should return False when all delivery methods fail")
        
        prod = self._read_product()
        self.assertEqual(prod.last_published_at, 0.0)
        self.assertEqual(prod.last_published_price, 0)
        self.assertEqual(prod.daily_post_count, 0)
        self.assertIsNone(prod.telegram_message_id)

    def test_08_text_fallback_requires_valid_message_id(self):
        """
        TEST 8: text fallback returns 200 but NO valid message_id -> failure, state unchanged.
        """
        mock_get_res = MagicMock()
        mock_get_res.status_code = 404

        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)
            elif "sendMessage" in url:
                return MockResponse(200, message_id=None)
            return MockResponse(500)

        # Mock: post returns 200 with NO message_id for sendMessage
        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', side_effect=mock_post_side_effect), \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/image.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertFalse(result)
        prod = self._read_product()
        self.assertEqual(prod.last_published_at, 0.0)

    def test_09_text_fallback_http_400_is_failure(self):
        """
        TEST 9: text fallback returns 400 -> failure.
        """
        mock_get_res = MagicMock()
        mock_get_res.status_code = 404

        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)
            elif "sendMessage" in url:
                return MockResponse(400)
            return MockResponse(500)

        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', side_effect=mock_post_side_effect), \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/image.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertFalse(result)

    def test_10_text_fallback_http_429_is_failure(self):
        """
        TEST 10: text fallback returns 429 -> failure.
        """
        mock_get_res = MagicMock()
        mock_get_res.status_code = 404

        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)
            elif "sendMessage" in url:
                return MockResponse(429)
            return MockResponse(500)

        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', side_effect=mock_post_side_effect), \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/image.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertFalse(result)

    def test_11_p02_success_state_preserved_for_text_fallback(self):
        """
        TEST 11: Successful text-only publication commits all P0-2 details:
        telegram_message_id, last_published_at, last_published_price, daily_post_count.
        """
        mock_get_res = MagicMock()
        mock_get_res.status_code = 404

        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)
            elif "sendMessage" in url:
                return MockResponse(200, message_id=98765)
            return MockResponse(500)

        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', side_effect=mock_post_side_effect), \
             patch('database.db_session.SessionLocal', self.TestSession), \
             patch('deal_engine.notifier.SessionLocal', self.TestSession):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/image.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertTrue(result)
        
        prod = self._read_product()
        self.assertEqual(prod.telegram_message_id, 98765)
        self.assertGreater(prod.last_published_at, 0.0)
        self.assertEqual(prod.last_published_price, 999)
        self.assertEqual(prod.daily_post_count, 1)

    def test_12_db_commit_failure_after_telegram_success(self):
        """
        TEST 12: DB persistence/commit fails after successful Telegram delivery.
        - NEVER pretend the DB state was successfully persisted.
        - Return 'db_fail'.
        - DB publication-state remains unchanged.
        """
        mock_get_res = MagicMock()
        mock_get_res.status_code = 404

        def mock_post_side_effect(url, *args, **kwargs):
            if "sendPhoto" in url:
                return MockResponse(400)
            elif "sendMessage" in url:
                return MockResponse(200, message_id=87654)
            return MockResponse(500)

        # Mock db.commit to raise an exception
        original_session = self.TestSession
        def bad_session(*args, **kwargs):
            session = original_session(*args, **kwargs)
            session.commit = MagicMock(side_effect=Exception("DB locked error"))
            return session

        with patch('requests.get', return_value=mock_get_res), \
             patch('requests.post', side_effect=mock_post_side_effect), \
             patch('database.db_session.SessionLocal', bad_session), \
             patch('deal_engine.notifier.SessionLocal', bad_session):

            result = send_telegram_alert(
                bot_token="FAKE_BOT_TOKEN",
                chat_id="@test_channel",
                platform="amazon",
                title="Test Title",
                price=999,
                mrp=1999,
                discount=50.0,
                img_url="https://example.com/image.jpg",
                final_url="https://www.amazon.in/dp/IMG_FAIL_001",
                is_verified_low=True,
                deal_score=80.0,
                unique_id="IMG_FAIL_001"
            )

        self.assertEqual(result, 'db_fail')
        
        # Verify database state remained unchanged
        prod = self._read_product()
        self.assertEqual(prod.telegram_message_id, None)
        self.assertEqual(prod.last_published_at, 0.0)

    def test_13_db_commit_failure_does_not_retry(self):
        """
        TEST 13: Ensure that when an alert job returns 'db_fail',
        the worker marks the notification as 'failed' in the database
        and does NOT re-enqueue it for retry.
        """
        import threading
        from deal_engine.notifier import _process_and_broadcast_alert_job
        
        job = {
            "db_id": 999,
            "platform": "amazon",
            "title": "Test Title",
            "price": 999,
            "mrp": 1999,
            "discount": 50.0,
            "img_url": "https://example.com/image.jpg",
            "final_url": "https://www.amazon.in/dp/IMG_FAIL_001",
            "is_verified_low": True,
            "deal_score": 80.0,
            "unique_id": "IMG_FAIL_001",
            "retries": 0
        }
        
        status_updates = []
        def mock_update_status(db_id, status, retries=0):
            status_updates.append((db_id, status, retries))
            
        with patch('deal_engine.notifier.send_telegram_alert', return_value='db_fail'), \
             patch('deal_engine.notifier.db_update_notification_status', side_effect=mock_update_status), \
             patch('threading.Timer') as mock_timer:
             
             # Put job in queue
             from deal_engine.notifier import notification_queue
             while not notification_queue.empty():
                 try: notification_queue.get_nowait()
                 except Exception: pass
                 
             # Put job and sentinel to break the loop as PriorityQueue tuples
             notification_queue.put((1, time.time(), 1, job))
             notification_queue.put((1, time.time(), 2, None))
             
             from deal_engine.notifier import notifier_worker
             notifier_worker()
             
             # Verify status was updated to 'failed'
             self.assertEqual(status_updates, [(999, 'failed', 0)])
             
             # Verify Timer was NOT called (no retry scheduled)
             mock_timer.assert_not_called()


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    unittest.main()
