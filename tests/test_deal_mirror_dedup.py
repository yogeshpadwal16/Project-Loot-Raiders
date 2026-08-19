"""
tests/test_deal_mirror_dedup.py
Targeted regression tests for Deal Mirror Deduplication (P0-1).
Verifies that:
1. New products are accepted.
2. Existing products with the same price are rejected as duplicates.
3. Existing products with price drops are accepted.
4. Existing products with multi-point history price drops are accepted.
5. Existing products with multi-point history same price are rejected.
6. Existing products with price increases are rejected.
7. Existing products without any PriceHistory records are accepted.
8. Canonical URL matching correctly evaluates PriceHistory rather than unconditionally dropping.
"""

import time
import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db_session import Base
from knowledge_base.models import Product, PriceHistory
from deal_engine.mirroring.processor import DealMirrorProcessor
from deal_engine.mirroring.schemas import NormalizedMessage


class TestDealMirrorDeduplication(unittest.TestCase):

    def setUp(self):
        # Create an in-memory SQLite database for isolated test execution
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.Session()

        # Instantiate DealMirrorProcessor with mock queue
        self.mock_queue = MagicMock()
        self.processor = DealMirrorProcessor(queue=self.mock_queue)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def _seed_product(self, product_id, title, url, platform="amazon", initial_price=1000, mrp=2000, timestamp=None, create_price_history=True):
        prod = Product(
            id=product_id,
            title=title,
            url=url,
            platform=platform,
            image_url="https://images.amazon.com/sample.jpg"
        )
        self.db.add(prod)
        self.db.commit()

        if create_price_history and initial_price is not None:
            ph = PriceHistory(
                product_id=product_id,
                price=initial_price,
                mrp=mrp,
                discount=50.0,
                is_verified_low=True,
                deal_score=85.0,
                timestamp=timestamp if timestamp is not None else time.time()
            )
            self.db.add(ph)
            self.db.commit()
        return prod

    @patch("deal_engine.notifier.enqueue_alert")
    @patch("deal_engine.mirroring.processor.save_deal_to_db")
    @patch("deal_engine.mirroring.processor.calculate_deal_score", return_value=90.0)
    @patch("deal_engine.mirroring.processor.scrape_product_details")
    @patch("deal_engine.mirroring.processor.DealMirrorProcessor._expand_url_with_retry")
    def test_01_new_product_accepted(self, mock_expand, mock_scrape, mock_score, mock_save, mock_enqueue):
        """Scenario 1: Brand new product must be accepted and enqueued for publication."""
        mock_expand.return_value = "https://www.amazon.in/dp/B0NEWPROD1"
        mock_scrape.return_value = {
            "title": "Brand New Noise Cancelling Headphones",
            "price": 1499,
            "mrp": 2999,
            "discount": 50.0,
            "img_url": "https://images.amazon.com/headphones.jpg"
        }
        mock_save.return_value = "B0NEWPROD1"

        msg = NormalizedMessage(
            channel_id="test_channel_123",
            channel_name="test_loot_channel",
            message_id=101,
            correlation_id="test-corr-01",
            extracted_urls=["https://amzn.to/newprod"],
            raw_text="Hot Deal on Headphones"
        )

        self.processor._process_single_raw_url(
            raw_url="https://amzn.to/newprod",
            correlation_id="test-corr-01",
            message=msg,
            extracted_data={},
            db=self.db
        )

        # Assert that the deal was enqueued
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args.kwargs
        self.assertEqual(call_kwargs["unique_id"], "B0NEWPROD1")
        self.assertEqual(call_kwargs["price"], 1499)

    @patch("deal_engine.notifier.enqueue_alert")
    @patch("deal_engine.mirroring.processor.scrape_product_details")
    @patch("deal_engine.mirroring.processor.DealMirrorProcessor._expand_url_with_retry")
    def test_02_existing_product_same_price_rejected(self, mock_expand, mock_scrape, mock_enqueue):
        """Scenario 2: Existing product at the exact same price (Rs. 1000 == Rs. 1000) must be rejected."""
        self._seed_product("B0SAMEPRIC", "Wireless Mouse", "https://www.amazon.in/dp/B0SAMEPRIC", initial_price=1000)

        mock_expand.return_value = "https://www.amazon.in/dp/B0SAMEPRIC"
        mock_scrape.return_value = {
            "title": "Wireless Mouse",
            "price": 1000, # Same price
            "mrp": 2000,
            "discount": 50.0,
            "img_url": "https://images.amazon.com/mouse.jpg"
        }

        msg = NormalizedMessage(
            channel_id="test_channel_123",
            channel_name="test_loot_channel",
            message_id=102,
            correlation_id="test-corr-02",
            extracted_urls=["https://amzn.to/sameprice"],
            raw_text="Mouse Deal"
        )

        self.processor._process_single_raw_url(
            raw_url="https://amzn.to/sameprice",
            correlation_id="test-corr-02",
            message=msg,
            extracted_data={},
            db=self.db
        )

        # Must NOT be enqueued because price has not dropped
        mock_enqueue.assert_not_called()

    @patch("deal_engine.notifier.enqueue_alert")
    @patch("deal_engine.mirroring.processor.save_deal_to_db")
    @patch("deal_engine.mirroring.processor.calculate_deal_score", return_value=95.0)
    @patch("deal_engine.mirroring.processor.scrape_product_details")
    @patch("deal_engine.mirroring.processor.DealMirrorProcessor._expand_url_with_retry")
    def test_03_existing_product_price_drop_accepted(self, mock_expand, mock_scrape, mock_score, mock_save, mock_enqueue):
        """Scenario 3: Existing product (Rs. 1000) with a lower price (Rs. 900) MUST be accepted."""
        self._seed_product("B0PRICEDRP", "Gaming Keyboard", "https://www.amazon.in/dp/B0PRICEDRP", initial_price=1000)

        mock_expand.return_value = "https://www.amazon.in/dp/B0PRICEDRP"
        mock_scrape.return_value = {
            "title": "Gaming Keyboard",
            "price": 900, # Price dropped from Rs. 1000 to Rs. 900
            "mrp": 2000,
            "discount": 55.0,
            "img_url": "https://images.amazon.com/kb.jpg"
        }
        mock_save.return_value = "B0PRICEDRP"

        msg = NormalizedMessage(
            channel_id="competitor_channel_456",
            channel_name="competitor_loot_box",
            message_id=103,
            correlation_id="test-corr-03",
            extracted_urls=["https://amzn.to/pricedrop"],
            raw_text="Huge Price Crash on Gaming Keyboard"
        )

        self.processor._process_single_raw_url(
            raw_url="https://amzn.to/pricedrop",
            correlation_id="test-corr-03",
            message=msg,
            extracted_data={},
            db=self.db
        )

        # Must be accepted and enqueued
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args.kwargs
        self.assertEqual(call_kwargs["unique_id"], "B0PRICEDRP")
        self.assertEqual(call_kwargs["price"], 900)

    @patch("deal_engine.notifier.enqueue_alert")
    @patch("deal_engine.mirroring.processor.save_deal_to_db")
    @patch("deal_engine.mirroring.processor.calculate_deal_score", return_value=90.0)
    @patch("deal_engine.mirroring.processor.scrape_product_details")
    @patch("deal_engine.mirroring.processor.DealMirrorProcessor._expand_url_with_retry")
    def test_04_multi_point_history_price_drop_accepted(self, mock_expand, mock_scrape, mock_score, mock_save, mock_enqueue):
        """Scenario 4: History Rs. 1200, Rs. 1000 -> Incoming Rs. 900 MUST be accepted."""
        now = time.time()
        # Seed older price Rs. 1200 (t = now - 100)
        self._seed_product("B0HISTMLT1", "USB Hub", "https://www.amazon.in/dp/B0HISTMLT1", initial_price=1200, timestamp=now - 100)
        
        # Add newer price Rs. 1000 (t = now - 50)
        ph2 = PriceHistory(
            product_id="B0HISTMLT1",
            price=1000,
            mrp=2000,
            discount=50.0,
            is_verified_low=True,
            deal_score=80.0,
            timestamp=now - 50
        )
        self.db.add(ph2)
        self.db.commit()

        mock_expand.return_value = "https://www.amazon.in/dp/B0HISTMLT1"
        mock_scrape.return_value = {
            "title": "USB Hub",
            "price": 900, # Lower than latest price of 1000
            "mrp": 2000,
            "discount": 55.0,
            "img_url": "https://images.amazon.com/hub.jpg"
        }
        mock_save.return_value = "B0HISTMLT1"

        msg = NormalizedMessage(
            channel_id="test_channel_123",
            channel_name="test_channel",
            message_id=104,
            correlation_id="test-corr-04",
            extracted_urls=["https://amzn.to/hub900"]
        )

        self.processor._process_single_raw_url(
            raw_url="https://amzn.to/hub900",
            correlation_id="test-corr-04",
            message=msg,
            extracted_data={},
            db=self.db
        )

        mock_enqueue.assert_called_once()
        self.assertEqual(mock_enqueue.call_args.kwargs["price"], 900)

    @patch("deal_engine.notifier.enqueue_alert")
    @patch("deal_engine.mirroring.processor.scrape_product_details")
    @patch("deal_engine.mirroring.processor.DealMirrorProcessor._expand_url_with_retry")
    def test_05_multi_point_history_same_price_rejected(self, mock_expand, mock_scrape, mock_enqueue):
        """Scenario 5: History Rs. 1200, Rs. 1000 -> Incoming Rs. 1000 must be rejected."""
        now = time.time()
        self._seed_product("B0HISTREJ1", "Webcam", "https://www.amazon.in/dp/B0HISTREJ1", initial_price=1200, timestamp=now - 100)
        
        ph2 = PriceHistory(
            product_id="B0HISTREJ1",
            price=1000,
            mrp=2500,
            discount=60.0,
            is_verified_low=True,
            deal_score=85.0,
            timestamp=now - 50
        )
        self.db.add(ph2)
        self.db.commit()

        mock_expand.return_value = "https://www.amazon.in/dp/B0HISTREJ1"
        mock_scrape.return_value = {
            "title": "Webcam",
            "price": 1000, # Same as latest price of 1000 (even though lower than original 1200)
            "mrp": 2500,
            "discount": 60.0,
            "img_url": "https://images.amazon.com/cam.jpg"
        }

        msg = NormalizedMessage(
            channel_id="test_channel_123",
            channel_name="test_channel",
            message_id=105,
            correlation_id="test-corr-05",
            extracted_urls=["https://amzn.to/cam1000"]
        )

        self.processor._process_single_raw_url(
            raw_url="https://amzn.to/cam1000",
            correlation_id="test-corr-05",
            message=msg,
            extracted_data={},
            db=self.db
        )

        mock_enqueue.assert_not_called()

    @patch("deal_engine.notifier.enqueue_alert")
    @patch("deal_engine.mirroring.processor.scrape_product_details")
    @patch("deal_engine.mirroring.processor.DealMirrorProcessor._expand_url_with_retry")
    def test_06_existing_product_price_increase_rejected(self, mock_expand, mock_scrape, mock_enqueue):
        """Scenario 6: History Rs. 1000 -> Incoming Rs. 1200 (price increase) must be rejected."""
        self._seed_product("B0PRICEINC", "Smart Watch", "https://www.amazon.in/dp/B0PRICEINC", initial_price=1000)

        mock_expand.return_value = "https://www.amazon.in/dp/B0PRICEINC"
        mock_scrape.return_value = {
            "title": "Smart Watch",
            "price": 1200, # Price increased from Rs. 1000 to Rs. 1200
            "mrp": 2500,
            "discount": 52.0,
            "img_url": "https://images.amazon.com/watch.jpg"
        }

        msg = NormalizedMessage(
            channel_id="test_channel_123",
            channel_name="test_loot_channel",
            message_id=106,
            correlation_id="test-corr-06",
            extracted_urls=["https://amzn.to/priceinc"],
            raw_text="Smart Watch Deal"
        )

        self.processor._process_single_raw_url(
            raw_url="https://amzn.to/priceinc",
            correlation_id="test-corr-06",
            message=msg,
            extracted_data={},
            db=self.db
        )

        mock_enqueue.assert_not_called()

    @patch("deal_engine.notifier.enqueue_alert")
    @patch("deal_engine.mirroring.processor.save_deal_to_db")
    @patch("deal_engine.mirroring.processor.calculate_deal_score", return_value=90.0)
    @patch("deal_engine.mirroring.processor.scrape_product_details")
    @patch("deal_engine.mirroring.processor.DealMirrorProcessor._expand_url_with_retry")
    def test_07_existing_product_no_price_history_accepted(self, mock_expand, mock_scrape, mock_score, mock_save, mock_enqueue):
        """Scenario 7: Product exists in DB with no PriceHistory records -> must be accepted."""
        # Seed product with NO price history
        self._seed_product("B0NOHIST01", "Laptop Stand", "https://www.amazon.in/dp/B0NOHIST01", create_price_history=False)

        mock_expand.return_value = "https://www.amazon.in/dp/B0NOHIST01"
        mock_scrape.return_value = {
            "title": "Laptop Stand",
            "price": 599,
            "mrp": 1499,
            "discount": 60.0,
            "img_url": "https://images.amazon.com/stand.jpg"
        }
        mock_save.return_value = "B0NOHIST01"

        msg = NormalizedMessage(
            channel_id="test_channel_123",
            channel_name="test_channel",
            message_id=107,
            correlation_id="test-corr-07",
            extracted_urls=["https://amzn.to/stand"]
        )

        self.processor._process_single_raw_url(
            raw_url="https://amzn.to/stand",
            correlation_id="test-corr-07",
            message=msg,
            extracted_data={},
            db=self.db
        )

        mock_enqueue.assert_called_once()
        self.assertEqual(mock_enqueue.call_args.kwargs["unique_id"], "B0NOHIST01")
        self.assertEqual(mock_enqueue.call_args.kwargs["price"], 599)

    @patch("deal_engine.notifier.enqueue_alert")
    @patch("deal_engine.mirroring.processor.save_deal_to_db")
    @patch("deal_engine.mirroring.processor.calculate_deal_score", return_value=92.0)
    @patch("deal_engine.mirroring.processor.scrape_product_details")
    @patch("deal_engine.mirroring.processor.DealMirrorProcessor._expand_url_with_retry")
    def test_08_canonical_url_match_price_drop_accepted(self, mock_expand, mock_scrape, mock_score, mock_save, mock_enqueue):
        """Scenario 8: Matching via canonical URL with price drop must be accepted."""
        # Seed product with full canonical URL
        self._seed_product("B0CANONMT1", "Power Bank", "https://www.amazon.in/dp/B0CANONMT1", initial_price=1200)

        # Incoming URL has extra tracking query params that resolve to same canonical URL
        mock_expand.return_value = "https://www.amazon.in/dp/B0CANONMT1?tag=comp-21&psc=1"
        mock_scrape.return_value = {
            "title": "Power Bank 20000mAh",
            "price": 899, # Price dropped from 1200 to 899
            "mrp": 2499,
            "discount": 64.0,
            "img_url": "https://images.amazon.com/pb.jpg"
        }
        mock_save.return_value = "B0CANONMT1"

        msg = NormalizedMessage(
            channel_id="test_channel_123",
            channel_name="test_channel",
            message_id=108,
            correlation_id="test-corr-08",
            extracted_urls=["https://amzn.to/pbdeal"]
        )

        self.processor._process_single_raw_url(
            raw_url="https://amzn.to/pbdeal",
            correlation_id="test-corr-08",
            message=msg,
            extracted_data={},
            db=self.db
        )

        mock_enqueue.assert_called_once()
        self.assertEqual(mock_enqueue.call_args.kwargs["unique_id"], "B0CANONMT1")
        self.assertEqual(mock_enqueue.call_args.kwargs["price"], 899)


if __name__ == "__main__":
    unittest.main()
