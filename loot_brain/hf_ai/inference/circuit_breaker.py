"""
Circuit Breaker Pattern for Local AI Inference Engine.
Prevents pipeline latency degradation during local model timeout or RAM saturation.
"""

from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Circuit tripped; block AI calls instantly
    HALF_OPEN = "HALF_OPEN"# Testing recovery


class InferenceCircuitBreaker:
    """
    Protects latency-critical deal pipeline from model inference failures.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout_sec: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def allow_execution(self) -> bool:
        """Returns True if inference call is allowed to execute."""
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_state_change > self.recovery_timeout_sec:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                logger.info("[InferenceCircuitBreaker] Circuit state changed to HALF_OPEN. Testing recovery...")
                return True
            return False
        return True

    def record_success(self) -> None:
        if self.state != CircuitState.CLOSED:
            logger.info("[InferenceCircuitBreaker] Circuit state reset to CLOSED.")
        self.state = CircuitState.CLOSED
        self.failure_count = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
            logger.error(f"[InferenceCircuitBreaker] Failure threshold ({self.failure_threshold}) hit. Circuit state TRIPPED to OPEN!")
