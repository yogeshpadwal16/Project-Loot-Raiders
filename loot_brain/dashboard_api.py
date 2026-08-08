"""
FastAPI Routes for AI Brain Control Center and Dashboard PWA Integration.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from loot_brain.agents.registry import AgentRegistry
from loot_brain.learning.subconscious import SubconsciousLoop
from loot_brain.memory.store import MemoryStore
from loot_brain.orchestrator.engine import LootBrainOrchestrator

router = APIRouter(prefix="/api/v1/brain", tags=["AI Brain Control Center"])


class ProcessDealRequest(BaseModel):
    title: str
    original_price: float
    deal_price: float
    merchant: str = "Amazon"
    url: str
    in_stock: bool = True
    coupon_code: Optional[str] = None


class ApprovePolicyRequest(BaseModel):
    approver_id: str = "admin"


def get_brain_components():
    """Dependency injection helper for Loot Brain singleton components."""
    # Injected at app startup
    from web.server import brain_store, brain_registry, brain_orchestrator, brain_subconscious
    return brain_store, brain_registry, brain_orchestrator, brain_subconscious


@router.get("/status")
def get_brain_status():
    """Returns status of Loot Brain, registered agents, and memory statistics."""
    try:
        store, registry, orchestrator, subconscious = get_brain_components()
        agents = registry.list_agents()
        active_memories = store.search_memories(include_archived=False, limit=1000)
        archived_memories = store.search_memories(include_archived=True, limit=1000)

        return {
            "status": "ONLINE",
            "version": "1.0.0",
            "registered_agents_count": len(agents),
            "agents": agents,
            "active_memories_count": len(active_memories),
            "archived_memories_count": len(archived_memories) - len(active_memories),
            "pending_policy_proposals_count": len(subconscious.list_proposed_policies()),
        }
    except Exception as e:
        return {
            "status": "STANDALONE",
            "version": "1.0.0",
            "message": f"Brain running in standalone mode: {e}",
        }


@router.get("/memories")
def search_brain_memories(query: Optional[str] = None, category: Optional[str] = None, limit: int = 50):
    """Searches Loot Brain dual memory store."""
    try:
        store, _, _, _ = get_brain_components()
        memories = store.search_memories(query=query, limit=limit)
        return [m.model_dump() for m in memories]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning/policies")
def list_proposed_policies():
    """Lists AI Brain self-improvement policies awaiting human approval."""
    try:
        _, _, _, subconscious = get_brain_components()
        policies = subconscious.list_proposed_policies()
        return [p.model_dump() for p in policies]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learning/policies/{policy_id}/approve")
def approve_proposed_policy(policy_id: str, req: ApprovePolicyRequest):
    """Applies human signoff to approve an AI self-improvement policy."""
    try:
        _, _, _, subconscious = get_brain_components()
        success = subconscious.approve_policy_candidate(policy_id, approver_id=req.approver_id)
        if not success:
            raise HTTPException(status_code=404, detail="Policy candidate not found")
        return {"approved": True, "policy_id": policy_id, "approver_id": req.approver_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipeline/process")
def process_deal_pipeline(req: ProcessDealRequest):
    """Submits a raw deal to the autonomous Loot Brain pipeline."""
    try:
        _, _, orchestrator, _ = get_brain_components()
        task_id = f"api-task-{req.url.split('/')[-1] or 'deal'}"
        result = orchestrator.process_deal_pipeline(task_id, req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
