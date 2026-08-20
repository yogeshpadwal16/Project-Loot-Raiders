"""
Unit tests for Loot Brain Phase 2 Memory Engine.
"""

from pathlib import Path
import shutil
import tempfile
import time
import unittest

from loot_brain.context.schemas import MemoryCategory, MemoryEntry, MemoryType
from loot_brain.memory.store import MemoryStore
from loot_brain.memory.hygiene import MemoryHygieneManager, ProgressiveRetriever


class TestLootBrainMemory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test_memory.db")
        self.md_dir = str(Path(self.temp_dir) / "md_store")
        self.store = MemoryStore(db_path=self.db_path, md_base_dir=self.md_dir)
        self.hygiene = MemoryHygieneManager(self.store)
        self.retriever = ProgressiveRetriever(self.store)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_retrieve_memory(self):
        mem = MemoryEntry(
            memory_id="mem-001",
            category=MemoryCategory.DEAL,
            memory_type=MemoryType.FACT,
            title="Amazon Price History",
            content="Historical minimum for iPhone 15 is 65000 INR",
            confidence=0.95,
        )
        self.store.save_memory(mem)

        retrieved = self.store.get_memory("mem-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Amazon Price History")
        self.assertEqual(retrieved.confidence, 0.95)

        # Check Obsidian MD file created
        md_file = Path(self.md_dir) / "deal" / "mem-001.md"
        self.assertTrue(md_file.exists())
        content = md_file.read_text(encoding="utf-8")
        self.assertIn("---", content)
        self.assertIn("Amazon Price History", content)

    def test_decay_sweep(self):
        # 1. Active high-confidence memory
        active_mem = MemoryEntry(
            memory_id="active-1",
            category=MemoryCategory.PLATFORM,
            memory_type=MemoryType.FACT,
            title="Selector rule",
            content="Amazon price selector is .a-price",
            confidence=0.9,
            last_used=time.time(),
        )
        # 2. Old low-confidence memory
        stale_mem = MemoryEntry(
            memory_id="stale-1",
            category=MemoryCategory.PLATFORM,
            memory_type=MemoryType.FACT,
            title="Stale rule",
            content="Deprecated selector",
            confidence=0.3,
            last_used=time.time() - (40 * 86400),
        )
        # 3. Protected rule memory (old but Rule type)
        protected_rule = MemoryEntry(
            memory_id="rule-1",
            category=MemoryCategory.SYSTEM,
            memory_type=MemoryType.RULE,
            title="Never post broken coupon",
            content="Must verify coupon before post",
            confidence=0.4,
            last_used=time.time() - (50 * 86400),
        )

        self.store.save_memory(active_mem)
        self.store.save_memory(stale_mem)
        self.store.save_memory(protected_rule)

        archived_count = self.hygiene.run_decay_sweep(max_idle_days=30, min_confidence=0.5)
        self.assertEqual(archived_count, 1)

        # Verify stale-1 is archived, active-1 and rule-1 are active
        self.assertTrue(self.store.get_memory("stale-1").archived)
        self.assertFalse(self.store.get_memory("active-1").archived)
        self.assertFalse(self.store.get_memory("rule-1").archived)

    def test_pattern_consolidation(self):
        # Create 5 similar experience observations
        for i in range(5):
            mem = MemoryEntry(
                memory_id=f"exp-{i}",
                category=MemoryCategory.TELEGRAM,
                memory_type=MemoryType.EXPERIENCE,
                title="Rate limit on post",
                content=f"Telegram flood wait triggered at attempt {i}",
                confidence=0.8,
            )
            self.store.save_memory(mem)

        consolidated_count = self.hygiene.consolidate_patterns(min_similar=5)
        self.assertEqual(consolidated_count, 1)

        # Verify raw experiences are archived
        for i in range(5):
            self.assertTrue(self.store.get_memory(f"exp-{i}").archived)

        # Verify consolidated pattern memory exists
        patterns = self.store.search_memories(category=MemoryCategory.TELEGRAM, memory_type=MemoryType.FACT)
        self.assertEqual(len(patterns), 1)
        self.assertIn("Consolidated Pattern", patterns[0].title)

    def test_progressive_retrieval(self):
        mem = MemoryEntry(
            memory_id="deal-mem",
            category=MemoryCategory.DEAL,
            memory_type=MemoryType.FACT,
            title="Flipkart Big Billion Days",
            content="Lowest discounts occur at midnight sale launch",
        )
        self.store.save_memory(mem)

        # Stage 1: Candidate identification
        candidates = self.retriever.search_candidates(query="Billion", category=MemoryCategory.DEAL)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["memory_id"], "deal-mem")

        # Stage 2: Context block building
        context_block = self.retriever.build_context_block([c["memory_id"] for c in candidates])
        self.assertIn("RELEVANT LOOT BRAIN MEMORY CONTEXT", context_block)
        self.assertIn("Flipkart Big Billion Days", context_block)


if __name__ == "__main__":
    unittest.main()
