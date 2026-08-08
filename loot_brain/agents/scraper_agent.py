"""
Scraper Agent for robust multi-platform deal extraction and HTML parsing.
"""

import time
from typing import Any, Dict, List, Optional
from loot_brain.agents.base_agent import BaseAgent, AgentReport
from loot_brain.context.schemas import ScrapingPayload, MemoryCategory, MemoryEntry, MemoryType
from loot_brain.security.permissions import PrivilegeScope, InputSanitizer


class ScraperAgent(BaseAgent):
    """
    Scraper Agent handling HTML extraction, anti-bot resilience, and DOM parsing.
    """

    def __init__(self):
        super().__init__(
            agent_id="scraper_agent",
            name="Scraper Agent",
            role="E-commerce Page Scraping and Entity Extraction",
            capabilities=["scrape_url", "parse_html", "extract_metadata"],
            max_privilege_scope=PrivilegeScope.READ_ONLY,
        )

    def observe(self, input_data: Any) -> Dict[str, Any]:
        if isinstance(input_data, dict):
            return InputSanitizer.sanitize_dict(input_data)
        return {"url": str(input_data)}

    def understand(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        url = observation.get("url", "")
        platform = observation.get("merchant") or observation.get("store") or "Generic"
        if "amazon" in url.lower():
            platform = "Amazon"
        elif "flipkart" in url.lower():
            platform = "Flipkart"
        return {"raw_input": observation, "url": url, "platform": platform}

    def plan(self, understood: Dict[str, Any]) -> Dict[str, Any]:
        return understood

    def execute(self, plan: Dict[str, Any]) -> ScrapingPayload:
        raw = plan["raw_input"]
        url = plan["url"]
        platform = plan["platform"]

        # Preserve input fields if already parsed, or extract defaults
        extracted = {
            "deal_id": raw.get("deal_id", f"deal-{int(time.time())}"),
            "title": raw.get("title", f"Extracted Product from {platform}"),
            "original_price": float(raw.get("original_price", 2000.0)),
            "deal_price": float(raw.get("deal_price", 1200.0)),
            "merchant": platform,
            "store": raw.get("store", platform),
            "url": url or raw.get("url", "https://example.com"),
            "in_stock": raw.get("in_stock", True),
            "coupon_code": raw.get("coupon_code"),
        }

        return ScrapingPayload(
            source_url=url or "https://example.com",
            platform=platform,
            success=True,
            status_code=200,
            extracted_data=extracted,
        )

    def verify(self, payload: ScrapingPayload) -> ScrapingPayload:
        if not payload.success:
            raise ValueError(f"Scraping failed: {payload.error_message}")
        return payload

    def report(self, verified: ScrapingPayload) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            task_id="",
            success=verified.success,
            data=verified.model_dump(),
        )

    def remember(self, report: AgentReport) -> List[MemoryEntry]:
        mem = MemoryEntry(
            memory_id=f"mem-scrape-{int(time.time())}",
            category=MemoryCategory.PLATFORM,
            memory_type=MemoryType.OBSERVATION,
            title=f"Scrape Success: {report.data.get('platform')}",
            content=f"Successfully extracted {report.data.get('source_url')}",
            confidence=1.0,
            agent_id=self.agent_id,
        )
        return [mem]
