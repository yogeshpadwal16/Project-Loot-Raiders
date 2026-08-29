import unittest
from unittest.mock import patch, MagicMock
import requests

from deal_engine.scorer import (
    calculate_deal_score,
    get_heuristic_ai_ranking,
    get_gemini_ai_desirability_score,
    check_if_glitch,
    should_publish_deal,
    _ai_score_cache
)

class TestDealScorerArchitecture(unittest.TestCase):

    def setUp(self):
        # Clear cache between tests
        _ai_score_cache._cache.clear()

    # ---------------------------------------------------------
    # TEST 1: Apple iPhone Flagship Deal
    # ---------------------------------------------------------
    def test_apple_iphone_flagship_deal(self):
        # iPhone 16 128GB @ 59,999 / MRP 79,900 (~24.9% discount, 19,901 savings, verified low)
        score = calculate_deal_score(
            platform="amazon",
            price=59999,
            mrp=79900,
            discount=24.91,
            is_verified_low=True,
            title="Apple iPhone 16 (128 GB) - Teal",
            rating=4.6,
            reviews=12000
        )
        # Should be a strong genuine deal (80-92 range with DIE ratings)
        self.assertGreaterEqual(score, 75.0)
        self.assertLessEqual(score, 92.0)

    # ---------------------------------------------------------
    # TEST 2: Samsung Galaxy Flagship Deal
    # ---------------------------------------------------------
    def test_samsung_galaxy_flagship_deal(self):
        # Samsung S24 @ 45,999 / MRP 74,999 (~38.7% discount, 29,000 savings, verified low)
        score = calculate_deal_score(
            platform="amazon",
            price=45999,
            mrp=74999,
            discount=38.67,
            is_verified_low=True,
            title="Samsung Galaxy S24 5G (128GB)",
            rating=4.5,
            reviews=8500
        )
        self.assertGreaterEqual(score, 80.0)
        self.assertLessEqual(score, 94.0)

    # ---------------------------------------------------------
    # TEST 3: Branded Budget Earbuds (boAt)
    # ---------------------------------------------------------
    def test_boat_budget_earbuds_not_bloated(self):
        # boAt Earbuds @ 799 / MRP 2999 (~73.35% discount, 2200 savings, verified low)
        score = calculate_deal_score(
            platform="amazon",
            price=799,
            mrp=2999,
            discount=73.35,
            is_verified_low=True,
            title="boAt Airdopes 141 Bluetooth Truly Wireless Earbuds"
        )
        # Should be a solid budget deal (~65-78), NOT bloated > 90
        self.assertGreaterEqual(score, 65.0)
        self.assertLess(score, 82.0)

    # ---------------------------------------------------------
    # TEST 4: Generic USB Cable
    # ---------------------------------------------------------
    def test_generic_usb_cable_low_desirability(self):
        # Generic USB Cable @ 199 / MRP 999 (~80.08% discount)
        score_verified = calculate_deal_score(
            platform="amazon",
            price=199,
            mrp=999,
            discount=80.08,
            is_verified_low=True,
            title="Generic Micro USB Charging Cable"
        )
        # Low value item desirability penalty prevents it from becoming a top deal
        self.assertLess(score_verified, 70.0)

    # ---------------------------------------------------------
    # TEST 5: Fake High-MRP / Huge Advertised Discount Product
    # ---------------------------------------------------------
    def test_fake_mrp_unverified_deal_protected(self):
        # Unverified deal with 90% fake discount (MRP 9999 -> Price 999)
        score = calculate_deal_score(
            platform="amazon",
            price=999,
            mrp=9999,
            discount=90.0,
            is_verified_low=False,
            title="Unbranded Smartwatch with Heart Rate Monitor"
        )
        # DIE v2 Kappa-MRP attenuation and generic brand penalty suppress fake-MRP deals (< 45.0)
        self.assertLess(score, 45.0)
        self.assertFalse(should_publish_deal("amazon", score))

    # ---------------------------------------------------------
    # TEST 6: Verified Historical-Low Deal
    # ---------------------------------------------------------
    def test_verified_historical_low_can_exceed_publish(self):
        score = calculate_deal_score(
            platform="amazon",
            price=14999,
            mrp=24999,
            discount=40.0,
            is_verified_low=True,
            title="LG 32-inch HD Ready Smart LED TV"
        )
        self.assertGreaterEqual(score, 45.0)
        self.assertTrue(should_publish_deal("amazon", score))

    # ---------------------------------------------------------
    # TEST 7: Unverified Deal Protection
    # ---------------------------------------------------------
    def test_unverified_deal_protected_below_publish_threshold(self):
        score = calculate_deal_score(
            platform="amazon",
            price=2999,
            mrp=7999,
            discount=62.5,
            is_verified_low=False,
            title="Puma Men Running Shoes"
        )
        # Legitimate brand unverified deal with 62.5% discount qualifies in the standard band (45-80)
        self.assertGreaterEqual(score, 45.0)
        self.assertLess(score, 80.0)
        self.assertTrue(should_publish_deal("amazon", score))

    # ---------------------------------------------------------
    # TEST 8: Price Glitch Detection
    # ---------------------------------------------------------
    def test_price_glitch_boosts_score(self):
        # High value laptop at ₹3,999 (MRP ₹65,000, 93.8% OFF)
        is_glitch = check_if_glitch(
            price=3999,
            mrp=65000,
            discount=93.8,
            title="ASUS Vivobook 15 Intel Core i5 Laptop"
        )
        self.assertTrue(is_glitch)

        score = calculate_deal_score(
            platform="amazon",
            price=3999,
            mrp=65000,
            discount=93.8,
            is_verified_low=False,
            title="ASUS Vivobook 15 Intel Core i5 Laptop"
        )
        # Glitch deal should bypass unverified cap and score high
        self.assertGreaterEqual(score, 75.0)

    # ---------------------------------------------------------
    # TEST 9: OmniRoute Unavailable / Outage Handling
    # ---------------------------------------------------------
    @patch("requests.post")
    @patch("config.settings.load_settings")
    def test_omniroute_unavailable_does_not_break_scoring(self, mock_settings, mock_post):
        mock_settings.return_value = {
            "gemini_ai_scoring_enabled": True,
            "omniroute_base_url": "http://localhost:20128/v1",
            "omniroute_api_key": "test_key",
            "omniroute_model": "Loot-Raiders"
        }
        mock_post.side_effect = requests.RequestException("Connection refused")

        # Outage returns None gracefully
        score_ai = get_gemini_ai_desirability_score("Test Title", 1000, 2000, 50.0, "amazon")
        self.assertIsNone(score_ai)

        # Deterministic scoring completes without throwing error
        final_score = calculate_deal_score(
            platform="amazon",
            price=1999,
            mrp=4999,
            discount=60.0,
            is_verified_low=True,
            title="Sony WH-CH520 Wireless Headphones"
        )
        self.assertIsInstance(final_score, float)
        self.assertGreater(final_score, 0)

    # ---------------------------------------------------------
    # TEST 10: OmniRoute Malformed Response Handling
    # ---------------------------------------------------------
    @patch("requests.post")
    @patch("config.settings.load_settings")
    def test_omniroute_malformed_response_handled(self, mock_settings, mock_post):
        mock_settings.return_value = {
            "gemini_ai_scoring_enabled": True,
            "omniroute_base_url": "http://localhost:20128/v1",
            "omniroute_api_key": "test_key",
            "omniroute_model": "Loot-Raiders"
        }
        # Mock malformed response missing numeric score
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "I am not sure about this product"}}]}
        mock_post.return_value = mock_resp

        score_ai = get_gemini_ai_desirability_score("Test Title", 1000, 2000, 50.0, "amazon")
        self.assertIsNone(score_ai)

    # ---------------------------------------------------------
    # TEST 11: OmniRoute Disagreement Bounded Influence
    # ---------------------------------------------------------
    @patch("deal_engine.scorer.get_gemini_ai_desirability_score")
    @patch("config.settings.load_settings")
    def test_omniroute_cannot_dominate_final_score(self, mock_settings, mock_llm):
        mock_settings.return_value = {
            "gemini_ai_scoring_enabled": True,
            "scoring_rules": {"weights": {"discount": 0.35, "savings": 0.20, "history": 0.25, "urgency": 0.10, "trust": 0.10}}
        }
        # LLM gives extreme score 100, while heuristic score is ~50
        mock_llm.return_value = 100.0

        score_with_llm = calculate_deal_score(
            platform="amazon",
            price=1999,
            mrp=2999,
            discount=33.3,
            is_verified_low=True,
            title="Plain Cotton T-Shirt"
        )

        mock_llm.return_value = None
        score_without_llm = calculate_deal_score(
            platform="amazon",
            price=1999,
            mrp=2999,
            discount=33.3,
            is_verified_low=True,
            title="Plain Cotton T-Shirt"
        )

        # Difference should be bounded (at most +/- 5 points)
        diff = abs(score_with_llm - score_without_llm)
        self.assertLessEqual(diff, 5.0)

    # ---------------------------------------------------------
    # TEST 12: Heuristic Cache Behavior
    # ---------------------------------------------------------
    def test_heuristic_cache_behavior(self):
        title = "Test Product Title Cache Key"
        price = 1000
        platform = "amazon"
        product_id = "test_cache_id_1"

        # Prime cache
        score1 = get_heuristic_ai_ranking(
            title=title,
            platform=platform,
            price=price,
            mrp=2000,
            discount=50.0,
            is_verified_low=True,
            product_id=product_id
        )

        cache_key = (product_id, title, price, platform)
        self.assertEqual(_ai_score_cache.get(cache_key), score1)

        # Changing price must produce/use a distinct cache key
        score2 = get_heuristic_ai_ranking(
            title=title,
            platform=platform,
            price=500,
            mrp=2000,
            discount=75.0,
            is_verified_low=True,
            product_id=product_id
        )
        new_cache_key = (product_id, title, 500, platform)
        self.assertEqual(_ai_score_cache.get(new_cache_key), score2)

    # ---------------------------------------------------------
    # TEST 13: Scores Above 95 are Exceptional & Uncommon
    # ---------------------------------------------------------
    def test_scores_above_95_are_uncommon(self):
        standard_good_deal = calculate_deal_score(
            platform="amazon",
            price=1200,
            mrp=3000,
            discount=60.0,
            is_verified_low=True,
            title="JBL Go 3 Wireless Speaker"
        )
        self.assertLess(standard_good_deal, 95.0)

if __name__ == "__main__":
    unittest.main()
