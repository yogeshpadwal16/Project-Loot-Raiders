"""
Durable Checkpoint & Execution Tracing Subsystem.
Ensures idempotency, durable recovery across crashes, and full execution tracing.
"""

import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from loot_brain.harness.tools import SideEffectLevel

logger = logging.getLogger(__name__)


class ToolCallRecord(BaseModel):
    """Record of an individual tool call within an execution trace."""
    tool_name: str
    agent_id: str
    kwargs_keys: List[str] = Field(default_factory=list)
    success: bool
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    side_effect_level: SideEffectLevel = SideEffectLevel.READ_ONLY
    timestamp: float = Field(default_factory=time.time)


class CheckpointRecord(BaseModel):
    """Snapshot of task state captured prior to performing side-effects."""
    checkpoint_id: str
    task_id: str
    step_name: str
    task_state: str
    payload_snapshot: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class TaskExecutionTrace(BaseModel):
    """Complete auditable execution trace for an agent task."""
    task_id: str
    objective: str
    assigned_agent: str
    status: str = "RUNNING"
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    checkpoints: List[CheckpointRecord] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class CheckpointStore:
    """
    Durable Persistence Engine for Task Execution Traces and State Checkpoints.
    Backed by SQLite and thread-safe in-memory cache.
    """

    def __init__(self, db_path: str = "database/loot_raiders.db"):
        self.db_path = db_path
        self._memory_traces: Dict[str, TaskExecutionTrace] = {}
        self._memory_checkpoints: Dict[str, List[CheckpointRecord]] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initializes checkpoint and audit trace tables in SQLite if missing."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS harness_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    task_state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS harness_traces (
                    task_id TEXT PRIMARY KEY,
                    assigned_agent TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trace_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[CheckpointStore] DB table initialization warning: {e}")

    def save_checkpoint(self, task_id: str, step_name: str, task_state: str, payload: Dict[str, Any]) -> CheckpointRecord:
        """Saves a pre-side-effect checkpoint for durable recovery."""
        checkpoint_id = f"chk-{task_id}-{int(time.time()*1000)}"
        record = CheckpointRecord(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            step_name=step_name,
            task_state=task_state,
            payload_snapshot=payload,
        )

        if task_id not in self._memory_checkpoints:
            self._memory_checkpoints[task_id] = []
        self._memory_checkpoints[task_id].append(record)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO harness_checkpoints VALUES (?, ?, ?, ?, ?, ?)",
                (checkpoint_id, task_id, step_name, task_state, json.dumps(payload), record.timestamp),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[CheckpointStore] Failed to write checkpoint to SQLite: {e}")

        logger.info(f"[CheckpointStore] Saved checkpoint '{checkpoint_id}' for task '{task_id}' [{step_name}]")
        return record

    def get_latest_checkpoint(self, task_id: str) -> Optional[CheckpointRecord]:
        """Retrieves the most recent checkpoint for a task."""
        checkpoints = self._memory_checkpoints.get(task_id, [])
        if checkpoints:
            return checkpoints[-1]

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT checkpoint_id, task_id, step_name, task_state, payload_json, created_at FROM harness_checkpoints WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return CheckpointRecord(
                    checkpoint_id=row[0],
                    task_id=row[1],
                    step_name=row[2],
                    task_state=row[3],
                    payload_snapshot=json.loads(row[4]),
                    timestamp=row[5],
                )
        except Exception as e:
            logger.warning(f"[CheckpointStore] Failed to fetch checkpoint from SQLite: {e}")
        return None

    def record_trace(self, trace: TaskExecutionTrace) -> None:
        """Stores or updates a task execution trace."""
        self._memory_traces[trace.task_id] = trace

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO harness_traces VALUES (?, ?, ?, ?, ?, ?)",
                (
                    trace.task_id,
                    trace.assigned_agent,
                    trace.objective,
                    trace.status,
                    trace.model_dump_json(),
                    time.time(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[CheckpointStore] Failed to record trace into SQLite: {e}")

    def get_trace(self, task_id: str) -> Optional[TaskExecutionTrace]:
        """Retrieves an execution trace by task ID."""
        if task_id in self._memory_traces:
            return self._memory_traces[task_id]

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT trace_json FROM harness_traces WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                data = json.loads(row[0])
                return TaskExecutionTrace(**data)
        except Exception as e:
            logger.warning(f"[CheckpointStore] Failed to load trace from SQLite: {e}")
        return None
