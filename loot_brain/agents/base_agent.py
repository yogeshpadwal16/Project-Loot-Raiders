"""
Abstract Base Agent enforcing the 7-stage Lifecycle Contract:
OBSERVE -> UNDERSTAND -> PLAN -> EXECUTE -> VERIFY -> REPORT -> REMEMBER
"""

from abc import ABC, abstractmethod
from enum import Enum
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from loot_brain.security.permissions import PrivilegeScope, SecurityBoundary
from loot_brain.context.schemas import MemoryEntry


class AgentState(str, Enum):
    IDLE = "IDLE"
    OBSERVING = "OBSERVING"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REPORTING = "REPORTING"
    REMEMBERING = "REMEMBERING"
    ERROR = "ERROR"


class AgentReport(BaseModel):
    """Output generated at the REPORT stage of the agent lifecycle."""
    agent_id: str
    task_id: str
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    memories_created: List[MemoryEntry] = Field(default_factory=list)
    execution_time_ms: float = 0.0


class BaseAgent(ABC):
    """
    Abstract Base Class for all Loot Brain Agents.
    Guarantees bounded capabilities, privilege boundary enforcement, and structured lifecycle execution.
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        capabilities: List[str],
        max_privilege_scope: PrivilegeScope = PrivilegeScope.SAFE_WRITE,
        security_boundary: Optional[SecurityBoundary] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.capabilities = capabilities
        self.max_privilege_scope = max_privilege_scope
        self.security_boundary = security_boundary or SecurityBoundary(max_allowed_scope=max_privilege_scope)
        self.state = AgentState.IDLE

    @abstractmethod
    def observe(self, input_data: Any) -> Any:
        """Stage 1: Gather raw signals, input payload, or environmental state."""
        pass

    @abstractmethod
    def understand(self, observation: Any) -> Any:
        """Stage 2: Parse, sanitize, and validate context."""
        pass

    @abstractmethod
    def plan(self, understood_context: Any) -> Any:
        """Stage 3: Formulate deterministic or AI reasoning plan of execution."""
        pass

    @abstractmethod
    def execute(self, plan: Any) -> Any:
        """Stage 4: Execute actions using tools within allowed privilege scope."""
        pass

    @abstractmethod
    def verify(self, execution_result: Any) -> Any:
        """Stage 5: Validate outcome against safety & business invariants."""
        pass

    @abstractmethod
    def report(self, verified_result: Any) -> AgentReport:
        """Stage 6: Synthesize final output report."""
        pass

    @abstractmethod
    def remember(self, report: AgentReport) -> List[MemoryEntry]:
        """Stage 7: Generate experience, outcome, or fact memory records."""
        pass

    def run_lifecycle(self, task_id: str, input_data: Any) -> AgentReport:
        """
        Master Lifecycle Runner executing the 7 stages sequentially.
        """
        start_time = time.time()
        errors: List[str] = []

        try:
            # 1. OBSERVE
            self.state = AgentState.OBSERVING
            observation = self.observe(input_data)

            # 2. UNDERSTAND
            self.state = AgentState.UNDERSTANDING
            understood = self.understand(observation)

            # 3. PLAN
            self.state = AgentState.PLANNING
            plan = self.plan(understood)

            # 4. EXECUTE
            self.state = AgentState.EXECUTING
            execution_res = self.execute(plan)

            # 5. VERIFY
            self.state = AgentState.VERIFYING
            verified_res = self.verify(execution_res)

            # 6. REPORT
            self.state = AgentState.REPORTING
            report = self.report(verified_res)
            report.task_id = task_id
            report.execution_time_ms = (time.time() - start_time) * 1000

            # 7. REMEMBER
            self.state = AgentState.REMEMBERING
            memories = self.remember(report)
            report.memories_created = memories

            self.state = AgentState.IDLE
            return report

        except Exception as e:
            self.state = AgentState.ERROR
            error_msg = f"Lifecycle failure in state [{self.state.value}]: {str(e)}"
            errors.append(error_msg)
            report = AgentReport(
                agent_id=self.agent_id,
                task_id=task_id,
                success=False,
                errors=errors,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
            return report
