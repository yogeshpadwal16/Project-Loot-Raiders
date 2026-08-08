"""
Unit tests for Loot Brain Phase 5 Tool & MCP Layer.
"""

import unittest

from loot_brain.security.permissions import PrivilegeScope, SecurityBoundary, SecurityViolationError
from loot_brain.tools.catalog_tools import (
    SearchDealsTool,
    FetchPriceTool,
    PublishTelegramTool,
    UpdatePolicyTool,
    DeleteProductionDataTool,
)
from loot_brain.mcp.server import MCPServer, ToolNotFoundError


class TestLootBrainMCPTools(unittest.TestCase):

    def setUp(self):
        self.boundary = SecurityBoundary(max_allowed_scope=PrivilegeScope.SAFE_WRITE)
        self.mcp_server = MCPServer(security_boundary=self.boundary)

        self.mcp_server.register_tool(SearchDealsTool())
        self.mcp_server.register_tool(FetchPriceTool())
        self.mcp_server.register_tool(PublishTelegramTool())
        self.mcp_server.register_tool(UpdatePolicyTool())
        self.mcp_server.register_tool(DeleteProductionDataTool())

    def test_mcp_list_tools(self):
        tools = self.mcp_server.list_tools()
        self.assertEqual(len(tools), 5)
        names = [t["name"] for t in tools]
        self.assertIn("search_deals", names)
        self.assertIn("publish_telegram", names)
        self.assertIn("delete_production_data", names)

    def test_mcp_call_read_only_tool(self):
        res = self.mcp_server.call_tool(
            name="search_deals",
            arguments={"query": "laptop", "merchant": "Amazon"},
            agent_id="test_agent",
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["merchant"], "Amazon")

    def test_mcp_call_safe_write_tool(self):
        res = self.mcp_server.call_tool(
            name="publish_telegram",
            arguments={"text_content": "🔥 <b>Great Deal!</b>"},
            agent_id="telegram_agent",
        )
        self.assertTrue(res["published"])
        self.assertEqual(res["message_id"], 99102)

    def test_mcp_call_admin_tool_blocked(self):
        # Default server boundary max_allowed_scope is SAFE_WRITE -> ADMIN is blocked
        with self.assertRaises(SecurityViolationError):
            self.mcp_server.call_tool(
                name="delete_production_data",
                arguments={"table_name": "deals"},
                agent_id="unauthorized_agent",
            )

    def test_mcp_unregistered_tool(self):
        with self.assertRaises(ToolNotFoundError):
            self.mcp_server.call_tool(
                name="non_existent_tool",
                arguments={},
                agent_id="test_agent",
            )


if __name__ == "__main__":
    unittest.main()
