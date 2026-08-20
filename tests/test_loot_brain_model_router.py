"""
Unit tests for Loot Brain Model Router & Context Manager.
"""

import unittest

from loot_brain.model_router.router import (
    ModelRouter,
    ModelTier,
    TaskComplexity,
    ModelProviderConfig,
)
from loot_brain.model_router.context_manager import ContextManager


class TestLootBrainModelRouter(unittest.TestCase):

    def setUp(self):
        self.router = ModelRouter()
        self.context_mgr = ContextManager(max_token_budget=1000)

    def test_routing_simple_task(self):
        provider = self.router.route_task("deal_extraction", TaskComplexity.SIMPLE)
        self.assertEqual(provider.tier, ModelTier.LIGHTWEIGHT)
        self.assertEqual(provider.name, "gpt-4o-mini")

    def test_routing_complex_task(self):
        provider = self.router.route_task("price_anomaly_arbitration", TaskComplexity.COMPLEX)
        self.assertEqual(provider.tier, ModelTier.FRONTIER)
        self.assertEqual(provider.name, "claude-3-5-sonnet")

    def test_usage_cost_recording(self):
        provider = self.router.route_task("deal_extraction", TaskComplexity.SIMPLE)
        metric = self.router.record_usage(
            task_id="task-cost-1",
            provider=provider,
            prompt_tokens=1000,
            completion_tokens=500,
            latency_ms=250.0,
        )
        self.assertEqual(metric.task_id, "task-cost-1")
        self.assertGreater(metric.estimated_cost_usd, 0.0)
        self.assertEqual(len(self.router.metrics_history), 1)

    def test_context_budget_assembly(self):
        prompt = self.context_mgr.assemble_prompt_context(
            system_instruction="You are Loot Brain AI.",
            memory_context="[Fact] Low price rule",
            task_input="Evaluate deal URL",
            conversation_history=[
                {"role": "user", "content": "Previous query"},
                {"role": "assistant", "content": "Previous answer"},
            ],
        )
        self.assertIn("You are Loot Brain AI.", prompt)
        self.assertIn("Evaluate deal URL", prompt)
        self.assertIn("Low price rule", prompt)


if __name__ == "__main__":
    unittest.main()
