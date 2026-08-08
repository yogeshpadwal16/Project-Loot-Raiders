"""
Dynamic 2-Tier Model Router supporting provider fallbacks and evaluation metrics tracking.
"""

from enum import Enum
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from loot_brain.context.schemas import EvaluationMetrics


class ModelTier(str, Enum):
    LIGHTWEIGHT = "LIGHTWEIGHT"  # Fast, cheap: deal extraction, classification, basic formatting
    FRONTIER = "FRONTIER"        # Complex reasoning: pricing anomalies, multi-agent arbitration, code repair


class TaskComplexity(str, Enum):
    SIMPLE = "SIMPLE"
    MODERATE = "MODERATE"
    COMPLEX = "COMPLEX"
    CRITICAL = "CRITICAL"


class ModelProviderConfig(BaseModel):
    name: str
    tier: ModelTier
    cost_per_1k_prompt_tokens: float
    cost_per_1k_completion_tokens: float
    is_available: bool = True


class ModelRouter:
    """
    Dynamic Router matching task complexity to the optimal LLM Tier.
    Includes cost metrics collection and automatic fallback provider switching.
    """

    DEFAULT_PROVIDERS: Dict[ModelTier, List[ModelProviderConfig]] = {
        ModelTier.LIGHTWEIGHT: [
            ModelProviderConfig(name="gpt-4o-mini", tier=ModelTier.LIGHTWEIGHT, cost_per_1k_prompt_tokens=0.00015, cost_per_1k_completion_tokens=0.0006),
            ModelProviderConfig(name="claude-3-haiku", tier=ModelTier.LIGHTWEIGHT, cost_per_1k_prompt_tokens=0.00025, cost_per_1k_completion_tokens=0.00125),
        ],
        ModelTier.FRONTIER: [
            ModelProviderConfig(name="claude-3-5-sonnet", tier=ModelTier.FRONTIER, cost_per_1k_prompt_tokens=0.003, cost_per_1k_completion_tokens=0.015),
            ModelProviderConfig(name="gpt-4o", tier=ModelTier.FRONTIER, cost_per_1k_prompt_tokens=0.0025, cost_per_1k_completion_tokens=0.01),
        ],
    }

    def __init__(self, custom_providers: Optional[Dict[ModelTier, List[ModelProviderConfig]]] = None):
        self.providers = custom_providers or self.DEFAULT_PROVIDERS
        self.metrics_history: List[EvaluationMetrics] = []

    def route_task(self, task_type: str, complexity: TaskComplexity) -> ModelProviderConfig:
        """Determines target ModelTier based on task complexity."""
        target_tier = ModelTier.LIGHTWEIGHT
        if complexity in (TaskComplexity.COMPLEX, TaskComplexity.CRITICAL):
            target_tier = ModelTier.FRONTIER

        candidates = self.providers.get(target_tier, [])
        active_candidates = [p for p in candidates if p.is_available]

        if not active_candidates:
            # Fallback to alternative tier if primary tier unavailable
            fallback_tier = ModelTier.FRONTIER if target_tier == ModelTier.LIGHTWEIGHT else ModelTier.LIGHTWEIGHT
            active_candidates = [p for p in self.providers.get(fallback_tier, []) if p.is_available]

        if not active_candidates:
            raise RuntimeError("No LLM model providers are currently available.")

        return active_candidates[0]

    def record_usage(
        self,
        task_id: str,
        provider: ModelProviderConfig,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        accuracy_score: float = 1.0,
    ) -> EvaluationMetrics:
        """Calculates USD cost and logs EvaluationMetrics."""
        cost = (
            (prompt_tokens / 1000.0) * provider.cost_per_1k_prompt_tokens +
            (completion_tokens / 1000.0) * provider.cost_per_1k_completion_tokens
        )
        metric = EvaluationMetrics(
            task_id=task_id,
            model_name=provider.name,
            latency_ms=latency_ms,
            token_count_prompt=prompt_tokens,
            token_count_completion=completion_tokens,
            estimated_cost_usd=round(cost, 6),
            accuracy_score=accuracy_score,
        )
        self.metrics_history.append(metric)
        return metric
