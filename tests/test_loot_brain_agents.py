"""
Unit tests for Loot Brain Phase 3 Agent Registry and Specialized Agents.
"""

import unittest

from loot_brain.agents.registry import AgentRegistry, AgentNotFoundError
from loot_brain.agents.deal_intelligence import DealIntelligenceAgent
from loot_brain.agents.scraper_agent import ScraperAgent
from loot_brain.agents.affiliate_agent import AffiliateAgent
from loot_brain.agents.telegram_agent import TelegramAgent


class TestLootBrainAgents(unittest.TestCase):

    def setUp(self):
        self.registry = AgentRegistry()
        self.deal_agent = DealIntelligenceAgent(min_discount_threshold=20.0)
        self.scraper_agent = ScraperAgent()
        self.affiliate_agent = AffiliateAgent()
        self.telegram_agent = TelegramAgent()

        self.registry.register(self.deal_agent)
        self.registry.register(self.scraper_agent)
        self.registry.register(self.affiliate_agent)
        self.registry.register(self.telegram_agent)

    def test_registry_registration(self):
        agents_list = self.registry.list_agents()
        self.assertEqual(len(agents_list), 4)

        retrieved = self.registry.get_agent("deal_intelligence_agent")
        self.assertEqual(retrieved.name, "Deal Intelligence Agent")

        with self.assertRaises(AgentNotFoundError):
            self.registry.get_agent("non_existent_agent")

    def test_deal_intelligence_agent_valid_deal(self):
        raw_deal = {
            "deal_id": "deal-999",
            "title": "Sony WH-1000XM5 Headphones",
            "original_price": 30000.0,
            "deal_price": 18000.0,
            "merchant": "Amazon",
            "store": "Amazon",
            "url": "https://www.amazon.in/dp/B09XS7JWHH",
            "in_stock": True,
        }
        report = self.registry.dispatch("deal_intelligence_agent", "task-101", raw_deal)

        self.assertTrue(report.success)
        self.assertEqual(report.data["recommendation"], "PUBLISH")
        self.assertEqual(report.data["discount_percentage"], 40.0)
        self.assertEqual(len(report.memories_created), 1)

    def test_deal_intelligence_agent_hard_rule_reject(self):
        low_discount_deal = {
            "deal_id": "deal-888",
            "title": "Generic USB Cable",
            "original_price": 500.0,
            "deal_price": 450.0,  # 10% discount < 20% threshold
            "in_stock": True,
        }
        report = self.registry.dispatch("deal_intelligence_agent", "task-102", low_discount_deal)

        self.assertFalse(report.success)
        self.assertEqual(report.data["recommendation"], "REJECT")
        self.assertIn("Hard Rule Violation", report.data["reasons"][0])

    def test_affiliate_agent_link_conversion(self):
        raw_input = {"url": "https://www.amazon.in/dp/B09XS7JWHH"}
        report = self.registry.dispatch("affiliate_agent", "task-103", raw_input)

        self.assertTrue(report.success)
        self.assertIn("tag=lootraiders-21", report.data["converted_url"])
        self.assertEqual(report.data["provider"], "Amazon")

    def test_telegram_agent_copy_generation(self):
        deal_info = {
            "title": "Sony WH-1000XM5",
            "deal_price": 18000.0,
            "original_price": 30000.0,
            "discount_percentage": 40.0,
            "affiliate_url": "https://www.amazon.in/dp/B09XS7JWHH?tag=lootraiders-21",
            "coupon_code": "AUDIO2000",
            "store": "Amazon",
        }
        report = self.registry.dispatch("telegram_agent", "task-104", deal_info)

        self.assertTrue(report.success)
        self.assertIn("Sony WH-1000XM5", report.data["text_content"])
        self.assertIn("AUDIO2000", report.data["text_content"])
        self.assertEqual(len(report.data["inline_buttons"]), 2)


if __name__ == "__main__":
    unittest.main()
