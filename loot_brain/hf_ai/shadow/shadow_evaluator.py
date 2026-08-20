"""
Non-Binding Shadow Mode Evaluation Harness for Local Hugging Face AI.
Executes reranking and classification predictions alongside production system decisions,
recording disagreement metrics and latency signals without altering production outcomes.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from loot_brain.hf_ai.config import hf_ai_config
from loot_brain.hf_ai.reranker.semantic_reranker import SemanticReranker
from loot_brain.hf_ai.classifier.deal_classifier import DealClassifier
from loot_brain.hf_ai.types import LocalAISignals, RerankCandidate

logger = logging.getLogger(__name__)


class ShadowDisagreementRecord(BaseModel):
    """Record of disagreement between production decision and HF AI prediction."""
    task_id: str
    title: str
    production_decision: str
    ai_predicted_decision: str
    disagreement_type: str
    confidence: float = 0.0
    timestamp: float = Field(default_factory=time.time)


class HFShadowEvaluator:
    """
    Shadow Mode Evaluator running local HF AI signals in parallel with production pipeline.
    """

    def __init__(self):
        self.reranker = SemanticReranker()
        self.classifier = DealClassifier()
        self._disagreements: List[ShadowDisagreementRecord] = []

    def evaluate_shadow_signals(
        self,
        task_id: str,
        title: str,
        price: float = 0.0,
        mrp: float = 0.0,
        platform: str = "Amazon",
        candidates: Optional[List[RerankCandidate]] = None,
        production_decision: str = "APPROVE",
    ) -> LocalAISignals:
        """
        Computes shadow AI signals and evaluates agreement with production decision.
        """
        start_time = time.time()

        # 1. Run Deal Classifier
        class_res = self.classifier.classify_deal(title=title, price=price, mrp=mrp, platform=platform)

        # 2. Run Semantic Reranker if candidates present
        rerank_res = None
        if candidates:
            rerank_list = self.reranker.rerank_candidates(query_title=title, candidates=candidates, query_price=price)
            if rerank_list:
                rerank_res = rerank_list[0]

        total_latency = (time.time() - start_time) * 1000

        # Predict shadow decision: APPROVE if quality >= 0.50 and not accessory mismatch
        ai_pred_decision = "APPROVE" if (class_res.deal_quality_probability >= 0.40 and not class_res.is_accessory) else "REJECT"

        # Record disagreement if present
        if ai_pred_decision != production_decision:
            record = ShadowDisagreementRecord(
                task_id=task_id,
                title=title,
                production_decision=production_decision,
                ai_predicted_decision=ai_pred_decision,
                disagreement_type="DECISION_MISMATCH",
                confidence=class_res.deal_quality_probability,
            )
            self._disagreements.append(record)
            logger.info(f"[HFShadowEvaluator] Disagreement on Task '{task_id}': Production={production_decision} vs AI={ai_pred_decision} (Title: '{title[:30]}')")

        return LocalAISignals(
            model_available=True,
            shadow_mode=hf_ai_config.LOCAL_AI_SHADOW_MODE,
            rerank_result=rerank_res,
            classification_result=class_res,
            total_latency_ms=round(total_latency, 2),
            model_version="v1.0.0-shadow",
        )

    def get_disagreements(self) -> List[ShadowDisagreementRecord]:
        return list(self._disagreements)
