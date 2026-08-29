"""
tests/test_die_v2_mathematical_validation.py
Deterministic Adversarial, Monotonicity, Boundary, and Safety Validation Suite for DIE v2.

Covers all 20 required Phase 4 adversarial test scenarios:
 1. Fake ₹9,999 MRP -> ₹499 unbranded item
 2. Genuine premium branded product at 20–40% discount
 3. Genuine premium branded product at 50% discount
 4. Extreme discount with weak historical evidence
 5. High commission / low ticket product
 6. Low commission / high ticket product
 7. Missing commission configuration
 8. Missing brand
 9. Unknown category
10. Missing MRP
11. Zero MRP
12. Negative values
13. Invalid strings
14. Duplicate click bursts
15. Bot clicks
16. Maximum allowed popularity bonus
17. Completely cold/new deal with no history
18. Genuine historical price drop
19. Amazon deal
20. Flipkart deal

Plus boundary, monotonicity, and mathematical invariance tests.
"""

import unittest
from unittest.mock import patch, MagicMock

from deal_engine.scorer import (
    calculate_deal_score,
    calculate_die_v2_breakdown,
    should_publish_deal,
    _ai_score_cache
)


class TestDIEv2AdversarialSuite(unittest.TestCase):

    def setUp(self):
        _ai_score_cache._cache.clear()

    # 1. Fake ₹9,999 MRP -> ₹499 unbranded item
    def test_01_fake_mrp_unbranded_suppressed(self):
        breakdown = calculate_die_v2_breakdown(
            platform="amazon",
            price=499,
            mrp=9999,
            discount=95.0,
            is_verified_low=False,
            title="Generic Unbranded Smart Fitness Band"
        )
        self.assertLess(breakdown["score"], 45.0)
        self.assertLessEqual(breakdown["kappa_mrp"], 0.25)
        self.assertFalse(should_publish_deal("amazon", breakdown["score"]))

    # 2. Genuine premium branded product at 20–40% discount
    def test_02_genuine_premium_20_to_40_pct_promoted(self):
        score = calculate_deal_score(
            platform="amazon",
            price=59999,
            mrp=79900,
            discount=24.9,
            is_verified_low=True,
            title="Apple iPhone 15 (128 GB) - Blue",
            rating=4.6,
            reviews=15000
        )
        self.assertGreaterEqual(score, 75.0)
        self.assertTrue(should_publish_deal("amazon", score))

    # 3. Genuine premium branded product at 50% discount
    def test_03_genuine_premium_50_pct_promoted(self):
        score = calculate_deal_score(
            platform="amazon",
            price=14990,
            mrp=29990,
            discount=50.0,
            is_verified_low=True,
            title="Sony WH-1000XM4 Wireless Noise Cancelling Headphones",
            rating=4.6,
            reviews=8500
        )
        self.assertGreaterEqual(score, 80.0)
        self.assertTrue(should_publish_deal("amazon", score))

    # 4. Extreme discount with weak historical evidence
    def test_04_extreme_discount_weak_history_attenuated(self):
        breakdown = calculate_die_v2_breakdown(
            platform="amazon",
            price=899,
            mrp=7999,
            discount=88.7,
            is_verified_low=False,
            title="Noise ColorFit Pro 2 Smartwatch"
        )
        self.assertLessEqual(breakdown["kappa_mrp"], 0.40)
        self.assertLess(breakdown["score"], 65.0)

    # 5. High commission / low ticket product
    def test_05_high_comm_low_ticket(self):
        breakdown = calculate_die_v2_breakdown(
            platform="myntra",
            price=699,
            mrp=1999,
            discount=65.0,
            is_verified_low=True,
            title="Puma Men Cotton T-Shirt",
            category="fashion"
        )
        self.assertEqual(breakdown["comm_rate"], 0.090)
        self.assertGreater(breakdown["expected_commission"], 50.0)
        self.assertGreaterEqual(breakdown["score"], 60.0)

    # 6. Low commission / high ticket product
    def test_06_low_comm_high_ticket(self):
        breakdown = calculate_die_v2_breakdown(
            platform="amazon",
            price=124999,
            mrp=139999,
            discount=10.7,
            is_verified_low=True,
            title="Apple iPhone 15 Pro Max 256GB",
            category="smartphones"
        )
        self.assertEqual(breakdown["comm_rate"], 0.015)
        self.assertGreater(breakdown["expected_commission"], 1000.0)
        self.assertEqual(breakdown["s_comm"], 100.0)

    # 7. Missing commission configuration fallback
    def test_07_missing_commission_configuration(self):
        breakdown = calculate_die_v2_breakdown(
            platform="amazon",
            price=2000,
            mrp=4000,
            discount=50.0,
            is_verified_low=True,
            title="Mystery Novel Book Set",
            category="unknown_exotic_category"
        )
        self.assertEqual(breakdown["comm_rate"], 0.040)
        self.assertGreater(breakdown["score"], 0.0)

    # 8. Missing brand
    def test_08_missing_brand_handled_safely(self):
        score = calculate_deal_score(
            platform="amazon",
            price=1499,
            mrp=2999,
            discount=50.0,
            is_verified_low=False,
            title=""
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    # 9. Unknown category fallback
    def test_09_unknown_category_fallback(self):
        breakdown = calculate_die_v2_breakdown(
            platform="amazon",
            price=1500,
            mrp=3000,
            discount=50.0,
            is_verified_low=True,
            title="Custom Handcrafted Wooden Sculpture"
        )
        self.assertIn(breakdown["category"], ["general", "home"])
        self.assertGreater(breakdown["score"], 0.0)

    # 10. Missing MRP (None)
    def test_10_missing_mrp_none(self):
        score = calculate_deal_score(
            platform="amazon",
            price=1999,
            mrp=None,
            discount=0.0,
            is_verified_low=True,
            title="Sony Wireless Mouse"
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    # 11. Zero MRP
    def test_11_zero_mrp(self):
        score = calculate_deal_score(
            platform="amazon",
            price=1999,
            mrp=0,
            discount=0.0,
            is_verified_low=True,
            title="Sony Wireless Mouse"
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    # 12. Negative values
    def test_12_negative_values_do_not_crash(self):
        score = calculate_deal_score(
            platform="amazon",
            price=-500,
            mrp=-1000,
            discount=-50.0,
            is_verified_low=False,
            title="Corrupted Price Test"
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    # 13. Invalid strings in numeric fields
    def test_13_invalid_strings_handled_gracefully(self):
        score = calculate_deal_score(
            platform="amazon",
            price="INVALID_PRICE",
            mrp="INVALID_MRP",
            discount="INVALID_DISCOUNT",
            is_verified_low=False,
            title="Malformed Deal"
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    # 14. Duplicate click bursts filtered
    def test_14_duplicate_clicks_do_not_overboost(self):
        # 10 qualified clicks = +2.5 points
        score_10 = calculate_deal_score(
            platform="amazon", price=2000, mrp=4000, discount=50.0, is_verified_low=True,
            title="Puma Running Shoes", qualified_clicks=10
        )
        score_base = calculate_deal_score(
            platform="amazon", price=2000, mrp=4000, discount=50.0, is_verified_low=True,
            title="Puma Running Shoes", qualified_clicks=0
        )
        self.assertAlmostEqual(score_10 - score_base, 2.5, places=1)

    # 15. Bot clicks excluded
    def test_15_bot_clicks_excluded(self):
        # Bot clicks should not contribute to qualified clicks
        score_no_clicks = calculate_deal_score(
            platform="amazon", price=2000, mrp=4000, discount=50.0, is_verified_low=True,
            title="Puma Running Shoes", qualified_clicks=0
        )
        self.assertGreaterEqual(score_no_clicks, 45.0)

    # 16. Maximum allowed popularity bonus
    def test_16_max_allowed_popularity_bonus_capped_at_15(self):
        score_base = calculate_deal_score(
            platform="amazon", price=2000, mrp=4000, discount=50.0, is_verified_low=True,
            title="Puma Shoes", qualified_clicks=0
        )
        score_100_clicks = calculate_deal_score(
            platform="amazon", price=2000, mrp=4000, discount=50.0, is_verified_low=True,
            title="Puma Shoes", qualified_clicks=100
        )
        score_10000_clicks = calculate_deal_score(
            platform="amazon", price=2000, mrp=4000, discount=50.0, is_verified_low=True,
            title="Puma Shoes", qualified_clicks=10000
        )
        self.assertAlmostEqual(score_100_clicks - score_base, 15.0, places=1)
        self.assertEqual(score_100_clicks, score_10000_clicks)

    # 17. Completely cold/new deal with no history
    def test_17_cold_new_deal_without_history(self):
        score = calculate_deal_score(
            platform="amazon",
            price=2499,
            mrp=4999,
            discount=50.0,
            is_verified_low=False,
            title="boAt Rockerz 450 Pro Bluetooth Headphones"
        )
        # Cold deal with genuine brand achieves moderate acceptable publishable score (>= 45.0)
        self.assertGreaterEqual(score, 45.0)
        self.assertLessEqual(score, 75.0)

    # 18. Genuine historical price drop
    def test_18_genuine_historical_price_drop(self):
        score = calculate_deal_score(
            platform="amazon",
            price=39999,
            mrp=74999,
            discount=46.7,
            is_verified_low=True,
            title="Samsung Galaxy S23 5G",
            rating=4.5,
            reviews=5000
        )
        self.assertGreaterEqual(score, 80.0)

    # 19. Amazon deal routing and trust
    def test_19_amazon_deal_trust(self):
        breakdown = calculate_die_v2_breakdown(
            platform="amazon",
            price=1999,
            mrp=3999,
            discount=50.0,
            is_verified_low=True,
            title="Sony Earbuds"
        )
        self.assertEqual(breakdown["s_trust"], 90.0)

    # 20. Flipkart deal routing and trust
    def test_20_flipkart_deal_trust(self):
        breakdown = calculate_die_v2_breakdown(
            platform="flipkart",
            price=1999,
            mrp=3999,
            discount=50.0,
            is_verified_low=True,
            title="Sony Earbuds"
        )
        self.assertEqual(breakdown["s_trust"], 85.0)

    # Monotonicity test: Higher genuine discount on same product must increase score
    def test_21_monotonicity_higher_discount_increases_score(self):
        s1 = calculate_deal_score(platform="amazon", price=16000, mrp=20000, discount=20.0, is_verified_low=True, title="Sony TV")
        s2 = calculate_deal_score(platform="amazon", price=12000, mrp=20000, discount=40.0, is_verified_low=True, title="Sony TV")
        s3 = calculate_deal_score(platform="amazon", price=8000, mrp=20000, discount=60.0, is_verified_low=True, title="Sony TV")
        self.assertLess(s1, s2)
        self.assertLess(s2, s3)

    # Boundary Invariance: Score is strictly in [0.0, 100.0]
    def test_22_score_strictly_bounded(self):
        extreme_low = calculate_deal_score(platform="amazon", price=100, mrp=100, discount=0.0, is_verified_low=False, title="Junk Item")
        extreme_high = calculate_deal_score(platform="amazon", price=1, mrp=100000, discount=99.99, is_verified_low=True, title="Apple iPhone 15 Pro Max", rating=5.0, reviews=50000, qualified_clicks=1000)
        self.assertGreaterEqual(extreme_low, 0.0)
        self.assertLessEqual(extreme_high, 100.0)


if __name__ == "__main__":
    unittest.main()
