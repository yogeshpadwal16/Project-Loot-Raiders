"""
Task Lifecycle State Machine Definitions and Transition Guards.
"""

from enum import Enum
import time
from typing import Any, ClassVar, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskState(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    REVIEW = "REVIEW"
    VERIFIED = "VERIFIED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class InvalidStateTransitionError(Exception):
    """Raised when an illegal TaskState transition is attempted."""
    pass


class TaskContext(BaseModel):
    """
    Task Lifecycle Container managing task status, history, retries, and payloads.
    """
    task_id: str
    task_type: str
    current_state: TaskState = TaskState.PENDING
    payload: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    assigned_agent: Optional[str] = None
    error_log: List[str] = Field(default_factory=list)

    # Valid State Transition Matrix
    ALLOWED_TRANSITIONS: ClassVar[Dict[TaskState, List[TaskState]]] = {
        TaskState.PENDING: [TaskState.PLANNING, TaskState.FAILED],
        TaskState.PLANNING: [TaskState.RUNNING, TaskState.FAILED],
        TaskState.RUNNING: [TaskState.WAITING, TaskState.REVIEW, TaskState.VERIFIED, TaskState.FAILED],
        TaskState.WAITING: [TaskState.RUNNING, TaskState.FAILED],
        TaskState.REVIEW: [TaskState.VERIFIED, TaskState.FAILED, TaskState.RETRYING],
        TaskState.VERIFIED: [TaskState.COMPLETED, TaskState.FAILED],
        TaskState.FAILED: [TaskState.RETRYING, TaskState.COMPLETED],
        TaskState.RETRYING: [TaskState.RUNNING, TaskState.FAILED],
        TaskState.COMPLETED: [],
    }

    def transition_to(self, target_state: TaskState, reason: str = "") -> None:
        """Transitions task to a new state if valid according to state machine matrix."""
        allowed = self.ALLOWED_TRANSITIONS.get(self.current_state, [])
        if target_state not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition Task '{self.task_id}' from state [{self.current_state.value}] "
                f"to state [{target_state.value}]. Allowed transitions: {[s.value for s in allowed]}"
            )

        previous_state = self.current_state
        self.current_state = target_state
        self.updated_at = time.time()

        self.history.append({
            "from_state": previous_state.value,
            "to_state": target_state.value,
            "timestamp": self.updated_at,
            "reason": reason,
        })
