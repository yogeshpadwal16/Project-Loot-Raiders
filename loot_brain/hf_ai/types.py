"""
Data types and Pydantic schemas for Hugging Face AI signals.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RerankCandidate(BaseModel):
    """Candidate deal object evaluated by second-stage reranker."""
    candidate_id: str
    candidate_title: str
    candidate_price: float = 0.0
    initial_score: float = 0.0


class RerankResult(BaseModel):
    """Structured output produced by 2nd-stage Semantic Reranker."""
    candidate_id: str
    relevance_score: float = 0.0            # 0.0 to 1.0 cross-encoder similarity score
    same_product_probability: float = 0.0   # Exact product identity confidence
    same_variant_probability: float = 0.0   # Variant match (color, storage, capacity)
    accessory_probability: float = 0.0      # Probability candidate is an accessory
    confidence: float = 0.0
    latency_ms: float = 0.0


class ClassificationResult(BaseModel):
    """Structured output produced by Product & Deal Classifier."""
    category: str = "general"
    category_confidence: float = 0.0
    brand: str = "unknown"
    brand_confidence: float = 0.0
    is_accessory: bool = False
    accessory_probability: float = 0.0
    deal_quality_probability: float = 0.50
    latency_ms: float = 0.0


class LocalAISignals(BaseModel):
    """Structured signals exported by Hugging Face AI Subsystem to main pipeline."""
    model_available: bool = False
    shadow_mode: bool = True
    rerank_result: Optional[RerankResult] = None
    classification_result: Optional[ClassificationResult] = None
    total_latency_ms: float = 0.0
    model_version: str = "v1.0.0-shadow"
