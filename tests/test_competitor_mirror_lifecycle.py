"""
tests/test_competitor_mirror_lifecycle.py
Targeted test suite for Competitor Channel Mirroring:
- Daemon lifecycle and graceful shutdown
- In-memory queue fallback and RPOPLPUSH pattern
- Synthetic message normalization, deduplication, and pipeline execution without public spam
"""

import unittest
from unittest.mock import MagicMock, patch
import time
import threading
from deal_engine.mirroring.schemas import NormalizedMessage, ButtonSchema
from deal_engine.mirroring.redis_queue import RedisMessageQueue
from deal_engine.mirroring.processor import DealMirrorProcessor
from deal_engine.channel_mirror import _should_skip_url, start_channel_mirror, stop_channel_mirror, run_channel_mirror_daemon
import deal_engine.mirroring as mirroring_pkg

class TestCompetitorMirrorLifecycle(unittest.TestCase):

    def test_should_skip_url(self):
        """Verify non-product and aggregator URLs are filtered out."""
        self.assertTrue(_should_skip_url("https://www.amazon.in/s?k=deals+of+the+day"))
        self.assertTrue(_should_skip_url("https://www.amazon.in/gp/goldbox?pct-off=50-"))
        self.assertTrue(_should_skip_url("https://www.amazon.in/gp/bestsellers/electronics"))
        self.assertTrue(_should_skip_url("https://www.amazon.in/gp/new-releases/books"))
        self.assertTrue(_should_skip_url("https://www.flipkart.com/all/pr?sid=tyy,4io"))
        
        # Valid product URLs must not be skipped
        self.assertFalse(_should_skip_url("https://www.amazon.in/dp/B0D1234567"))
        self.assertFalse(_should_skip_url("https://www.flipkart.com/product/p/itm123456789"))

    def test_in_memory_queue_operations(self):
        """Verify thread-safe in-memory queue fallback behaves identically to Redis."""
        queue = RedisMessageQueue()
        # Force fallback mode to verify in-memory resilience
        queue.use_fallback = True
        
        msg = NormalizedMessage(
            channel_id="c_123",
            message_id=1001,
            channel_name="test_competitor_channel",
            raw_text="🔥 Super Deal! Apple iPhone 15 at Rs.59,999 https://www.amazon.in/dp/B0CHX1W1XY",
            extracted_urls=["https://www.amazon.in/dp/B0CHX1W1XY"],
            correlation_id="corr-test-1001"
        )
        
        # 1. Enqueue
        enqueued = queue.enqueue(msg)
        self.assertTrue(enqueued)
        
        # 2. Dequeue
        worker_id = "test-worker-1"
        popped_msg = queue.dequeue(worker_id=worker_id, timeout=1)
        self.assertIsNotNone(popped_msg)
        self.assertEqual(popped_msg.message_id, 1001)
        self.assertEqual(popped_msg.correlation_id, "corr-test-1001")
        self.assertEqual(len(queue.fallback_processing.get(worker_id, [])), 1)
        
        # 3. Commit / Ack
        queue.commit(worker_id=worker_id, message=popped_msg)
        self.assertEqual(len(queue.fallback_processing.get(worker_id, [])), 0)

    @patch("deal_engine.mirroring.processor.DealMirrorProcessor._expand_url_with_retry")
    @patch("deal_engine.notifier.enqueue_alert")
    @patch("deal_engine.mirroring.processor.scrape_product_details")
    def test_synthetic_competitor_message_pipeline(self, mock_scrape, mock_enqueue, mock_expand):
        """Verify end-to-end processing of a synthetic competitor message without live network calls or public posts."""
        import uuid
        unique_asin = f"B0TEST{uuid.uuid4().hex[:4].upper()}"
        target_url = f"https://www.amazon.in/dp/{unique_asin}"
        
        mock_expand.return_value = target_url
        mock_scrape.return_value = {
            "title": "Apple iPhone 15 (128 GB) - Black",
            "price": 59999,
            "mrp": 79900,
            "discount": 24.9,
            "image_url": "https://m.media-amazon.com/images/I/71657TiFeHL._AC_SL1500_.jpg",
            "rating": 4.6,
            "reviews": 1200,
            "has_bank_offer": True
        }
        
        queue = RedisMessageQueue()
        queue.use_fallback = True
        processor = DealMirrorProcessor(queue)
        
        msg = NormalizedMessage(
            channel_id="c_456",
            message_id=2002,
            channel_name="top_deals_india",
            raw_text=f"Huge Price Drop! Apple iPhone 15 (128GB)\nMRP: 79900 Deal: 59999\nBuy here: {target_url}",
            extracted_urls=[target_url],
            correlation_id="corr-synth-2002"
        )
        
        # 1. Fresh Message Processing
        processor._execute_pipeline(msg)
        
        # Verify scrape was invoked with canonical URL
        mock_scrape.assert_called()
        # Verify alert was enqueued with proper affiliate and discount metadata
        mock_enqueue.assert_called()
        call_args = mock_enqueue.call_args[1] if mock_enqueue.call_args[1] else mock_enqueue.call_args[0][0]
        self.assertEqual(call_args.get("platform"), "amazon")
        self.assertEqual(call_args.get("price"), 59999)
        self.assertTrue(call_args.get("is_mirror"))
        self.assertIn("lootraiders", call_args.get("final_url", ""))
        
        # 2. Duplicate Message Processing (must be suppressed by deduplicator)
        mock_enqueue.reset_mock()
        processor._execute_pipeline(msg)
        mock_enqueue.assert_not_called()

    def test_mirror_engine_lifecycle(self):
        """Verify mirror engine starts workers and event loop cleanly, and cleanly shuts down."""
        # Ensure clean initial state
        stop_channel_mirror()
        
        # Start mirror engine
        start_channel_mirror()
        time.sleep(0.3)
        
        # Verify processor workers were spawned
        processor = mirroring_pkg.get_processor()
        self.assertGreater(len(processor.workers), 0)
        self.assertFalse(processor.should_stop)
        
        # Verify event loop is active
        self.assertIsNotNone(mirroring_pkg._loop)
        self.assertTrue(mirroring_pkg._loop.is_running())
        
        # Cleanly stop engine
        stop_channel_mirror()
        time.sleep(0.3)
        
        # Verify processor signaled stop
        self.assertTrue(processor.should_stop)
        self.assertIsNone(mirroring_pkg._loop)

if __name__ == "__main__":
    unittest.main()
