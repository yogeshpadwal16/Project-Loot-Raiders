"""
Unit tests for Loot Brain Cloud Resilience & Recovery.
"""

from pathlib import Path
import shutil
import tempfile
import unittest

from loot_brain.memory.store import MemoryStore
from loot_brain.context.schemas import MemoryCategory, MemoryEntry, MemoryType


class TestLootBrainCloudResilience(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test_resilience.db")
        self.md_dir = str(Path(self.temp_dir) / "md_store")
        self.store = MemoryStore(db_path=self.db_path, md_base_dir=self.md_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_crash_rebuild_from_markdown(self):
        # 1. Save memory
        mem = MemoryEntry(
            memory_id="resilient-001",
            category=MemoryCategory.SYSTEM,
            memory_type=MemoryType.RULE,
            title="Production Guard Rule",
            content="Never post deals with discount under 20%",
        )
        self.store.save_memory(mem)

        # Verify Markdown file exists
        md_file = Path(self.md_dir) / "system" / "resilient-001.md"
        self.assertTrue(md_file.exists())

        # 2. Simulate total SQLite database destruction
        Path(self.db_path).unlink()

        # 3. Re-initialize MemoryStore (recreates SQLite tables)
        rebuilt_store = MemoryStore(db_path=self.db_path, md_base_dir=self.md_dir)

        # 4. Re-save memory from Markdown files (Simulated Markdown sync recovery)
        content = md_file.read_text(encoding="utf-8")
        self.assertIn("Production Guard Rule", content)

        recovered_mem = MemoryEntry(
            memory_id="resilient-001",
            category=MemoryCategory.SYSTEM,
            memory_type=MemoryType.RULE,
            title="Production Guard Rule",
            content="Never post deals with discount under 20%",
        )
        rebuilt_store.save_memory(recovered_mem)

        retrieved = rebuilt_store.get_memory("resilient-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Production Guard Rule")


if __name__ == "__main__":
    unittest.main()
