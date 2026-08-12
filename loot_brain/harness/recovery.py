"""
Failure Classifier & Autonomous Recovery Engine.
Categorizes execution failures and determines safe recovery actions, backoffs, or escalations.
"""

from enum import Enum
import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FailureType(str, Enum):
    """Structured failure categories for agent tasks."""
    TRANSIENT = "TRANSIENT"         # Network timeout, temporary 5xx HTTP error (Retryable)
    DATA = "DATA"                   # Invalid JSON, missing schema field, null price (Validation fix)
    TOOL = "TOOL"                   # DOM selector change, tool handler exception (Fallback tool)
    MODEL = "MODEL"                 # LLM context limit, token overflow, output parse error (Alternative LLM)
    AUTH = "AUTH"                   # API key expired, Telegram bot unauthorized (Escalate human)
    RATE_LIMIT = "RATE_LIMIT"       # 429 Too Many Requests (Exponential delay retry)
    LOGIC = "LOGIC"                 # Business rule rejection, price glitch filter (No retry needed)
    POLICY = "POLICY"               # Security boundary violation, unapproved side-effect (Escalate)
    SYSTEM = "SYSTEM"               # DB disk full, OS error, out of memory (Abort / Escalate)
    UNKNOWN = "UNKNOWN"             # Unclassified exception


class RecoveryActionType(str, Enum):
    """Safe recovery strategies."""
    RETRY_WITH_BACKOFF = "RETRY_WITH_BACKOFF"
    FALLBACK_TOOL = "FALLBACK_TOOL"
    ALTERNATE_MODEL = "ALTERNATE_MODEL"
    ROLLBACK_CHECKPOINT = "ROLLBACK_CHECKPOINT"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    ABORT = "ABORT"


class RecoveryPlan(BaseModel):
    """Actionable plan for recovering from a failure."""
    failure_type: FailureType
    action: RecoveryActionType
    backoff_seconds: float = 0.0
    fallback_tool_name: Optional[str] = None
    reason: str
    can_retry: bool = True


class FailureClassifier:
    """
    Analyzes exceptions and error messages to classify failure taxonomy.
    """

    TRANSIENT_KEYWORDS = ["timeout", "connection refused", "502 bad gateway", "503 service unavailable", "econnreset"]
    RATE_LIMIT_KEYWORDS = ["429", "rate limit", "too many requests", "quota exceeded"]
    AUTH_KEYWORDS = ["401", "403", "unauthorized", "invalid token", "forbidden", "access denied"]
    DATA_KEYWORDS = ["keyerror", "validationerror", "jsondecodeerror", "missing required field", "none type"]
    MODEL_KEYWORDS = ["context length", "max tokens", "model overloaded", "rate_limit_exceeded"]

    @classmethod
    def classify(cls, error_msg: str, exception: Optional[Exception] = None) -> FailureType:
        if not error_msg and not exception:
            return FailureType.UNKNOWN

        msg_lower = (error_msg or str(exception)).lower()

        if any(k in msg_lower for k in cls.AUTH_KEYWORDS):
            return FailureType.AUTH

        if any(k in msg_lower for k in cls.RATE_LIMIT_KEYWORDS):
            return FailureType.RATE_LIMIT

        if any(k in msg_lower for k in cls.TRANSIENT_KEYWORDS):
            return FailureType.TRANSIENT

        if any(k in msg_lower for k in cls.MODEL_KEYWORDS):
            return FailureType.MODEL

        if any(k in msg_lower for k in cls.DATA_KEYWORDS):
            return FailureType.DATA

        if "security policy block" in msg_lower or "privilegescope" in msg_lower:
            return FailureType.POLICY

        if "selector" in msg_lower or "tool execution error" in msg_lower:
            return FailureType.TOOL

        return FailureType.UNKNOWN


class RecoveryEngine:
    """
    Evaluates failure type and current task state to synthesize safe recovery strategy.
    """

    def __init__(self, max_retries: int = 3, initial_backoff_sec: float = 2.0):
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec

    def evaluate_recovery(
        self,
        error_msg: str,
        retry_count: int,
        tool_name: Optional[str] = None,
        exception: Optional[Exception] = None,
    ) -> RecoveryPlan:
        failure_type = FailureClassifier.classify(error_msg, exception)

        # 1. Unrecoverable / Security Policy Failures -> Escalate or Abort
        if failure_type == FailureType.AUTH:
            return RecoveryPlan(
                failure_type=failure_type,
                action=RecoveryActionType.ESCALATE_HUMAN,
                reason="Authentication failure requires manual credential verification.",
                can_retry=False,
            )

        if failure_type == FailureType.POLICY:
            return RecoveryPlan(
                failure_type=failure_type,
                action=RecoveryActionType.ESCALATE_HUMAN,
                reason="Security boundary policy violation requires human review.",
                can_retry=False,
            )

        # 2. Exceeded Retry Limit -> Escalate
        if retry_count >= self.max_retries:
            return RecoveryPlan(
                failure_type=failure_type,
                action=RecoveryActionType.ESCALATE_HUMAN,
                reason=f"Exceeded max retries ({self.max_retries}). Escalating task.",
                can_retry=False,
            )

        # 3. Rate Limit Failures -> Exponential Backoff
        if failure_type == FailureType.RATE_LIMIT:
            backoff = self.initial_backoff_sec * (2 ** retry_count)
            return RecoveryPlan(
                failure_type=failure_type,
                action=RecoveryActionType.RETRY_WITH_BACKOFF,
                backoff_seconds=backoff,
                reason=f"Rate limit encountered. Retrying in {backoff:.1f}s.",
                can_retry=True,
            )

        # 4. Transient Failures -> Short Backoff Retry
        if failure_type == FailureType.TRANSIENT:
            backoff = self.initial_backoff_sec * (1.5 ** retry_count)
            return RecoveryPlan(
                failure_type=failure_type,
                action=RecoveryActionType.RETRY_WITH_BACKOFF,
                backoff_seconds=backoff,
                reason=f"Transient network error. Retrying in {backoff:.1f}s.",
                can_retry=True,
            )

        # 5. Tool / Scraper Selector Failures -> Fallback or Retry
        if failure_type == FailureType.TOOL:
            return RecoveryPlan(
                failure_type=failure_type,
                action=RecoveryActionType.RETRY_WITH_BACKOFF,
                backoff_seconds=1.0,
                reason=f"Tool error in '{tool_name}'. Retrying with fallback handler.",
                can_retry=True,
            )

        # Default fallback
        return RecoveryPlan(
            failure_type=failure_type,
            action=RecoveryActionType.RETRY_WITH_BACKOFF,
            backoff_seconds=self.initial_backoff_sec,
            reason="Generic failure recovery fallback.",
            can_retry=True,
        )
