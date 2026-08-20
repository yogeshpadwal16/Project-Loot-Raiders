"""
Human Approval & Escalation Gate Subsystem.
Intercepts HIGH_IMPACT and IRREVERSIBLE tool actions for human review before execution.
"""

from enum import Enum
import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from loot_brain.harness.tools import SideEffectLevel

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalRequest(BaseModel):
    """Pending human approval request envelope."""
    request_id: str
    task_id: str
    agent_id: str
    action_name: str
    side_effect_level: SideEffectLevel
    payload_summary: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer_notes: Optional[str] = None


class ApprovalGate:
    """
    Approval Gate managing high-risk side-effects.
    Automates safe low-risk work and escalates high-impact operations.
    """

    def __init__(self, auto_approve_side_effects: bool = True):
        self.auto_approve_side_effects = auto_approve_side_effects
        self._requests: Dict[str, ApprovalRequest] = {}

    def requires_approval(self, side_effect_level: SideEffectLevel) -> bool:
        """Determines whether a tool action requires human authorization."""
        if side_effect_level in (SideEffectLevel.HIGH_IMPACT, SideEffectLevel.IRREVERSIBLE):
            return True
        if side_effect_level == SideEffectLevel.SIDE_EFFECT and not self.auto_approve_side_effects:
            return True
        return False

    def submit_request(
        self,
        task_id: str,
        agent_id: str,
        action_name: str,
        side_effect_level: SideEffectLevel,
        payload_summary: Dict[str, Any],
    ) -> ApprovalRequest:
        """Submits a new pending approval request."""
        req_id = f"appr-{task_id}-{int(time.time()*1000)}"
        req = ApprovalRequest(
            request_id=req_id,
            task_id=task_id,
            agent_id=agent_id,
            action_name=action_name,
            side_effect_level=side_effect_level,
            payload_summary=payload_summary,
        )
        self._requests[req_id] = req
        logger.warning(f"[ApprovalGate] Escalate Task '{task_id}': Action '{action_name}' ({side_effect_level.value}) requires human approval. Created request '{req_id}'.")
        return req

    def approve(self, request_id: str, notes: str = "Approved by operator") -> Optional[ApprovalRequest]:
        """Approves a pending request."""
        req = self._requests.get(request_id)
        if req and req.status == ApprovalStatus.PENDING:
            req.status = ApprovalStatus.APPROVED
            req.reviewer_notes = notes
            logger.info(f"[ApprovalGate] Request '{request_id}' APPROVED: {notes}")
            return req
        return None

    def reject(self, request_id: str, notes: str = "Rejected by operator") -> Optional[ApprovalRequest]:
        """Rejects a pending request."""
        req = self._requests.get(request_id)
        if req and req.status == ApprovalStatus.PENDING:
            req.status = ApprovalStatus.REJECTED
            req.reviewer_notes = notes
            logger.info(f"[ApprovalGate] Request '{request_id}' REJECTED: {notes}")
            return req
        return None

    def list_pending(self) -> List[ApprovalRequest]:
        """Returns all currently pending approval requests."""
        return [r for r in self._requests.values() if r.status == ApprovalStatus.PENDING]

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)
