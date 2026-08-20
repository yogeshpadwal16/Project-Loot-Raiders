"""
Security Boundaries, RBAC Privilege Enums, Prompt Injection Defense, and Audit Logging.
"""

from enum import Enum
import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PrivilegeScope(str, Enum):
    """Privilege tiers for tools, agents, and autonomous operations."""
    READ_ONLY = "READ_ONLY"
    SAFE_WRITE = "SAFE_WRITE"
    SENSITIVE_WRITE = "SENSITIVE_WRITE"
    ADMIN = "ADMIN"


class SecurityViolationError(Exception):
    """Raised when an operation attempts to exceed its granted privilege boundary."""
    pass


class AuditLogEntry(BaseModel):
    """Immutable audit trail entry for every security-sensitive action."""
    timestamp: float = Field(default_factory=time.time)
    agent_id: str
    action_name: str
    required_scope: PrivilegeScope
    granted_scope: PrivilegeScope
    allowed: bool
    details: Dict[str, Any] = Field(default_factory=dict)
    input_hash: Optional[str] = None


class SecurityBoundary:
    """
    Enforces RBAC boundaries and monitors privilege escalation attempts.
    """
    def __init__(self, max_allowed_scope: PrivilegeScope = PrivilegeScope.SAFE_WRITE):
        self.max_allowed_scope = max_allowed_scope
        self._audit_logs: List[AuditLogEntry] = []

    SCOPE_HIERARCHY = {
        PrivilegeScope.READ_ONLY: 1,
        PrivilegeScope.SAFE_WRITE: 2,
        PrivilegeScope.SENSITIVE_WRITE: 3,
        PrivilegeScope.ADMIN: 4,
    }

    def check_permission(
        self,
        agent_id: str,
        action_name: str,
        required_scope: PrivilegeScope,
        agent_max_scope: Optional[PrivilegeScope] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        effective_max = agent_max_scope or self.max_allowed_scope
        req_level = self.SCOPE_HIERARCHY[required_scope]
        allowed_level = self.SCOPE_HIERARCHY[effective_max]

        is_allowed = req_level <= allowed_level

        log_entry = AuditLogEntry(
            agent_id=agent_id,
            action_name=action_name,
            required_scope=required_scope,
            granted_scope=effective_max,
            allowed=is_allowed,
            details=context or {},
        )
        self._audit_logs.append(log_entry)

        if not is_allowed:
            raise SecurityViolationError(
                f"Agent '{agent_id}' attempted action '{action_name}' requiring scope "
                f"[{required_scope.value}], but holds maximum scope [{effective_max.value}]."
            )
        return True

    def get_audit_logs(self) -> List[AuditLogEntry]:
        return list(self._audit_logs)


class InputSanitizer:
    """
    Defends against prompt injection, malicious markup, control token tampering,
    and secret credential leakage in untrusted scraped/external content.
    """
    # Patterns targeting prompt injection delimiters & control codes
    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"<\|im_start\|>", re.IGNORECASE),
        re.compile(r"<\|im_end\|>", re.IGNORECASE),
        re.compile(r"\[SYSTEM_INSTRUCTION\]", re.IGNORECASE),
        re.compile(r"\[OVERRIDE_RULES\]", re.IGNORECASE),
        re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+a\s+unrestricted", re.IGNORECASE),
        re.compile(r"system\s*:\s*you\s+must", re.IGNORECASE),
    ]

    # Secret masking patterns (API keys, Telegram bot tokens, AWS keys)
    SECRET_MASK_PATTERNS = [
        (re.compile(r"(bot)?\d{8,10}:[A-Za-z0-9_-]{35}"), "[MASKED_TELEGRAM_TOKEN]"),
        (re.compile(r"sk-[A-Za-z0-9]{32,64}"), "[MASKED_OPENAI_KEY]"),
        (re.compile(r"AKIA[0-9A-Z]{16}"), "[MASKED_AWS_KEY]"),
    ]

    @classmethod
    def sanitize_text(cls, raw_text: str) -> str:
        """Sanitizes text by stripping prompt injection triggers and masking secrets."""
        if not raw_text:
            return ""

        cleaned = raw_text
        # Strip injection triggers
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            cleaned = pattern.sub("[NEUTRALIZED_PROMPT_INJECTION]", cleaned)

        # Mask sensitive keys if inadvertently present
        for pattern, replacement in cls.SECRET_MASK_PATTERNS:
            cleaned = pattern.sub(replacement, cleaned)

        return cleaned.strip()

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitizes dictionary strings."""
        sanitized = {}
        for key, val in data.items():
            if isinstance(val, str):
                sanitized[key] = cls.sanitize_text(val)
            elif isinstance(val, dict):
                sanitized[key] = cls.sanitize_dict(val)
            elif isinstance(val, list):
                sanitized[key] = [
                    cls.sanitize_text(v) if isinstance(v, str)
                    else (cls.sanitize_dict(v) if isinstance(v, dict) else v)
                    for v in val
                ]
            else:
                sanitized[key] = val
        return sanitized
