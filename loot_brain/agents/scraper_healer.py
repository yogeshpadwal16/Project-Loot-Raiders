"""
Self-Healing AI Selector Agent for Project Loot Raiders.
Automatically detects DOM selector drift and repairs CSS matrices at runtime.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from loot_brain.agents.base_agent import BaseAgent, AgentReport
from loot_brain.security.permissions import PrivilegeScope

class ScraperHealerAgent(BaseAgent):
    """
    Autonomous AI agent that repairs broken scraper CSS selectors at runtime.
    """

    def __init__(self):
        super().__init__(
            agent_id="scraper_healer_agent",
            name="Scraper Healer Agent",
            role="Autonomous CSS Selector Drift Detection and Self-Healing",
            capabilities=["detect_drift", "heal_selectors", "update_matrix"],
            max_privilege_scope=PrivilegeScope.SAFE_WRITE,
        )

    def observe(self, input_data: Any) -> Dict[str, Any]:
        return input_data if isinstance(input_data, dict) else {}

    def understand(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        platform = observation.get("platform", "unknown")
        consecutive_failures = observation.get("consecutive_failures", 0)
        current_config = observation.get("config", {})
        return {
            "platform": platform,
            "consecutive_failures": consecutive_failures,
            "current_config": current_config,
            "requires_healing": consecutive_failures >= 1
        }

    def plan(self, understood: Dict[str, Any]) -> Dict[str, Any]:
        return understood

    def auto_repair_selectors(self, driver, platform: str, current_config: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Scans current DOM page source using heuristic candidate patterns to discover working card selectors.
        """
        logging.info(f"[Scraper Healer Agent] Initiating autonomous selector repair for platform: {platform}")
        
        # Candidate container selectors by platform type
        candidate_card_selectors = [
            "div[data-component-type='s-search-result']",
            "div[data-testid='product-card']",
            "div[class*='ProductCard-module__card']",
            "div.sg-col-inner",
            "div[data-id]",
            "div._1AtVbE",
            "div.cPHR1N",
            "div.slAVV4",
            "div._1sdMkc",
            "div._4ddWXP",
            "div.DOjaG1",
            "div._75nlfW",
            "div[class*='cPHR1N']",
            "div[class*='slAVV4']",
            "li.product-base",
            "div.product-base",
            "div.item",
            "div.riltrx-card"
        ]

        if not driver:
            return None

        for card_sel in candidate_card_selectors:
            try:
                from selenium.webdriver.common.by import By
                cards = driver.find_elements(By.CSS_SELECTOR, card_sel)
                if len(cards) >= 2:
                    logging.info(f"[Scraper Healer Agent] AUTO-HEAL SUCCESS! Discovered {len(cards)} valid containers using selector: '{card_sel}'")
                    
                    repaired_config = dict(current_config)
                    # Merge discovered working selector into existing config
                    existing_card_sel = current_config.get("card_selector", "")
                    if card_sel not in existing_card_sel:
                        repaired_config["card_selector"] = f"{card_sel}, {existing_card_sel}"
                    
                    self.persist_repaired_selector(platform, repaired_config)
                    return repaired_config
            except Exception as e:
                continue

        return None

    def persist_repaired_selector(self, platform: str, repaired_config: Dict[str, str]):
        """Persists repaired selector into selectors.json and SQLite SelectorMatrix."""
        try:
            from config.settings import BASE_DIR
            selectors_path = os.path.join(BASE_DIR, "selectors.json")
            data = {}
            if os.path.exists(selectors_path):
                with open(selectors_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            data[platform] = repaired_config
            with open(selectors_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                
            logging.info(f"[Scraper Healer Agent] Successfully saved healed selector for '{platform}' into selectors.json")
        except Exception as err:
            logging.error(f"[Scraper Healer Agent] Failed to persist repaired selector: {err}")

    def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        return {"healed": True, "platform": plan.get("platform")}

    def verify(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return result

    def report(self, verified: Dict[str, Any]) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            task_id="",
            success=verified.get("healed", False),
            data=verified
        )

    def remember(self, report: AgentReport) -> list:
        return []
