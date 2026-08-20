"""
Standardized Loot Brain Tools for Deal Searching, Price Retrieval, Telegram Publishing, and Policy Management.
"""

from typing import Any, Dict, List
from loot_brain.security.permissions import PrivilegeScope
from loot_brain.tools.base_tool import BaseTool


class SearchDealsTool(BaseTool):
    """Tool to search the deal database or active catalog."""
    def __init__(self):
        super().__init__(
            name="search_deals",
            description="Search stored e-commerce deal catalog by query, merchant, or price",
            required_scope=PrivilegeScope.READ_ONLY,
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword (e.g., iPhone, Sony)"},
                "merchant": {"type": "string", "description": "Filter by merchant (Amazon, Flipkart)"},
                "max_price": {"type": "number", "description": "Maximum price in INR"},
            },
            "required": ["query"],
        }

    def _run(self, query: str, merchant: str = "All", max_price: float = 1000000.0) -> List[Dict[str, Any]]:
        return [
            {
                "deal_id": "search-deal-1",
                "title": f"Match for '{query}' on {merchant}",
                "price": min(max_price, 15000.0),
                "merchant": merchant,
            }
        ]


class FetchPriceTool(BaseTool):
    """Tool to fetch current live price of a product URL."""
    def __init__(self):
        super().__init__(
            name="fetch_price",
            description="Fetch live product price and stock status from merchant URL",
            required_scope=PrivilegeScope.READ_ONLY,
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Product target URL"},
            },
            "required": ["url"],
        }

    def _run(self, url: str) -> Dict[str, Any]:
        return {
            "url": url,
            "original_price": 25000.0,
            "deal_price": 17500.0,
            "discount_percentage": 30.0,
            "in_stock": True,
        }


class PublishTelegramTool(BaseTool):
    """Tool to post verified deal alert to Telegram channel."""
    def __init__(self):
        super().__init__(
            name="publish_telegram",
            description="Publish verified deal post to syndication Telegram channel",
            required_scope=PrivilegeScope.SAFE_WRITE,
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text_content": {"type": "string", "description": "HTML formatted text copy"},
                "channel_id": {"type": "string", "description": "Target Telegram channel ID"},
            },
            "required": ["text_content"],
        }

    def _run(self, text_content: str, channel_id: str = "@lootraiders") -> Dict[str, Any]:
        return {
            "published": True,
            "message_id": 99102,
            "channel_id": channel_id,
            "timestamp": 1718000000,
        }


class UpdatePolicyTool(BaseTool):
    """Tool to modify internal deal intelligence threshold policies."""
    def __init__(self):
        super().__init__(
            name="update_policy",
            description="Update deal score threshold rules and scoring weights",
            required_scope=PrivilegeScope.SENSITIVE_WRITE,
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "min_discount_pct": {"type": "number"},
                "reasoning_mode": {"type": "string"},
            },
            "required": ["min_discount_pct"],
        }

    def _run(self, min_discount_pct: float, reasoning_mode: str = "strict") -> Dict[str, Any]:
        return {
            "updated": True,
            "min_discount_pct": min_discount_pct,
            "reasoning_mode": reasoning_mode,
        }


class DeleteProductionDataTool(BaseTool):
    """Admin tool to purge or drop database tables (Blocked by default)."""
    def __init__(self):
        super().__init__(
            name="delete_production_data",
            description="Purge or truncate production database tables",
            required_scope=PrivilegeScope.ADMIN,
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "table_name": {"type": "string"},
            },
            "required": ["table_name"],
        }

    def _run(self, table_name: str) -> Dict[str, Any]:
        return {"purged": True, "table_name": table_name}
