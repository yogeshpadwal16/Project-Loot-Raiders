"""
Base Tool Abstraction with Privilege Scope Enforcement and Schema Export.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from loot_brain.security.permissions import PrivilegeScope, SecurityBoundary, SecurityViolationError


class BaseTool(ABC):
    """
    Abstract Base Tool for all Loot Brain tool capabilities.
    Enforces RBAC privilege limits prior to tool execution.
    """

    def __init__(
        self,
        name: str,
        description: str,
        required_scope: PrivilegeScope = PrivilegeScope.READ_ONLY,
    ):
        self.name = name
        self.description = description
        self.required_scope = required_scope

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """JSON Schema defining tool arguments."""
        pass

    @abstractmethod
    def _run(self, **kwargs) -> Any:
        """Internal tool execution implementation."""
        pass

    def run(
        self,
        agent_id: str,
        security_boundary: SecurityBoundary,
        agent_max_scope: Optional[PrivilegeScope] = None,
        **kwargs,
    ) -> Any:
        """
        Executes the tool after validating RBAC permissions through SecurityBoundary.
        """
        security_boundary.check_permission(
            agent_id=agent_id,
            action_name=f"tool:{self.name}",
            required_scope=self.required_scope,
            agent_max_scope=agent_max_scope,
            context={"arguments": kwargs},
        )
        return self._run(**kwargs)

    def to_mcp_schema(self) -> Dict[str, Any]:
        """Exports definition compatible with Model Context Protocol (MCP) tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters_schema,
            "required_scope": self.required_scope.value,
        }
