"""
Benchmark Evaluation Suite for Local Hugging Face AI Integration.
Evaluates precision, recall, F1 score, and latency metrics across benchmark dataset cases.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from loot_brain.hf_ai.classifier.deal_classifier import DealClassifier
from loot_brain.hf_ai.reranker.semantic_reranker import SemanticReranker

logger = logging.getLogger(__name__)


class HFAIBenchmarkTestCase(BaseModel):
    """Ground-truth benchmark test case for HF AI evaluation."""
    case_id: str
    title: str
    price: float
    mrp: float
    expected_category: str
    expected_is_accessory: bool
    expected_brand: str


class HFAIBenchmarkMetrics(BaseModel):
    """Aggregated evaluation metrics for Hugging Face AI benchmark run."""
    total_cases: int = 0
    category_accuracy: float = 0.0
    brand_accuracy: float = 0.0
    accessory_accuracy: float = 0.0
    avg_latency_ms: float = 0.0
    pass_status: bool = False


class HFAIBenchmark:
    """
    Evaluation Benchmark Framework for validating local AI intelligence.
    """

    def __init__(self):
        self.classifier = DealClassifier()
        self.reranker = SemanticReranker()

    def run_benchmark_suite(self, test_cases: List[HFAIBenchmarkTestCase]) -> HFAIBenchmarkMetrics:
        """Runs benchmark suite over test cases."""
        if not test_cases:
            return HFAIBenchmarkMetrics()

        cat_hits = 0
        brand_hits = 0
        acc_hits = 0
        total_latency = 0.0

        for case in test_cases:
            start_time = time.time()
            res = self.classifier.classify_deal(title=case.title, price=case.price, mrp=case.mrp)
            duration = (time.time() - start_time) * 1000
            total_latency += duration

            if res.category == case.expected_category:
                cat_hits += 1
            if res.brand == case.expected_brand:
                brand_hits += 1
            if res.is_accessory == case.expected_is_accessory:
                acc_hits += 1

        total = len(test_cases)
        cat_acc = (cat_hits / total) * 100.0
        brand_acc = (brand_hits / total) * 100.0
        acc_acc = (acc_hits / total) * 100.0
        avg_latency = total_latency / total

        overall_pass = (cat_acc >= 75.0 and brand_acc >= 75.0 and acc_acc >= 85.0)

        metrics = HFAIBenchmarkMetrics(
            total_cases=total,
            category_accuracy=round(cat_acc, 2),
            brand_accuracy=round(brand_acc, 2),
            accessory_accuracy=round(acc_acc, 2),
            avg_latency_ms=round(avg_latency, 2),
            pass_status=overall_pass,
        )

        logger.info(f"[HFAIBenchmark] Completed ({total} cases): Category={cat_acc:.1f}%, Brand={brand_acc:.1f}%, Accessory={acc_acc:.1f}% (Avg Latency: {avg_latency:.2f}ms)")
        return metrics
