"""
Central Loot Brain Orchestrator State Machine Engine.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from loot_brain.agents.registry import AgentRegistry
from loot_brain.context.schemas import DealPayload, TelegramCopy
from loot_brain.memory.store import MemoryStore
from loot_brain.orchestrator.states import TaskContext, TaskState, InvalidStateTransitionError
from loot_brain.security.permissions import SecurityBoundary, PrivilegeScope

logger = logging.getLogger(__name__)


class PipelineExecutionError(Exception):
    """Raised when an unrecoverable failure occurs during task pipeline execution."""
    pass


class LootBrainOrchestrator:
    """
    Central Task Engine orchestrating task lifecycle state machine transitions
    and multi-agent workflows.
    """

    def __init__(self, registry: AgentRegistry, memory_store: MemoryStore):
        self.registry = registry
        self.memory_store = memory_store
        self.security_boundary = SecurityBoundary(max_allowed_scope=PrivilegeScope.SAFE_WRITE)

    def process_deal_pipeline(self, task_id: str, raw_deal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full End-to-End Deal Syndication Pipeline:
        1. Scrape / Validate Raw Data (ScraperAgent)
        2. Deal Intelligence Scoring & Safety Verification (DealIntelligenceAgent)
        3. Convert Affiliate Link (AffiliateAgent)
        4. Prepare Telegram Copy & Inline Buttons (TelegramAgent)
        5. Store Experience & Decision Memories (MemoryStore)
        """
        task = TaskContext(task_id=task_id, task_type="deal_pipeline", payload=raw_deal_data)

        try:
            # 1. PENDING -> PLANNING
            task.transition_to(TaskState.PLANNING, reason="Initializing multi-agent pipeline plan")

            # 2. PLANNING -> RUNNING
            task.transition_to(TaskState.RUNNING, reason="Starting pipeline execution")

            # Step A: Scraping / Extractor Agent
            scrape_report = self.registry.dispatch("scraper_agent", f"{task_id}-scrape", raw_deal_data)
            if not scrape_report.success:
                raise PipelineExecutionError(f"ScraperAgent failed: {scrape_report.errors}")
            scraped_data = scrape_report.data.get("extracted_data", raw_deal_data)

            # Step B: Deal Intelligence Agent
            deal_report = self.registry.dispatch("deal_intelligence_agent", f"{task_id}-intel", scraped_data)
            deal_payload = deal_report.data

            if deal_payload.get("recommendation") == "REJECT":
                # Save decision memory and transition to COMPLETED (filtered deal)
                task.transition_to(TaskState.REVIEW, reason="Deal rejected by hard safety rules")
                task.transition_to(TaskState.VERIFIED, reason="Rejection verified")
                task.transition_to(TaskState.COMPLETED, reason="Pipeline complete: Deal rejected")

                # Store memories
                for mem in deal_report.memories_created:
                    self.memory_store.save_memory(mem)

                return {
                    "status": "REJECTED",
                    "reason": deal_payload.get("reasons"),
                    "task_id": task_id,
                }

            # Step C: Affiliate Link Conversion Agent
            aff_report = self.registry.dispatch("affiliate_agent", f"{task_id}-aff", deal_payload)
            deal_payload["affiliate_url"] = aff_report.data.get("converted_url", deal_payload.get("url"))

            # Step D: Telegram Copy Generator Agent
            tg_report = self.registry.dispatch("telegram_agent", f"{task_id}-tg", deal_payload)

            # 3. RUNNING -> REVIEW
            task.transition_to(TaskState.REVIEW, reason="All agents produced output, entering review stage")

            # 4. REVIEW -> VERIFIED
            task.transition_to(TaskState.VERIFIED, reason="Outputs verified against publishing policies")

            # Save memories into MemoryStore
            for report in (scrape_report, deal_report, aff_report, tg_report):
                for mem in report.memories_created:
                    self.memory_store.save_memory(mem)

            # 5. VERIFIED -> COMPLETED
            task.transition_to(TaskState.COMPLETED, reason="Deal pipeline completed successfully")

            return {
                "status": "APPROVED",
                "task_id": task_id,
                "deal_payload": deal_payload,
                "telegram_copy": tg_report.data,
                "history": [h["to_state"] for h in task.history],
            }

        except Exception as e:
            logger.error(f"Pipeline error for task '{task_id}': {e}")
            if task.current_state in (TaskState.RUNNING, TaskState.PLANNING, TaskState.REVIEW):
                task.transition_to(TaskState.FAILED, reason=str(e))
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.transition_to(TaskState.RETRYING, reason="Retrying failed pipeline step")
            return {
                "status": "FAILED",
                "task_id": task_id,
                "error": str(e),
                "current_state": task.current_state.value,
            }
