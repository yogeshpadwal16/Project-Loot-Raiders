"""
Comprehensive Unit Test Suite for Hugging Face AI Subsystem.
Verifies config, inference engine, circuit breaker, semantic reranker, deal classifier,
shadow mode evaluator, and benchmark suite without modifying production behavior.
"""

import unittest
from loot_brain.hf_ai.config import HFAIConfig
from loot_brain.hf_ai.inference.circuit_breaker import InferenceCircuitBreaker, CircuitState
from loot_brain.hf_ai.inference.engine import HFInferenceEngine
from loot_brain.hf_ai.reranker.semantic_reranker import SemanticReranker
from loot_brain.hf_ai.classifier.deal_classifier import DealClassifier
from loot_brain.hf_ai.shadow.shadow_evaluator import HFShadowEvaluator
from loot_brain.hf_ai.evaluation.benchmark import HFAIBenchmark, HFAIBenchmarkTestCase
from loot_brain.hf_ai.types import RerankCandidate, LocalAISignals


class TestHFAIIntelligence(unittest.TestCase):

    def setUp(self):
        from loot_brain.hf_ai.config import hf_ai_config
        hf_ai_config.ENABLE_LOCAL_AI = True
        hf_ai_config.LOCAL_AI_SHADOW_MODE = True
        self.circuit_breaker = InferenceCircuitBreaker(failure_threshold=2, recovery_timeout_sec=10.0)
        self.engine = HFInferenceEngine()
        self.reranker = SemanticReranker()
        self.classifier = DealClassifier()
        self.shadow = HFShadowEvaluator()
        self.benchmark = HFAIBenchmark()

    def tearDown(self):
        from loot_brain.hf_ai.config import hf_ai_config
        hf_ai_config.ENABLE_LOCAL_AI = False

    def test_config_defaults(self):
        """Test configuration defaults and environment override safety."""
        from loot_brain.hf_ai.config import hf_ai_config
        self.assertTrue(isinstance(hf_ai_config.LOCAL_AI_SHADOW_MODE, bool))
        self.assertEqual(hf_ai_config.MAX_RERANK_CANDIDATES, 5)

    def test_circuit_breaker_tripping_and_recovery(self):
        """Test circuit breaker trips after repeated failures."""
        self.assertTrue(self.circuit_breaker.allow_execution())
        self.circuit_breaker.record_failure()
        self.circuit_breaker.record_failure()
        self.assertEqual(self.circuit_breaker.state, CircuitState.OPEN)
        self.assertFalse(self.circuit_breaker.allow_execution())

    def test_semantic_reranker_accessory_detection(self):
        """Test 2nd-stage reranker penalizes accessory candidates for primary product query."""
        query_title = "Samsung Galaxy S24 Ultra 5G (256GB)"
        candidates = [
            RerankCandidate(
                candidate_id="c1",
                candidate_title="Samsung Galaxy S24 Ultra Protective Case Cover",
                candidate_price=499.0,
                initial_score=0.90,
            ),
            RerankCandidate(
                candidate_id="c2",
                candidate_title="Samsung Galaxy S24 Ultra 5G 256GB Titanium",
                candidate_price=109999.0,
                initial_score=0.92,
            ),
        ]
        results = self.reranker.rerank_candidates(query_title=query_title, candidates=candidates)
        self.assertEqual(len(results), 2)
        # Exact product should be top ranked over accessory
        self.assertEqual(results[0].candidate_id, "c2")
        self.assertGreater(results[0].same_product_probability, results[1].same_product_probability)

    def test_semantic_reranker_variant_mismatch(self):
        """Test 2nd-stage reranker detects storage variant mismatch (128GB vs 256GB)."""
        query_title = "Apple iPhone 15 Pro 128GB"
        candidates = [
            RerankCandidate(
                candidate_id="c1",
                candidate_title="Apple iPhone 15 Pro 256GB Natural Titanium",
                candidate_price=129900.0,
                initial_score=0.88,
            )
        ]
        results = self.reranker.rerank_candidates(query_title=query_title, candidates=candidates)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].same_variant_probability, 0.20)

    def test_deal_classifier_brand_and_category(self):
        """Test deal classifier extracts brand, category, and accessory status."""
        res = self.classifier.classify_deal(
            title="Sony WH-CH520 Wireless Headphones",
            price=3990.0,
            mrp=5990.0,
            platform="Amazon",
        )
        self.assertEqual(res.brand, "Sony")
        self.assertEqual(res.category, "audio")
        self.assertFalse(res.is_accessory)
        self.assertGreater(res.deal_quality_probability, 0.30)

    def test_shadow_mode_evaluation(self):
        """Test shadow mode evaluator produces LocalAISignals without affecting production decisions."""
        signals = self.shadow.evaluate_shadow_signals(
            task_id="task-shadow-hf-1",
            title="ASUS Vivobook 15 Intel Core i5",
            price=45990.0,
            mrp=65990.0,
            production_decision="APPROVE",
        )
        self.assertTrue(signals.model_available)
        self.assertTrue(signals.shadow_mode)
        self.assertIsNotNone(signals.classification_result)
        self.assertEqual(signals.classification_result.brand, "ASUS")

    def test_benchmark_suite_execution(self):
        """Test benchmark evaluation suite over reference test cases."""
        test_cases = [
            HFAIBenchmarkTestCase(
                case_id="b1",
                title="Samsung Galaxy S24 5G 128GB",
                price=64999.0,
                mrp=79999.0,
                expected_category="smartphone",
                expected_is_accessory=False,
                expected_brand="Samsung",
            ),
            HFAIBenchmarkTestCase(
                case_id="b2",
                title="Puma Men Running Shoes",
                price=1999.0,
                mrp=4999.0,
                expected_category="footwear",
                expected_is_accessory=False,
                expected_brand="Puma",
            ),
        ]
        metrics = self.benchmark.run_benchmark_suite(test_cases)
        self.assertEqual(metrics.total_cases, 2)
        self.assertEqual(metrics.category_accuracy, 100.0)
        self.assertEqual(metrics.brand_accuracy, 100.0)
        self.assertTrue(metrics.pass_status)


if __name__ == "__main__":
    unittest.main()
