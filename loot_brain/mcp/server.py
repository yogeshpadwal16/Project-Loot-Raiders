"""
Model Context Protocol (MCP) Server implementation for tool discovery and safe execution.
"""

from typing import Any, Dict, List, Optional
from loot_brain.security.permissions import PrivilegeScope, SecurityBoundary
from loot_brain.tools.base_tool import BaseTool


class ToolNotFoundError(Exception):
    """Raised when an unregistered tool is invoked."""
    pass


class MCPServer:
    """
    Standardized MCP Tool Server handling tool registration, schema discovery,
    and RBAC-enforced tool invocation.
    """

    def __init__(self, security_boundary: Optional[SecurityBoundary] = None):
        self._tools: Dict[str, BaseTool] = {}
        self.security_boundary = security_boundary or SecurityBoundary(max_allowed_scope=PrivilegeScope.SAFE_WRITE)

    def register_tool(self, tool: BaseTool) -> None:
        """Registers a BaseTool instance."""
        self._tools[tool.name] = tool

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns JSON schema definitions of all registered tools."""
        return [tool.to_mcp_schema() for tool in self._tools.values()]

    def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        agent_id: str,
        agent_max_scope: Optional[PrivilegeScope] = None,
    ) -> Any:
        """
        Executes named tool after RBAC permission check through SecurityBoundary.
        """
        if name not in self._tools:
            raise ToolNotFoundError(f"MCP Tool '{name}' is not registered on this server.")

        tool = self._tools[name]
        return tool.run(
            agent_id=agent_id,
            security_boundary=self.security_boundary,
            agent_max_scope=agent_max_scope,
            **arguments,
        )
