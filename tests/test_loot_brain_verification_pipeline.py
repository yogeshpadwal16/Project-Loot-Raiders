"""
Unit tests for Loot Brain 15-Step Deal Verification Pipeline.
"""

from pathlib import Path
import shutil
import tempfile
import unittest

from loot_brain.agents.registry import AgentRegistry
from loot_brain.agents.deal_intelligence import DealIntelligenceAgent
from loot_brain.agents.scraper_agent import ScraperAgent
from loot_brain.agents.affiliate_agent import AffiliateAgent
from loot_brain.agents.telegram_agent import TelegramAgent
from loot_brain.memory.store import MemoryStore
from loot_brain.workflows.deal_verification_pipeline import DealVerificationPipeline


class TestLootBrainVerificationPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test_memory.db")
        self.md_dir = str(Path(self.temp_dir) / "md_store")
        self.store = MemoryStore(db_path=self.db_path, md_base_dir=self.md_dir)

        self.registry = AgentRegistry()
        self.registry.register(DealIntelligenceAgent(min_discount_threshold=20.0))
        self.registry.register(ScraperAgent())
        self.registry.register(AffiliateAgent())
        self.registry.register(TelegramAgent())

        self.pipeline = DealVerificationPipeline(
            registry=self.registry,
            memory_store=self.store,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_15_step_pipeline_success(self):
        deal = {
            "deal_id": "v-101",
            "title": "Sony Bravia 55 inch TV",
            "original_price": 60000.0,
            "deal_price": 36000.0,  # 40% OFF
            "merchant": "Amazon",
            "store": "Amazon",
            "url": "https://www.amazon.in/dp/B08X55TV",
            "in_stock": True,
            "seller_rating": 4.5,
        }

        res = self.pipeline.run_15_step_verification(deal)

        self.assertEqual(len(res.step_results), 15)
        self.assertEqual(res.recommendation, "PUBLISH")
        self.assertIn("lootraiders-21", res.affiliate_url)
        self.assertIsNotNone(res.telegram_text)

    def test_15_step_pipeline_fake_discount_detected(self):
        fake_deal = {
            "deal_id": "v-102",
            "title": "Cheap Watch",
            "original_price": 50000.0,  # 50k original vs 100 deal price = 500x fake MRP
            "deal_price": 100.0,
            "merchant": "Generic",
            "url": "https://example.com/watch",
            "in_stock": True,
        }

        res = self.pipeline.run_15_step_verification(fake_deal)

        step8 = [s for s in res.step_results if s.step_number == 8][0]
        self.assertFalse(step8.passed)
        self.assertTrue(step8.details["fake_discount_detected"])


if __name__ == "__main__":
    unittest.main()
