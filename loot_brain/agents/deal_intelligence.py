"""
Deal Intelligence Agent evaluating hard safety rules, pricing anomalies, and deal scores.
"""

import time
from typing import Any, Dict, List, Optional

from loot_brain.agents.base_agent import BaseAgent, AgentReport
from loot_brain.context.schemas import DealPayload, MemoryCategory, MemoryEntry, MemoryType
from loot_brain.security.permissions import PrivilegeScope, InputSanitizer


class DealIntelligenceAgent(BaseAgent):
    """
    Autonomous Deal Intelligence Agent.
    Combines deterministic hard rules with evaluation heuristics.
    """

    def __init__(self, min_discount_threshold: float = 20.0):
        super().__init__(
            agent_id="deal_intelligence_agent",
            name="Deal Intelligence Agent",
            role="Deal Evaluation and Risk Scoring",
            capabilities=["evaluate_deal", "score_deal", "anomaly_check"],
            max_privilege_scope=PrivilegeScope.READ_ONLY,
        )
        self.min_discount_threshold = min_discount_threshold

    def observe(self, input_data: Any) -> Dict[str, Any]:
        """Stage 1: Ingest raw deal dictionary or URL payload."""
        if isinstance(input_data, dict):
            return InputSanitizer.sanitize_dict(input_data)
        return {"title": str(input_data), "deal_price": 0.0, "original_price": 0.0}

    def understand(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 2: Parse and validate pricing attributes."""
        title = observation.get("title", "Untitled Deal")
        orig_price = float(observation.get("original_price", 0.0))
        deal_price = float(observation.get("deal_price", 0.0))

        discount_pct = 0.0
        if orig_price > 0 and orig_price >= deal_price:
            discount_pct = round(((orig_price - deal_price) / orig_price) * 100, 2)

        return {
            "deal_id": observation.get("deal_id", f"deal-{int(time.time())}"),
            "title": title,
            "original_price": orig_price,
            "deal_price": deal_price,
            "discount_percentage": discount_pct,
            "merchant": observation.get("merchant", "Generic"),
            "store": observation.get("store", "Generic"),
            "url": observation.get("url", "https://example.com"),
            "in_stock": observation.get("in_stock", True),
            "coupon_code": observation.get("coupon_code"),
        }

    def plan(self, understood: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 3: Plan decision based on hard rules and scoring logic."""
        reasons: List[str] = []
        is_hard_rule_failed = False

        if not understood["in_stock"]:
            reasons.append("Hard Rule Violation: Product out of stock")
            is_hard_rule_failed = True

        if understood["discount_percentage"] < self.min_discount_threshold:
            reasons.append(f"Hard Rule Violation: Discount ({understood['discount_percentage']}%) below threshold ({self.min_discount_threshold}%)")
            is_hard_rule_failed = True

        if understood["deal_price"] <= 0:
            reasons.append("Hard Rule Violation: Deal price must be greater than zero")
            is_hard_rule_failed = True

        return {
            "understood": understood,
            "is_hard_rule_failed": is_hard_rule_failed,
            "reasons": reasons,
        }

    def execute(self, plan: Dict[str, Any]) -> DealPayload:
        """Stage 4: Execute scoring formulas and form recommendation."""
        u = plan["understood"]
        reasons = plan["reasons"]

        if plan["is_hard_rule_failed"]:
            recommendation = "REJECT"
            deal_score = 10.0
            quality_score = 10.0
            risk_score = 90.0
        else:
            recommendation = "PUBLISH" if u["discount_percentage"] >= 30.0 else "HOLD"
            deal_score = min(100.0, u["discount_percentage"] * 1.5 + 20.0)
            quality_score = 80.0
            risk_score = 15.0
            reasons.append(f"Valid deal with {u['discount_percentage']}% discount")

        savings = max(0.0, u["original_price"] - u["deal_price"])

        return DealPayload(
            deal_id=u["deal_id"],
            title=u["title"],
            original_price=u["original_price"],
            deal_price=u["deal_price"],
            discount_percentage=u["discount_percentage"],
            merchant=u["merchant"],
            store=u["store"],
            url=u["url"],
            in_stock=u["in_stock"],
            coupon_code=u["coupon_code"],
            deal_score=deal_score,
            confidence=0.9,
            quality_score=quality_score,
            risk_score=risk_score,
            estimated_savings=savings,
            recommendation=recommendation,
            reasons=reasons,
        )

    def verify(self, payload: DealPayload) -> DealPayload:
        """Stage 5: Verify safety invariants of calculated DealPayload."""
        if payload.recommendation not in ("PUBLISH", "REJECT", "HOLD", "REVIEW"):
            raise ValueError(f"Invalid recommendation generated: {payload.recommendation}")
        if payload.estimated_savings < 0:
            raise ValueError("Estimated savings cannot be negative")
        return payload

    def report(self, verified: DealPayload) -> AgentReport:
        """Stage 6: Generate structured AgentReport."""
        return AgentReport(
            agent_id=self.agent_id,
            task_id="",
            success=verified.recommendation in ("PUBLISH", "HOLD"),
            data=verified.model_dump(),
        )

    def remember(self, report: AgentReport) -> List[MemoryEntry]:
        """Stage 7: Formulate deal memory entry."""
        if not report.data:
            return []

        mem = MemoryEntry(
            memory_id=f"mem-deal-{report.data.get('deal_id', int(time.time()))}",
            category=MemoryCategory.DEAL,
            memory_type=MemoryType.DECISION,
            title=f"Deal Evaluation: {report.data.get('title')}",
            content=f"Recommendation: {report.data.get('recommendation')}, Score: {report.data.get('deal_score')}, Reasons: {report.data.get('reasons')}",
            confidence=0.9,
            agent_id=self.agent_id,
        )
        return [mem]
