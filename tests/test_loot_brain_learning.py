"""
Unit tests for Loot Brain Phase 8 Learning Engine & Subconscious Loop.
"""

from pathlib import Path
import shutil
import tempfile
import unittest

from loot_brain.context.schemas import MemoryCategory, MemoryEntry, MemoryType
from loot_brain.memory.store import MemoryStore
from loot_brain.learning.subconscious import SubconsciousLoop


class TestLootBrainLearning(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test_memory.db")
        self.md_dir = str(Path(self.temp_dir) / "md_store")
        self.store = MemoryStore(db_path=self.db_path, md_base_dir=self.md_dir)
        self.subconscious = SubconsciousLoop(self.store)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_subconscious_learning_cycle(self):
        # 1. Insert 5 recurring experience records
        for i in range(5):
            mem = MemoryEntry(
                memory_id=f"exp-tg-{i}",
                category=MemoryCategory.TELEGRAM,
                memory_type=MemoryType.EXPERIENCE,
                title="Telegram rate limit at 10pm",
                content=f"Attempt {i} hit flood wait at 10pm peak",
                confidence=0.85,
            )
            self.store.save_memory(mem)

        # 2. Run subconscious cycle
        res = self.subconscious.run_subconscious_cycle()

        self.assertEqual(res["consolidated_patterns"], 1)
        self.assertEqual(res["proposed_policies_count"], 1)

        # 3. Check proposed policies requiring human approval
        proposed = self.subconscious.list_proposed_policies()
        self.assertEqual(len(proposed), 1)
        self.assertTrue(proposed[0].requires_human_approval)
        self.assertFalse(proposed[0].approved)

        # 4. Apply human signoff
        policy_id = proposed[0].policy_id
        approved = self.subconscious.approve_policy_candidate(policy_id, approver_id="admin_yogesh")
        self.assertTrue(approved)

        # 5. Verify rule memory saved
        rule_mem = self.store.get_memory(f"mem-policy-approved-{policy_id}")
        self.assertIsNotNone(rule_mem)
        self.assertEqual(rule_mem.memory_type, MemoryType.RULE)


if __name__ == "__main__":
    unittest.main()
