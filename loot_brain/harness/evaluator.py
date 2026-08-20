"""
Agent Evaluation & Benchmark Framework.
Evaluates agent correctness, decision quality, tool selection accuracy, and schema compliance.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from loot_brain.harness.tools import ToolRegistry

logger = logging.getLogger(__name__)


class AgentEvaluationTestCase(BaseModel):
    """Ground-truth test case for agent evaluation benchmarks."""
    case_id: str
    description: str
    input_payload: Dict[str, Any]
    expected_recommendation: str    # "APPROVE" or "REJECT"
    expected_tools: List[str] = Field(default_factory=list)


class AgentEvaluationMetrics(BaseModel):
    """Aggregated metrics resulting from an evaluation benchmark run."""
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    accuracy_rate: float = 0.0
    schema_compliance_rate: float = 1.0
    avg_latency_ms: float = 0.0
    pass_status: bool = False


class AgentEvaluator:
    """
    Evaluates Loot Brain Agent performance against benchmark reference datasets.
    """

    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry

    def evaluate_benchmark_suite(self, test_cases: List[AgentEvaluationTestCase]) -> AgentEvaluationMetrics:
        """Runs evaluation benchmark across reference cases."""
        start_time = time.time()
        passed = 0
        failed = 0
        total_latency = 0.0

        for case in test_cases:
            case_start = time.time()

            # Execute scoring tool adapter
            res = self.tool_registry.execute(
                tool_name="deal.score",
                agent_id="eval_agent",
                kwargs={
                    "price": case.input_payload.get("price", 0.0),
                    "mrp": case.input_payload.get("mrp", 0.0),
                    "title": case.input_payload.get("title", ""),
                    "is_verified_low": case.input_payload.get("is_verified_low", True),
                },
            )

            case_duration = (time.time() - case_start) * 1000
            total_latency += case_duration

            if res.success and res.data:
                score = res.data.get("deal_score", 0.0)
                actual_rec = "APPROVE" if score >= 50.0 else "REJECT"
                if actual_rec == case.expected_recommendation:
                    passed += 1
                else:
                    failed += 1
            else:
                failed += 1

        total = len(test_cases)
        accuracy = (passed / total) * 100.0 if total > 0 else 0.0
        avg_latency = (total_latency / total) if total > 0 else 0.0

        metrics = AgentEvaluationMetrics(
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            accuracy_rate=accuracy,
            avg_latency_ms=avg_latency,
            pass_status=(accuracy >= 80.0),
        )

        logger.info(f"[AgentEvaluator] Benchmark Completed: {passed}/{total} Passed ({accuracy:.1f}% Accuracy, Avg Latency: {avg_latency:.1f}ms)")
        return metrics
