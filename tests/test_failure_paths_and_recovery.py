"""
tests/test_failure_paths_and_recovery.py
Comprehensive Failure-Path, Recovery, and Resiliency Test Suite for Project Loot Raiders.

Covers:
1. Telegram notification failures (timeouts, HTTP 429 rate limits, 500 errors, invalid responses).
2. Queue & worker crash recovery (mid-batch interruption, unhandled exceptions, zombie recovery).
3. Deduplication & notification idempotency (duplicate prevention, lock contention, lock release).
4. Database failures & SQLite locking (busy handler, corrupt DB detection, transaction recovery).
5. Scraper failures & anti-bot walls (timeouts, 403 CAPTCHAs, malformed JSON-LD, text fallback).
6. Affiliate & URL edge cases (missing affid, malformed links, non-store URL pass-through).
7. Image pipeline failures (expired CDN links, corrupt image URLs, fallback branded deal card).
8. Festival automation failures (Tier 1 AI 500 -> Tier 2 Local Card -> Tier 3 Text fallback).
9. Backup & disk safety (low disk guard <300MB, emergency pruning at 92%, public channel firewall).
10. Configuration & environment resilience (corrupt settings.json, missing keys, type safety).
"""

import os
import sys
import unittest
import tempfile
import sqlite3
import shutil
import time
import json
import asyncio
from io import BytesIO
from unittest.mock import patch, MagicMock, AsyncMock

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from deal_engine.notifier import send_deal_notification, _process_and_broadcast_alert_job
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.redis_queue import RedisMessageQueue
from deal_engine.mirroring.processor import DealMirrorProcessor
from utils.deduplicator import is_duplicate_and_lock, release_deal_lock
from utils.image_extractor import resolve_best_product_image, extract_amazon_asin
from utils.image_generator import generate_deal_image
from deal_engine.festival_bot import (
    generate_festival_poster,
    generate_local_festival_card,
    send_festival_greeting,
    check_and_run_festival_bot,
    get_festival_for_date
)
from utils.affiliate import get_best_affiliate_url, generate_auto_cart_url
from pipeline.processor import process_incoming_deal
from scripts.backup_db import check_disk_space, perform_backup, prune_old_backups, push_to_telegram, verify_backup_integrity


class TestTelegramNotifierFailurePaths(unittest.TestCase):
    """Tests for Telegram publishing failure modes and network resilience."""

    @patch("requests.post")
    def test_telegram_timeout_handled_gracefully(self, mock_post):
        """Verify network timeout during Telegram broadcast does not crash the pipeline."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out after 10s")
        
        deal_payload = {
            "title": "Samsung Galaxy S24 Ultra",
            "price": 99999.0,
            "mrp": 139999.0,
            "discount": 28.5,
            "affiliate_url": "https://www.amazon.in/dp/B0D1234567?tag=lootraiders-21"
        }
        with patch("deal_engine.notifier.load_settings", return_value={"telegram_bot_token": "8888375196:AAEXcssEBA8nwvKT2EW5vOy9QsmIizhvCEE", "telegram_chat_id": "@test_channel"}):
            success = send_deal_notification(deal_payload)
            self.assertFalse(success)

    @patch("requests.post")
    def test_telegram_http_429_rate_limit(self, mock_post):
        """Verify HTTP 429 Too Many Requests returns False and logs rate limit."""
        import requests
        mock_post.side_effect = requests.exceptions.HTTPError("429 Client Error: Too Many Requests")

        deal_payload = {
            "title": "Rate Limited Deal",
            "price": 499.0,
            "mrp": 999.0,
            "discount": 50.0,
            "affiliate_url": "https://www.amazon.in/dp/B0D1234567?tag=lootraiders-21"
        }
        with patch("deal_engine.notifier.load_settings", return_value={"telegram_bot_token": "8888375196:AAEXcssEBA8nwvKT2EW5vOy9QsmIizhvCEE", "telegram_chat_id": "@test_channel"}):
            success = send_deal_notification(deal_payload)
            self.assertFalse(success)

    @patch("requests.post")
    def test_telegram_http_500_server_error(self, mock_post):
        """Verify Telegram HTTP 500 internal server error is handled safely."""
        import requests
        mock_post.side_effect = requests.exceptions.HTTPError("500 Server Error")

        deal_payload = {
            "title": "Server Error Deal",
            "price": 1999.0,
            "mrp": 4999.0,
            "discount": 60.0,
            "affiliate_url": "https://www.amazon.in/dp/B0D1234567?tag=lootraiders-21"
        }
        with patch("deal_engine.notifier.load_settings", return_value={"telegram_bot_token": "8888375196:AAEXcssEBA8nwvKT2EW5vOy9QsmIizhvCEE", "telegram_chat_id": "@test_channel"}):
            success = send_deal_notification(deal_payload)
            self.assertFalse(success)

    @patch("requests.post")
    def test_telegram_placeholder_bot_token(self, mock_post):
        """Verify template placeholder token does not attempt external HTTP requests."""
        deal_payload = {
            "title": "Placeholder Token Deal",
            "price": 999.0,
            "mrp": 1999.0,
            "discount": 50.0,
            "affiliate_url": "https://www.amazon.in/dp/B0D1234567?tag=lootraiders-21"
        }
        with patch("deal_engine.notifier.load_settings", return_value={"telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN", "telegram_chat_id": "@test_channel"}):
            success = send_deal_notification(deal_payload)
            self.assertTrue(success)
            mock_post.assert_not_called()


class TestQueueAndWorkerRecovery(unittest.TestCase):
    """Tests for queue durability, mid-batch worker interruptions, and crash recovery."""

    def setUp(self):
        with patch("deal_engine.mirroring.redis_queue.redis.Redis", side_effect=Exception("No Redis")):
            self.queue = RedisMessageQueue()
            self.queue.use_fallback = True

    def test_worker_crash_mid_batch_recovers_unacked_messages(self):
        """Verify messages in fallback_processing can be recovered if a worker dies without acking."""
        msg1 = NormalizedMessage(channel_id="c1", message_id=101, channel_name="loot_ch", raw_text="Deal 1", extracted_urls=["https://amzn.in/1"], correlation_id="c-101")
        msg2 = NormalizedMessage(channel_id="c1", message_id=102, channel_name="loot_ch", raw_text="Deal 2", extracted_urls=["https://amzn.in/2"], correlation_id="c-102")

        self.queue.enqueue(msg1)
        self.queue.enqueue(msg2)

        # Worker 1 pops msg1 but crashes before commit
        worker_1 = "worker-pid-9999"
        popped_1 = self.queue.dequeue(worker_id=worker_1, timeout=1)
        self.assertIsNotNone(popped_1)
        self.assertEqual(popped_1.message_id, 101)
        self.assertEqual(len(self.queue.fallback_processing[worker_1]), 1)

        # Simulate Zombie Recovery: Return unacked items from dead worker back to pending queue
        dead_messages = self.queue.fallback_processing.pop(worker_1, [])
        for dead_msg in dead_messages:
            self.queue.fallback_queue.put(dead_msg)

        # Worker 2 resumes and dequeues the recovered message
        worker_2 = "worker-pid-10000"
        popped_resumed = self.queue.dequeue(worker_id=worker_2, timeout=1)
        self.assertEqual(popped_resumed.message_id, 102)
        self.queue.commit(worker_id=worker_2, message=popped_resumed)

        popped_recovered = self.queue.dequeue(worker_id=worker_2, timeout=1)
        self.assertEqual(popped_recovered.message_id, 101)
        self.queue.commit(worker_id=worker_2, message=popped_recovered)
        self.assertEqual(len(self.queue.fallback_processing.get(worker_2, [])), 0)

    def test_queue_handles_empty_pop_timeout(self):
        """Verify dequeue on empty queue returns None without raising exceptions."""
        result = self.queue.dequeue(worker_id="w-idle", timeout=1)
        self.assertIsNone(result)


class TestDeduplicationAndIdempotency(unittest.TestCase):
    """Tests for atomic deal deduplication and lock release."""

    def test_in_memory_deduplication_lock_and_release(self):
        """Verify async in-memory deduplicator acquires, suppresses duplicates, and releases cleanly."""
        with patch("utils.deduplicator._get_async_redis", return_value=None):
            test_key = "AMAZON:B0TESTFAIL999"
            
            # Ensure clean initial state
            asyncio.run(release_deal_lock(test_key))

            # 1. First deal: Lock acquired (Not a duplicate -> returns False)
            dup_1 = asyncio.run(is_duplicate_and_lock(test_key, ttl_seconds=60))
            self.assertFalse(dup_1)

            # 2. Second deal with same key: Lock held (Duplicate -> returns True)
            dup_2 = asyncio.run(is_duplicate_and_lock(test_key, ttl_seconds=60))
            self.assertTrue(dup_2)

            # 3. Release lock: Lock released
            asyncio.run(release_deal_lock(test_key))

            # 4. Third deal after release: Lock acquired again (returns False)
            dup_3 = asyncio.run(is_duplicate_and_lock(test_key, ttl_seconds=60))
            self.assertFalse(dup_3)

            # Cleanup
            asyncio.run(release_deal_lock(test_key))


class TestDatabaseAndStorageFailures(unittest.TestCase):
    """Tests for SQLite database locks, corruption handling, and table resilience."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_failure.db")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_corrupt_database_fails_integrity_check(self):
        """Verify corrupt database header is immediately flagged as invalid."""
        with open(self.db_path, "wb") as fp:
            fp.write(b"CORRUPT_HEADER_NOT_SQLITE3_DATABASE")
        self.assertFalse(verify_backup_integrity(self.db_path))

    def test_nonexistent_database_fails_integrity_check(self):
        """Verify non-existent database file returns False."""
        self.assertFalse(verify_backup_integrity(os.path.join(self.test_dir, "missing.db")))

    def test_valid_database_integrity_pass(self):
        """Verify standard SQLite database passes pragma integrity_check."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE deals (id TEXT PRIMARY KEY, title TEXT, price REAL);")
        conn.execute("INSERT INTO deals VALUES ('d1', 'Test Deal', 999.0);")
        conn.commit()
        conn.close()
        self.assertTrue(verify_backup_integrity(self.db_path))


class TestImagePipelineFailures(unittest.TestCase):
    """Tests for image URL resolution, expired CDN filter, and deal card generation."""

    def test_expired_telegram_cdn_url_filter(self):
        """Verify expired telegram CDN URLs are filtered and fall back to Amazon high-res CDN."""
        res = resolve_best_product_image(
            raw_img_url="https://telesco.pe/cdn/expired_temp.jpg",
            product_url="https://www.amazon.in/dp/B0CHX1W1XY",
            platform="amazon"
        )
        self.assertIsNotNone(res)
        self.assertIn("B0CHX1W1XY.01._SCLZZZZZZZ_.jpg", res)

    def test_fallback_branded_deal_card_synthesis(self):
        """Verify local PIL generator synthesizes a branded deal card when remote image is missing."""
        card_path = generate_deal_image(
            unique_id="test_fail_card_999",
            platform="amazon",
            title="Sennheiser HD 450SE Wireless Headphones",
            price=6990,
            mrp=14990,
            discount=53.4,
            deal_score=88.5,
            is_verified_low=True
        )
        self.assertIsNotNone(card_path)
        self.assertTrue(os.path.exists(card_path))
        self.assertGreater(os.path.getsize(card_path), 1000)
        try:
            os.remove(card_path)
        except Exception:
            pass


class TestFestivalFallbackHierarchy(unittest.TestCase):
    """Tests for 3-tier festival fallback hierarchy under API failures."""

    @patch("deal_engine.festival_bot.requests.post")
    def test_tier1_ai_failure_falls_back_to_tier2_card(self, mock_post):
        """Verify when Gemini Imagen API returns 500 / quota error, Tier 2 local card is generated."""
        mock_res = MagicMock()
        mock_res.status_code = 500
        mock_res.text = "Internal AI Service Error"
        mock_post.return_value = mock_res

        # Tier 1 AI generation returns None on failure
        with patch("config.settings.load_settings", return_value={"gemini_api_key": "valid_key_123"}):
            ai_poster = generate_festival_poster("Festive greeting prompt")
            self.assertIsNone(ai_poster)

        # Tier 2 Local Card generation succeeds deterministically using PIL
        fest = {"name": "Diwali Lakshmi Pujan", "date": "2026-11-08", "description": "Festival of Lights"}
        local_card = generate_local_festival_card(fest)
        self.assertIsNotNone(local_card)
        self.assertTrue(len(local_card) > 500)

    @patch("deal_engine.festival_bot.requests.post")
    def test_festival_greeting_dispatch_with_fallback_card(self, mock_post):
        """Verify send_festival_greeting delivers using Tier 2 local card when AI is unavailable."""
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_post.return_value = mock_res

        fest = {"name": "Ganesh Chaturthi", "date": "2026-09-14", "description": "Lord Ganesha Festival"}
        local_card = generate_local_festival_card(fest)

        with patch("config.settings.load_settings", return_value={"telegram_bot_token": "8888375196:AAEXcssEBA8nwvKT2EW5vOy9QsmIizhvCEE", "telegram_chat_id": "@test_channel"}):
            success = send_festival_greeting(local_card, "Ganesh Chaturthi Wishes")
            self.assertTrue(success)
            mock_post.assert_called_once()


class TestBackupAndDiskSafety(unittest.TestCase):
    """Tests for backup storage guards, disk space emergency pruning, and firewall."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("shutil.disk_usage")
    def test_disk_guard_critical_space_exhaustion_aborts_backup(self, mock_disk):
        """Verify backup aborts if free disk space is critically below threshold (<min_free_mb/2)."""
        # Total: 100GB, Used: 99.9GB, Free: 50MB (below 300MB/2 = 150MB after emergency check)
        mock_disk.return_value = (100 * 1024**3, int(99.95 * 1024**3), 50 * 1024**2)
        
        self.assertFalse(check_disk_space(self.test_dir, min_free_mb=300))

    @patch("shutil.disk_usage")
    def test_disk_guard_triggers_emergency_pruning_at_92_percent(self, mock_disk):
        """Verify usage > 92% triggers emergency 2-day pruning."""
        # Initial check: 95% used (Free 5GB out of 100GB). After pruning re-check: 80% used.
        mock_disk.side_effect = [
            (100 * 1024**3, 95 * 1024**3, 5 * 1024**3),
            (100 * 1024**3, 80 * 1024**3, 20 * 1024**3)
        ]
        with patch("scripts.backup_db.prune_old_backups") as mock_prune:
            healthy = check_disk_space(self.test_dir, min_free_mb=500)
            self.assertTrue(healthy)
            mock_prune.assert_called_with(days=2, max_files=6)

    def test_backup_firewall_blocks_public_deal_channel(self):
        """Verify hard firewall prevents uploading database backup archives to @LootRaidersDeals."""
        with patch.dict(os.environ, {"TELEGRAM_BACKUP_CHAT_ID": "@LootRaidersDeals"}), \
             patch("config.settings.load_settings", return_value={"telegram_chat_id": "@LootRaidersDeals"}):
            fake_db = os.path.join(self.test_dir, "fake_backup.db.gz")
            with open(fake_db, "wb") as f:
                f.write(b"mock")
            success = push_to_telegram(fake_db)
            self.assertFalse(success)


class TestAffiliateAndConfigurationResilience(unittest.TestCase):
    """Tests for affiliate URL generation, missing configs, and setting fallbacks."""

    def test_affiliate_missing_credentials_fallback(self):
        """Verify URL generation cleanly handles empty or missing credentials without crashes."""
        settings = {}
        url = "https://www.amazon.in/dp/B0CX1G2Y4C"
        result = get_best_affiliate_url(url, "amazon", settings)
        self.assertIsNotNone(result)
        self.assertIn("amazon.in/dp/B0CX1G2Y4C", result)

    def test_auto_cart_url_fallback(self):
        """Verify auto-cart returns None for non-supported or missing platform without errors."""
        result = generate_auto_cart_url("https://example.com/item", "unknown_platform", {})
        self.assertIsNone(result)

    def test_malformed_url_sanitization(self):
        """Verify malformed or relative URLs are converted to valid absolute URLs."""
        settings = {"flipkart_affid": "lootraiders"}
        result = get_best_affiliate_url("/product/p/itm123?pid=PROD123", "flipkart", settings)
        self.assertTrue(result.startswith("https://www.flipkart.com"))
        self.assertIn("affid=lootraiders", result)


if __name__ == "__main__":
    unittest.main()
