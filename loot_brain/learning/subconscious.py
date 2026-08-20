"""
Subconscious Background Learning Engine & Safeguard Pipeline:
OBSERVE -> MEASURE -> ANALYZE -> IDENTIFY PATTERN -> HYPOTHESIZE -> EXPERIMENT -> EVALUATE -> PROPOSE -> TEST -> APPROVE -> DEPLOY -> MONITOR
"""

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from loot_brain.context.schemas import MemoryCategory, MemoryEntry, MemoryType
from loot_brain.memory.hygiene import MemoryHygieneManager
from loot_brain.memory.store import MemoryStore


class CandidateLesson(BaseModel):
    lesson_id: str
    pattern_summary: str
    observed_occurrences: int
    confidence: float
    status: str = "CANDIDATE"  # CANDIDATE, VALIDATED, REJECTED, PROPOSED_POLICY


class LearningPolicyCandidate(BaseModel):
    policy_id: str
    title: str
    description: str
    proposed_rule_change: Dict[str, Any]
    requires_human_approval: bool = True
    approved: bool = False
    created_at: float = Field(default_factory=time.time)


class SubconsciousLoop:
    """
    Background cognition engine that processes experiences, extracts candidate lessons,
    and proposes policy updates through a human-in-the-loop safeguard gate.
    """

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store
        self.hygiene_manager = MemoryHygieneManager(memory_store)
        self._policy_candidates: List[LearningPolicyCandidate] = []

    def run_subconscious_cycle(self) -> Dict[str, Any]:
        """
        Executes a background learning cycle:
        1. Run Memory Decay Sweep
        2. Run Pattern Consolidation
        3. Analyze Consolidated Patterns to synthesize Candidate Lessons
        4. Propose Policy Candidates requiring Human Approval for safety
        """
        decayed_count = self.hygiene_manager.run_decay_sweep()
        consolidated_count = self.hygiene_manager.consolidate_patterns()

        # Extract facts created from consolidation
        facts = self.memory_store.search_memories(memory_type=MemoryType.FACT, query="Consolidated Pattern")
        candidate_lessons: List[CandidateLesson] = []

        for idx, fact in enumerate(facts):
            lesson = CandidateLesson(
                lesson_id=f"lesson-{int(time.time())}-{idx}",
                pattern_summary=fact.title,
                observed_occurrences=5,
                confidence=fact.confidence,
                status="VALIDATED",
            )
            candidate_lessons.append(lesson)

            # Generate policy candidate if high confidence
            if fact.confidence >= 0.8:
                policy = LearningPolicyCandidate(
                    policy_id=f"pol-cand-{int(time.time())}-{idx}",
                    title=f"Auto-Proposed Policy from {fact.title}",
                    description=fact.content[:150],
                    proposed_rule_change={"suggested_action": "update_threshold", "source_lesson": lesson.lesson_id},
                    requires_human_approval=True,
                )
                self._policy_candidates.append(policy)

        return {
            "decayed_memories": decayed_count,
            "consolidated_patterns": consolidated_count,
            "candidate_lessons": [l.model_dump() for l in candidate_lessons],
            "proposed_policies_count": len(self._policy_candidates),
        }

    def list_proposed_policies(self) -> List[LearningPolicyCandidate]:
        """Lists policy candidates awaiting human review and signoff."""
        return [p for p in self._policy_candidates if not p.approved]

    def approve_policy_candidate(self, policy_id: str, approver_id: str) -> bool:
        """Applies explicit human signoff to deploy a policy candidate."""
        for policy in self._policy_candidates:
            if policy.policy_id == policy_id:
                policy.approved = True
                # Record System Decision memory
                mem = MemoryEntry(
                    memory_id=f"mem-policy-approved-{policy_id}",
                    category=MemoryCategory.SYSTEM,
                    memory_type=MemoryType.RULE,
                    title=f"Approved Policy: {policy.title}",
                    content=f"Human approver [{approver_id}] approved policy: {policy.description}",
                    confidence=1.0,
                    provenance=f"human_approval:{approver_id}",
                )
                self.memory_store.save_memory(mem)
                return True
        return False
