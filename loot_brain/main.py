"""
Loot Brain Main Entrypoint for Autonomous Production Operation.
"""

import logging
import sys
import time
from typing import Dict, Any

from loot_brain.agents.registry import AgentRegistry
from loot_brain.agents.deal_intelligence import DealIntelligenceAgent
from loot_brain.agents.scraper_agent import ScraperAgent
from loot_brain.agents.affiliate_agent import AffiliateAgent
from loot_brain.agents.telegram_agent import TelegramAgent
from loot_brain.learning.subconscious import SubconsciousLoop
from loot_brain.memory.store import MemoryStore
from loot_brain.orchestrator.engine import LootBrainOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] LootBrain: %(message)s")
logger = logging.getLogger("LootBrainMain")


def boot_loot_brain():
    """Initializes Loot Brain core services."""
    logger.info("Initializing Loot Brain Persistent AI Engine v1.0.0...")

    store = MemoryStore()
    registry = AgentRegistry()

    # Register Autonomous Agents
    registry.register(DealIntelligenceAgent(min_discount_threshold=20.0))
    registry.register(ScraperAgent())
    registry.register(AffiliateAgent())
    registry.register(TelegramAgent())

    orchestrator = LootBrainOrchestrator(registry=registry, memory_store=store)
    subconscious = SubconsciousLoop(memory_store=store)

    logger.info(f"Loot Brain initialized with {len(registry.list_agents())} registered agents.")
    return store, registry, orchestrator, subconscious


def run_autonomous_loop(interval_seconds: int = 60):
    """Main autonomous operational loop."""
    store, registry, orchestrator, subconscious = boot_loot_brain()

    logger.info(f"Starting Loot Brain Autonomous Operation Loop (Tick: {interval_seconds}s)...")

    try:
        cycle_count = 0
        while True:
            cycle_count += 1
            logger.info(f"=== Autonomous Cycle #{cycle_count} ===")

            # 1. Run Subconscious Learning & Memory Hygiene Sweep
            learning_result = subconscious.run_subconscious_cycle()
            logger.info(f"Subconscious Sweep: Decayed={learning_result['decayed_memories']}, "
                        f"Consolidated={learning_result['consolidated_patterns']}, "
                        f"Proposed Policies={learning_result['proposed_policies_count']}")

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        logger.info("Loot Brain Autonomous Loop stopped gracefully by operator.")
    except Exception as e:
        logger.critical(f"Loot Brain Autonomous Loop crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_autonomous_loop(interval_seconds=30)
