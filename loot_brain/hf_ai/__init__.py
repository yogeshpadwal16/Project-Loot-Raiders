"""
Loot Raiders Hugging Face AI Intelligence Package.
Provides isolated, lightweight local AI capabilities including 2nd-stage semantic reranking,
product & deal classification, shadow mode evaluation, and fail-safe inference governance.
"""

from loot_brain.hf_ai.config import HFAIConfig
from loot_brain.hf_ai.types import RerankCandidate, RerankResult, ClassificationResult, LocalAISignals
from loot_brain.hf_ai.reranker.semantic_reranker import SemanticReranker
from loot_brain.hf_ai.classifier.deal_classifier import DealClassifier
from loot_brain.hf_ai.shadow.shadow_evaluator import HFShadowEvaluator
from loot_brain.hf_ai.evaluation.benchmark import HFAIBenchmark

__all__ = [
    "HFAIConfig",
    "RerankCandidate",
    "RerankResult",
    "ClassificationResult",
    "LocalAISignals",
    "SemanticReranker",
    "DealClassifier",
    "HFShadowEvaluator",
    "HFAIBenchmark",
]
