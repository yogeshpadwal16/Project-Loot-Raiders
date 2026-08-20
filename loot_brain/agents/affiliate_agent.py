"""
Affiliate Link Agent handling non-destructive tag insertion and provider routing.
"""

import time
from typing import Any, Dict, List, Optional
from loot_brain.agents.base_agent import BaseAgent, AgentReport
from loot_brain.context.schemas import AffiliateMeta, MemoryCategory, MemoryEntry, MemoryType
from loot_brain.security.permissions import PrivilegeScope


class AffiliateAgent(BaseAgent):
    """
    Affiliate Agent converting direct merchant links into tracking links without exposing secrets.
    """

    def __init__(self, amazon_tag: str = "lootraiders-21", flipkart_tag: str = "lootraiders"):
        super().__init__(
            agent_id="affiliate_agent",
            name="Affiliate Agent",
            role="Affiliate Tagging and Link Conversion",
            capabilities=["convert_link", "validate_affiliate"],
            max_privilege_scope=PrivilegeScope.SAFE_WRITE,
        )
        self.amazon_tag = amazon_tag
        self.flipkart_tag = flipkart_tag

    def observe(self, input_data: Any) -> Dict[str, Any]:
        url = str(input_data) if isinstance(input_data, str) else input_data.get("url", "")
        return {"original_url": url}

    def understand(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        url = observation["original_url"]
        provider = "Generic"
        tag = "default"

        if "amazon" in url.lower():
            provider = "Amazon"
            tag = self.amazon_tag
        elif "flipkart" in url.lower():
            provider = "Flipkart"
            tag = self.flipkart_tag

        return {"original_url": url, "provider": provider, "tag": tag}

    def plan(self, understood: Dict[str, Any]) -> Dict[str, Any]:
        return understood

    def execute(self, plan: Dict[str, Any]) -> AffiliateMeta:
        orig = plan["original_url"]
        provider = plan["provider"]
        tag = plan["tag"]

        converted = orig
        if provider == "Amazon":
            delim = "&" if "?" in orig else "?"
            converted = f"{orig}{delim}tag={tag}"
        elif provider == "Flipkart":
            delim = "&" if "?" in orig else "?"
            converted = f"{orig}{delim}affid={tag}"

        return AffiliateMeta(
            original_url=orig,
            converted_url=converted,
            provider=provider,
            tag_used=tag,
            success=True,
        )

    def verify(self, payload: AffiliateMeta) -> AffiliateMeta:
        if not payload.success:
            raise ValueError("Affiliate link conversion failed")
        return payload

    def report(self, verified: AffiliateMeta) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            task_id="",
            success=verified.success,
            data=verified.model_dump(),
        )

    def remember(self, report: AgentReport) -> List[MemoryEntry]:
        mem = MemoryEntry(
            memory_id=f"mem-aff-{int(time.time())}",
            category=MemoryCategory.AFFILIATE,
            memory_type=MemoryType.FACT,
            title=f"Affiliate Converted: {report.data.get('provider')}",
            content=f"Converted {report.data.get('original_url')} using tag {report.data.get('tag_used')}",
            confidence=1.0,
            agent_id=self.agent_id,
        )
        return [mem]
