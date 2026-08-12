"""
Isolated Local AI Inference Engine with Lazy Loading and Fail-Safe Fallback.
"""

import logging
import time
from typing import Any, Callable, Dict, Optional

from loot_brain.hf_ai.config import hf_ai_config
from loot_brain.hf_ai.inference.circuit_breaker import InferenceCircuitBreaker

logger = logging.getLogger(__name__)


class HFInferenceEngine:
    """
    Singleton Inference Engine for local Hugging Face model execution.
    Features lazy loading, memory safety, circuit-breaker protection, and neutral fallbacks.
    """

    def __init__(self):
        self.circuit_breaker = InferenceCircuitBreaker(failure_threshold=3, recovery_timeout_sec=30.0)
        self._models: Dict[str, Any] = {}

    def run_safe_inference(
        self,
        task_name: str,
        inference_func: Callable[..., Any],
        fallback_func: Callable[..., Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes an inference function safely. If local AI is disabled, circuit breaker is OPEN,
        or an error occurs, invokes fallback_func and returns neutral fallback signal.
        """
        start_time = time.time()

        if not hf_ai_config.ENABLE_LOCAL_AI:
            return fallback_func(**kwargs)

        if not self.circuit_breaker.allow_execution():
            logger.debug(f"[HFInferenceEngine] Task '{task_name}' blocked by OPEN circuit breaker. Using fallback.")
            return fallback_func(**kwargs)

        try:
            res = inference_func(**kwargs)
            self.circuit_breaker.record_success()
            return res
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.warning(f"[HFInferenceEngine] Task '{task_name}' failed in {duration:.1f}ms: {e}. Falling back to neutral signal.")
            self.circuit_breaker.record_failure()
            return fallback_func(**kwargs)


# Global Singleton Inference Engine
hf_engine = HFInferenceEngine()
