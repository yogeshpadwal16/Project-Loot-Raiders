"""
Cost Governance, Token Accounting & Runaway Loop Protection Subsystem.
Prevents runaway model iterations, enforces per-agent cost budgets, and tracks resource metrics.
"""

import logging
import time
from typing import Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when an agent task exceeds its allowed token or cost budget."""
    pass


class RunawayLoopError(Exception):
    """Raised when an agent execution exceeds iteration or time limits."""
    pass


class AgentBudget(BaseModel):
    """Configurable resource limits for an agent role or task execution."""
    max_cost_usd_per_task: float = 0.50
    max_total_tokens_per_task: int = 25000
    max_tool_calls_per_task: int = 15
    max_iterations: int = 10
    max_execution_time_seconds: float = 60.0


class CostTracker:
    """
    Tracks model input/output token counts and estimates total USD expenditure.
    Model Rates (per 1,000 tokens):
      - Fast (Gemini Flash / GPT-4o-mini): $0.00015 input, $0.0006 output
      - Advanced (Gemini Pro / Claude 3.5): $0.003 input, $0.015 output
    """

    DEFAULT_INPUT_COST_PER_1K = 0.0005
    DEFAULT_OUTPUT_COST_PER_1K = 0.0015

    def __init__(self):
        self._task_input_tokens: Dict[str, int] = {}
        self._task_output_tokens: Dict[str, int] = {}
        self._task_costs_usd: Dict[str, float] = {}

    def record_usage(
        self,
        task_id: str,
        input_tokens: int,
        output_tokens: int,
        custom_input_rate: Optional[float] = None,
        custom_output_rate: Optional[float] = None,
    ) -> float:
        """Records token usage for a task and returns estimated cost added."""
        in_rate = custom_input_rate if custom_input_rate is not None else self.DEFAULT_INPUT_COST_PER_1K
        out_rate = custom_output_rate if custom_output_rate is not None else self.DEFAULT_OUTPUT_COST_PER_1K

        cost_added = ((input_tokens / 1000.0) * in_rate) + ((output_tokens / 1000.0) * out_rate)

        self._task_input_tokens[task_id] = self._task_input_tokens.get(task_id, 0) + input_tokens
        self._task_output_tokens[task_id] = self._task_output_tokens.get(task_id, 0) + output_tokens
        self._task_costs_usd[task_id] = self._task_costs_usd.get(task_id, 0.0) + cost_added

        logger.info(f"[CostTracker] Task '{task_id}': +{input_tokens}in/+{output_tokens}out -> +${cost_added:.5f} USD (Total: ${self._task_costs_usd[task_id]:.4f})")
        return cost_added

    def get_task_cost(self, task_id: str) -> float:
        return self._task_costs_usd.get(task_id, 0.0)

    def check_budget(self, task_id: str, budget: AgentBudget) -> None:
        """Enforces token and cost limits for a task."""
        current_cost = self.get_task_cost(task_id)
        current_tokens = self._task_input_tokens.get(task_id, 0) + self._task_output_tokens.get(task_id, 0)

        if current_cost > budget.max_cost_usd_per_task:
            raise BudgetExceededError(
                f"Task '{task_id}' cost (${current_cost:.4f}) exceeded max limit (${budget.max_cost_usd_per_task:.4f})."
            )

        if current_tokens > budget.max_total_tokens_per_task:
            raise BudgetExceededError(
                f"Task '{task_id}' token count ({current_tokens}) exceeded max limit ({budget.max_total_tokens_per_task})."
            )


class LoopProtector:
    """
    Monitors execution state to prevent infinite loops, stack overflows, and time explosions.
    """

    def __init__(self):
        self._task_iterations: Dict[str, int] = {}
        self._task_tool_calls: Dict[str, int] = {}
        self._task_start_times: Dict[str, float] = {}

    def start_task(self, task_id: str) -> None:
        self._task_iterations[task_id] = 0
        self._task_tool_calls[task_id] = 0
        self._task_start_times[task_id] = time.time()

    def tick_iteration(self, task_id: str, budget: AgentBudget) -> int:
        if task_id not in self._task_start_times:
            self.start_task(task_id)

        self._task_iterations[task_id] += 1
        current_iters = self._task_iterations[task_id]
        elapsed = time.time() - self._task_start_times[task_id]

        if current_iters > budget.max_iterations:
            raise RunawayLoopError(
                f"Task '{task_id}' exceeded maximum allowed iterations ({budget.max_iterations})."
            )

        if elapsed > budget.max_execution_time_seconds:
            raise RunawayLoopError(
                f"Task '{task_id}' execution time ({elapsed:.1f}s) exceeded timeout ({budget.max_execution_time_seconds:.1f}s)."
            )

        return current_iters

    def record_tool_call(self, task_id: str, budget: AgentBudget) -> int:
        self._task_tool_calls[task_id] = self._task_tool_calls.get(task_id, 0) + 1
        current_calls = self._task_tool_calls[task_id]

        if current_calls > budget.max_tool_calls_per_task:
            raise RunawayLoopError(
                f"Task '{task_id}' exceeded max tool call limit ({budget.max_tool_calls_per_task})."
            )
        return current_calls
