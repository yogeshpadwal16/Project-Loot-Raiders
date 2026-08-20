"""
Unit tests for Loot Brain Orchestrator Engine.
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
from loot_brain.orchestrator.engine import LootBrainOrchestrator


class TestLootBrainOrchestrator(unittest.TestCase):

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

        self.orchestrator = LootBrainOrchestrator(
            registry=self.registry,
            memory_store=self.store,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pipeline_successful_deal(self):
        raw_deal = {
            "deal_id": "deal-777",
            "title": "MacBook Air M2",
            "original_price": 100000.0,
            "deal_price": 70000.0,  # 30% discount
            "merchant": "Amazon",
            "store": "Amazon",
            "url": "https://www.amazon.in/dp/B0B3C5a12",
            "in_stock": True,
        }

        res = self.orchestrator.process_deal_pipeline("task-777", raw_deal)

        self.assertEqual(res["status"], "APPROVED")
        self.assertIn("lootraiders-21", res["deal_payload"]["affiliate_url"])
        self.assertIn("MacBook Air M2", res["telegram_copy"]["text_content"])
        self.assertIn("COMPLETED", res["history"])

        # Check memory saved
        memories = self.store.search_memories()
        self.assertGreaterEqual(len(memories), 1)

    def test_pipeline_rejected_deal(self):
        low_discount_deal = {
            "deal_id": "deal-666",
            "title": "Basic Phone Case",
            "original_price": 1000.0,
            "deal_price": 950.0,  # 5% discount < 20%
            "merchant": "Amazon",
            "url": "https://www.amazon.in/dp/B0B3C5b34",
            "in_stock": True,
        }

        res = self.orchestrator.process_deal_pipeline("task-666", low_discount_deal)

        self.assertEqual(res["status"], "REJECTED")
        self.assertIn("Hard Rule Violation", res["reason"][0])


if __name__ == "__main__":
    unittest.main()
