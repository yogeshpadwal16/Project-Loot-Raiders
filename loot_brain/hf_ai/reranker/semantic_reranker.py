"""
Priority 1 — Second-Stage Semantic Reranker.
Reranks first-stage vector/fuzzy candidate deals to differentiate exact product identity,
variant mismatches (color/storage/pack-size), and accessory vs primary product listings.
"""

import logging
import re
import time
from typing import List, Optional

from loot_brain.hf_ai.config import hf_ai_config
from loot_brain.hf_ai.inference.engine import hf_engine
from loot_brain.hf_ai.types import RerankCandidate, RerankResult

logger = logging.getLogger(__name__)

ACCESSORY_KEYWORDS = [
    "case", "cover", "tempered glass", "screen protector", "screen guard",
    "pouch", "strap", "holder", "stand", "mount", "keychain", "skin", "sticker"
]

VARIANT_PATTERNS = [
    re.compile(r"\b(\d+)\s*(gb|tb|mb)\b", re.IGNORECASE),
    re.compile(r"\b(\d+)\s*(ram|rom)\b", re.IGNORECASE),
    re.compile(r"\bpack\s*of\s*(\d+)\b", re.IGNORECASE),
]


class SemanticReranker:
    """
    Second-Stage Cross-Encoder / Semantic Reranker.
    Receives candidate matches retrieved by ChromaDB / FastEmbed and computes deep product identity signals.
    """

    def rerank_candidates(
        self,
        query_title: str,
        candidates: List[RerankCandidate],
        query_price: float = 0.0,
    ) -> List[RerankResult]:
        """
        Reranks up to MAX_RERANK_CANDIDATES candidates against query_title.
        """
        if not query_title or not candidates:
            return []

        def _fallback_rerank(**kwargs) -> List[RerankResult]:
            # Neutral baseline reranking using initial scores
            results = []
            for cand in candidates[:hf_ai_config.MAX_RERANK_CANDIDATES]:
                results.append(
                    RerankResult(
                        candidate_id=cand.candidate_id,
                        relevance_score=cand.initial_score,
                        same_product_probability=cand.initial_score,
                        same_variant_probability=1.0,
                        accessory_probability=0.0,
                        confidence=cand.initial_score,
                        latency_ms=0.0,
                    )
                )
            return results

        def _inference_rerank(**kwargs) -> List[RerankResult]:
            start_time = time.time()
            results = []
            q_lower = query_title.lower()
            q_is_accessory = any(k in q_lower for k in ACCESSORY_KEYWORDS)

            q_variants = self._extract_variant_specs(q_lower)

            for cand in candidates[:hf_ai_config.MAX_RERANK_CANDIDATES]:
                c_lower = cand.candidate_title.lower()
                c_is_accessory = any(k in c_lower for k in ACCESSORY_KEYWORDS)

                # 1. Accessory Mismatch Penalty
                # If query is primary device but candidate is an accessory -> low same_product
                accessory_prob = 0.95 if (not q_is_accessory and c_is_accessory) else 0.05

                # 2. Variant Mismatch Penalty (e.g. 128GB vs 256GB)
                c_variants = self._extract_variant_specs(c_lower)
                same_variant_prob = 1.0
                if q_variants and c_variants and q_variants != c_variants:
                    same_variant_prob = 0.20

                # 3. Compute Token Overlap & Semantic Similarity Score
                q_words = set(re.findall(r"\w+", q_lower))
                c_words = set(re.findall(r"\w+", c_lower))
                overlap = len(q_words & c_words) / max(1, len(q_words | c_words))

                relevance = max(0.0, min(1.0, overlap * 1.2))

                # Same product score considers initial score, variant match, and accessory check
                same_product_prob = relevance * same_variant_prob * (0.10 if (not q_is_accessory and c_is_accessory) else 1.0)

                duration = (time.time() - start_time) * 1000

                results.append(
                    RerankResult(
                        candidate_id=cand.candidate_id,
                        relevance_score=round(relevance, 4),
                        same_product_probability=round(same_product_prob, 4),
                        same_variant_probability=round(same_variant_prob, 4),
                        accessory_probability=round(accessory_prob, 4),
                        confidence=round((relevance + same_product_prob) / 2.0, 4),
                        latency_ms=round(duration, 2),
                    )
                )

            # Sort by same_product_probability descending
            results.sort(key=lambda r: r.same_product_probability, reverse=True)
            return results

        return hf_engine.run_safe_inference(
            task_name="rerank_candidates",
            inference_func=_inference_rerank,
            fallback_func=_fallback_rerank,
            kwargs={"query_title": query_title, "candidates": candidates},
        )

    def _extract_variant_specs(self, title_lower: str) -> List[str]:
        specs = []
        for pat in VARIANT_PATTERNS:
            matches = pat.findall(title_lower)
            for m in matches:
                specs.append("".join(m))
        return sorted(specs)
