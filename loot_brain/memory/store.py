"""
Dual SQLite + Obsidian-Compatible Markdown Memory Store with Hybrid Search.
"""

import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional

from loot_brain.context.schemas import MemoryCategory, MemoryEntry, MemoryType


class MemoryStore:
    """
    Persistent Memory Store providing fast SQLite indexing and transparent
    Obsidian-compatible Markdown storage.
    """

    def __init__(self, db_path: str = "loot_brain_memory.db", md_base_dir: str = "loot_brain/memory/markdown_store"):
        self.db_path = db_path
        self.md_base_dir = Path(md_base_dir)
        self.md_base_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    scope TEXT NOT NULL,
                    agent_id TEXT,
                    platform TEXT,
                    provenance TEXT,
                    usefulness_score REAL NOT NULL,
                    last_used REAL NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_cat ON memories(category, archived)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type, archived)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_used ON memories(last_used)")
            conn.commit()

    def save_memory(self, entry: MemoryEntry) -> None:
        """Saves memory entry into SQLite and syncs Markdown representation to disk."""
        # 1. Save to SQLite
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memories (
                    memory_id, category, memory_type, title, content, confidence,
                    scope, agent_id, platform, provenance, usefulness_score,
                    last_used, created_at, updated_at, archived, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.memory_id,
                entry.category.value,
                entry.memory_type.value,
                entry.title,
                entry.content,
                entry.confidence,
                entry.scope,
                entry.agent_id,
                entry.platform,
                entry.provenance,
                entry.usefulness_score,
                entry.last_used,
                entry.created_at,
                entry.updated_at,
                1 if entry.archived else 0,
                json.dumps(entry.metadata),
            ))
            conn.commit()

        # 2. Sync to Obsidian Markdown file
        self._sync_to_markdown(entry)

    def _sync_to_markdown(self, entry: MemoryEntry) -> None:
        """Writes Obsidian-compatible Markdown file with YAML frontmatter."""
        target_dir = self.md_base_dir / ("archive" if entry.archived else entry.category.value.lower())
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{entry.memory_id}.md"

        yaml_frontmatter = (
            f"---\n"
            f"memory_id: \"{entry.memory_id}\"\n"
            f"category: \"{entry.category.value}\"\n"
            f"type: \"{entry.memory_type.value}\"\n"
            f"confidence: {entry.confidence}\n"
            f"scope: \"{entry.scope}\"\n"
            f"agent_id: \"{entry.agent_id or ''}\"\n"
            f"platform: \"{entry.platform or ''}\"\n"
            f"usefulness_score: {entry.usefulness_score}\n"
            f"created_at: {entry.created_at}\n"
            f"updated_at: {entry.updated_at}\n"
            f"archived: {str(entry.archived).lower()}\n"
            f"---\n\n"
        )
        md_content = f"{yaml_frontmatter}# {entry.title}\n\n{entry.content}\n"
        file_path.write_text(md_content, encoding="utf-8")

    def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM memories WHERE memory_id = ?", (memory_id,)).fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def search_memories(
        self,
        category: Optional[MemoryCategory] = None,
        memory_type: Optional[MemoryType] = None,
        query: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        sql = "SELECT * FROM memories WHERE 1=1"
        params: List[Any] = []

        if not include_archived:
            sql += " AND archived = 0"
        if category:
            sql += " AND category = ?"
            params.append(category.value)
        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type.value)
        if query:
            sql += " AND (title LIKE ? OR content LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])

        sql += " ORDER BY usefulness_score DESC, updated_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            memory_id=row["memory_id"],
            category=MemoryCategory(row["category"]),
            memory_type=MemoryType(row["memory_type"]),
            title=row["title"],
            content=row["content"],
            confidence=row["confidence"],
            scope=row["scope"],
            agent_id=row["agent_id"],
            platform=row["platform"],
            provenance=row["provenance"],
            usefulness_score=row["usefulness_score"],
            last_used=row["last_used"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            archived=bool(row["archived"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
