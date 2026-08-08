"""
Memory Hygiene Heuristics (Decay, Pattern Consolidation) and 2-Stage Progressive Retrieval.
"""

from collections import defaultdict
import time
from typing import Dict, List, Optional

from loot_brain.context.schemas import MemoryCategory, MemoryEntry, MemoryType
from loot_brain.memory.store import MemoryStore


class MemoryHygieneManager:
    """
    Automates Memory Decay Heuristics and Pattern Consolidation.
    """

    def __init__(self, store: MemoryStore):
        self.store = store

    def run_decay_sweep(self, max_idle_days: int = 30, min_confidence: float = 0.5) -> int:
        """
        Archives memories if unused for > max_idle_days or confidence < min_confidence.
        Protected Types: MemoryType.RULE and MemoryType.DECISION are never decayed automatically.
        """
        cutoff_time = time.time() - (max_idle_days * 86400)
        archived_count = 0

        # Fetch active memories
        active_memories = self.store.search_memories(include_archived=False, limit=1000)

        for mem in active_memories:
            # Protected rules/decisions cannot decay
            if mem.memory_type in (MemoryType.RULE, MemoryType.DECISION):
                continue

            should_archive = False
            if mem.last_used < cutoff_time:
                should_archive = True
            elif mem.confidence < min_confidence:
                should_archive = True

            if should_archive:
                mem.archived = True
                mem.updated_at = time.time()
                self.store.save_memory(mem)
                archived_count += 1

        return archived_count

    def consolidate_patterns(self, min_similar: int = 5) -> int:
        """
        Aggregates raw Experience/Observation memories sharing identical outcomes or root titles
        into a single consolidated Fact record, archiving individual raw items.
        """
        active_memories = self.store.search_memories(include_archived=False, limit=1000)
        grouped = defaultdict(list)

        for mem in active_memories:
            if mem.memory_type in (MemoryType.EXPERIENCE, MemoryType.OBSERVATION):
                key = (mem.category.value, mem.title.strip().lower())
                grouped[key].append(mem)

        consolidated_count = 0

        for (category_str, title_str), items in grouped.items():
            if len(items) >= min_similar:
                # Build consolidated memory
                consolidated_id = f"consolidated-pat-{int(time.time())}-{consolidated_count}"
                combined_content = "\n".join([f"- [{i.memory_id}]: {i.content}" for i in items])
                consolidated_mem = MemoryEntry(
                    memory_id=consolidated_id,
                    category=MemoryCategory(category_str),
                    memory_type=MemoryType.FACT,
                    title=f"Consolidated Pattern: {items[0].title}",
                    content=f"Aggregated from {len(items)} recurring observations:\n{combined_content}",
                    confidence=0.9,
                    provenance="subconscious_consolidation",
                    usefulness_score=1.5,
                )
                self.store.save_memory(consolidated_mem)

                # Archive raw items
                for raw_item in items:
                    raw_item.archived = True
                    raw_item.updated_at = time.time()
                    self.store.save_memory(raw_item)

                consolidated_count += 1

        return consolidated_count


class ProgressiveRetriever:
    """
    2-Stage Memory Retrieval System:
    Stage 1: Search -> Identify candidate IDs
    Stage 2: Expand -> Build full prompt context block
    """

    def __init__(self, store: MemoryStore):
        self.store = store

    def search_candidates(
        self,
        query: str,
        category: Optional[MemoryCategory] = None,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        """Stage 1: Light candidate identification."""
        memories = self.store.search_memories(category=category, query=query, limit=limit)
        return [
            {
                "memory_id": m.memory_id,
                "title": m.title,
                "category": m.category.value,
                "type": m.memory_type.value,
            }
            for m in memories
        ]

    def build_context_block(self, memory_ids: List[str]) -> str:
        """Stage 2: Expand candidates into full structured context for LLM prompt."""
        if not memory_ids:
            return ""

        context_lines = ["--- RELEVANT LOOT BRAIN MEMORY CONTEXT ---"]
        for mid in memory_ids:
            mem = self.store.get_memory(mid)
            if mem and not mem.archived:
                mem.last_used = time.time()
                self.store.save_memory(mem)
                context_lines.append(
                    f"[{mem.category.value} | {mem.memory_type.value}] {mem.title} (Confidence: {mem.confidence})\n"
                    f"{mem.content}\n"
                )
        context_lines.append("--- END MEMORY CONTEXT ---")
        return "\n".join(context_lines)
