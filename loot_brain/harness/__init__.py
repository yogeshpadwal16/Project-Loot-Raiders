"""
Loot Raiders Agent Harness Package.
Provides production-grade agent orchestration, tool safety contracts, durable checkpoints,
execution tracing, failure recovery, cost governance, human approval gates, and shadow mode execution.
"""

from loot_brain.harness.tools import ToolRegistry, SideEffectLevel, ToolDefinition
from loot_brain.harness.checkpoints import CheckpointStore, TaskExecutionTrace
from loot_brain.harness.recovery import FailureClassifier, FailureType, RecoveryEngine
from loot_brain.harness.governance import CostTracker, LoopProtector
from loot_brain.harness.approval import ApprovalGate
from loot_brain.harness.shadow import ShadowRunner
from loot_brain.harness.evaluator import AgentEvaluator

__all__ = [
    "ToolRegistry",
    "SideEffectLevel",
    "ToolDefinition",
    "CheckpointStore",
    "TaskExecutionTrace",
    "FailureClassifier",
    "FailureType",
    "RecoveryEngine",
    "CostTracker",
    "LoopProtector",
    "ApprovalGate",
    "ShadowRunner",
    "AgentEvaluator",
]
