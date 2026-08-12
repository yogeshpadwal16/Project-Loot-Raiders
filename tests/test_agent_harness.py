"""
Unit Test Suite for Loot Raiders Agent Harness Layer.
Verifies ToolRegistry, SideEffectLevel safety checks, CheckpointStore, FailureClassifier,
RecoveryEngine, CostTracker, LoopProtector, ApprovalGate, ShadowRunner, and AgentEvaluator.
"""

import unittest
import os
import time

from loot_brain.harness.tools import ToolRegistry, ToolDefinition, SideEffectLevel
from loot_brain.harness.checkpoints import CheckpointStore, TaskExecutionTrace
from loot_brain.harness.recovery import FailureClassifier, FailureType, RecoveryEngine, RecoveryActionType
from loot_brain.harness.governance import CostTracker, LoopProtector, AgentBudget, BudgetExceededError, RunawayLoopError
from loot_brain.harness.approval import ApprovalGate, ApprovalStatus
from loot_brain.harness.shadow import ShadowRunner
from loot_brain.harness.evaluator import AgentEvaluator, AgentEvaluationTestCase
from loot_brain.security.permissions import SecurityBoundary, PrivilegeScope, SecurityViolationError


class TestAgentHarness(unittest.TestCase):

    def setUp(self):
        self.tool_registry = ToolRegistry()
        self.checkpoint_store = CheckpointStore(db_path=":memory:")
        self.recovery_engine = RecoveryEngine()
        self.cost_tracker = CostTracker()
        self.loop_protector = LoopProtector()
        self.approval_gate = ApprovalGate()

    def test_tool_registry_default_adapters(self):
        """Verify default tools are registered and functional."""
        tools = self.tool_registry.list_tools()
        names = [t.name for t in tools]
        self.assertIn("deal.score", names)
        self.assertIn("affiliate.convert", names)
        self.assertIn("dedup.check", names)
        self.assertIn("telegram.publish", names)

    def test_tool_execution_deal_score(self):
        """Test deal.score tool execution."""
        res = self.tool_registry.execute(
            tool_name="deal.score",
            agent_id="test_agent",
            kwargs={"price": 499.0, "mrp": 1999.0, "title": "Wireless Earbuds", "is_verified_low": True},
        )
        self.assertTrue(res.success)
        self.assertIn("deal_score", res.data)
        self.assertGreater(res.data["deal_score"], 50.0)

    def test_security_boundary_rbac_enforcement(self):
        """Test RBAC privilege boundary check blocks unauthorized tool call."""
        sec = SecurityBoundary(max_allowed_scope=PrivilegeScope.READ_ONLY)
        res = self.tool_registry.execute(
            tool_name="affiliate.convert", # Requires SAFE_WRITE
            agent_id="unprivileged_agent",
            kwargs={"url": "https://amazon.in/dp/123456"},
            security_boundary=sec,
            agent_scope=PrivilegeScope.READ_ONLY,
        )
        self.assertFalse(res.success)
        self.assertIn("Security Policy Block", res.error)

    def test_checkpoint_store_save_and_retrieve(self):
        """Test durable checkpoint saving and retrieval."""
        task_id = "task-test-100"
        chk = self.checkpoint_store.save_checkpoint(
            task_id=task_id,
            step_name="PRE_PUBLISH",
            task_state="REVIEW",
            payload={"title": "Test Laptop", "price": 45000},
        )
        self.assertIsNotNone(chk.checkpoint_id)
        
        latest = self.checkpoint_store.get_latest_checkpoint(task_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.step_name, "PRE_PUBLISH")
        self.assertEqual(latest.payload_snapshot["price"], 45000)

    def test_failure_classifier_taxonomy(self):
        """Test error classification taxonomy."""
        self.assertEqual(FailureClassifier.classify("429 Too Many Requests"), FailureType.RATE_LIMIT)
        self.assertEqual(FailureClassifier.classify("502 Bad Gateway timeout"), FailureType.TRANSIENT)
        self.assertEqual(FailureClassifier.classify("401 Unauthorized API key"), FailureType.AUTH)
        self.assertEqual(FailureClassifier.classify("Security Policy Block error"), FailureType.POLICY)

    def test_recovery_engine_policy(self):
        """Test failure recovery plan generation."""
        plan_rate = self.recovery_engine.evaluate_recovery("429 Too Many Requests", retry_count=0)
        self.assertEqual(plan_rate.action, RecoveryActionType.RETRY_WITH_BACKOFF)
        self.assertTrue(plan_rate.can_retry)

        plan_auth = self.recovery_engine.evaluate_recovery("401 Unauthorized token", retry_count=0)
        self.assertEqual(plan_auth.action, RecoveryActionType.ESCALATE_HUMAN)
        self.assertFalse(plan_auth.can_retry)

    def test_cost_tracker_budget(self):
        """Test token cost tracking and budget enforcement."""
        task_id = "task-cost-1"
        self.cost_tracker.record_usage(task_id, input_tokens=1000, output_tokens=500)
        cost = self.cost_tracker.get_task_cost(task_id)
        self.assertGreater(cost, 0.0)

        budget = AgentBudget(max_cost_usd_per_task=0.0001)
        with self.assertRaises(BudgetExceededError):
            self.cost_tracker.check_budget(task_id, budget)

    def test_loop_protector(self):
        """Test loop protection iteration limits."""
        task_id = "task-loop-1"
        budget = AgentBudget(max_iterations=2)
        
        self.loop_protector.tick_iteration(task_id, budget)
        self.loop_protector.tick_iteration(task_id, budget)
        
        with self.assertRaises(RunawayLoopError):
            self.loop_protector.tick_iteration(task_id, budget)

    def test_approval_gate(self):
        """Test Human Approval Gate escalation and review."""
        self.assertTrue(self.approval_gate.requires_approval(SideEffectLevel.HIGH_IMPACT))
        self.assertFalse(self.approval_gate.requires_approval(SideEffectLevel.READ_ONLY))

        req = self.approval_gate.submit_request(
            task_id="task-appr-1",
            agent_id="test_agent",
            action_name="config.update",
            side_effect_level=SideEffectLevel.HIGH_IMPACT,
            payload_summary={"setting": "scrape_interval", "val": 30},
        )
        self.assertEqual(req.status, ApprovalStatus.PENDING)
        
        appr_req = self.approval_gate.approve(req.request_id, "Approved by admin")
        self.assertIsNotNone(appr_req)
        self.assertEqual(appr_req.status, ApprovalStatus.APPROVED)

    def test_shadow_runner(self):
        """Test Shadow Mode execution suppressing side-effects."""
        shadow = ShadowRunner(self.tool_registry, self.checkpoint_store)
        report = shadow.run_shadow_deal_pipeline(
            task_id="task-shadow-1",
            raw_deal_data={"title": "Sony Headphones", "price": 2999.0, "mrp": 7999.0, "url": "https://amazon.in/dp/B00123"},
        )
        self.assertTrue(report.shadow_mode)
        self.assertTrue(report.would_publish)
        self.assertTrue(report.suppressed_side_effects["telegram.publish"]["suppressed"])

    def test_agent_evaluator(self):
        """Test AgentEvaluator benchmark suite."""
        evaluator = AgentEvaluator(self.tool_registry)
        cases = [
            AgentEvaluationTestCase(
                case_id="c1",
                description="80% discount deal",
                input_payload={"title": "Test Item 1", "price": 200.0, "mrp": 1000.0},
                expected_recommendation="APPROVE",
            ),
            AgentEvaluationTestCase(
                case_id="c2",
                description="1% discount deal",
                input_payload={"title": "Test Item 2", "price": 990.0, "mrp": 1000.0},
                expected_recommendation="REJECT",
            ),
        ]
        metrics = evaluator.evaluate_benchmark_suite(cases)
        self.assertEqual(metrics.total_cases, 2)
        self.assertEqual(metrics.passed_cases, 2)
        self.assertTrue(metrics.pass_status)


if __name__ == "__main__":
    unittest.main()
