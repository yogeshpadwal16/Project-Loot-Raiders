"""
tests/test_die_v2_mathematical_validation.py
Automated unit, boundary, adversarial, and monotonicity tests for DIE v2 scoring mathematics.
"""

import unittest
import math


class TestDIEv2MathematicalValidation(unittest.TestCase):
    def setUp(self):
        self.COMMISSION_RATES = {
            "fashion": 0.08,
            "beauty": 0.07,
            "home": 0.06,
            "electronics": 0.045,
            "grocery": 0.05,
            "appliances": 0.035,
            "laptops": 0.03,
            "smartphones": 0.015,
            "general": 0.04
        }
        self.FLAGSHIP_BRANDS = ["apple", "samsung", "sony", "dyson", "bose", "lg", "dell", "hp", "nike", "adidas"]
        self.GENERIC_BRANDS = ["generic", "unbranded", "local", "no brand"]

    def _calc_die_v2(self, title, price, mrp, discount, is_verified_low=False, brand_tier="standard", qualified_clicks=0, risk=0.0):
        t_lower = (title or "").lower()
        is_flagship = any(b in t_lower for b in self.FLAGSHIP_BRANDS) or brand_tier == "flagship"
        is_generic = any(b in t_lower for b in self.GENERIC_BRANDS) or brand_tier == "generic"

        # 1. Kappa MRP
        if is_verified_low or is_flagship:
            kappa_mrp = 1.0
        elif is_generic:
            if discount >= 80.0: kappa_mrp = 0.25
            elif discount >= 60.0: kappa_mrp = 0.50
            else: kappa_mrp = 0.75
        else:
            if discount >= 85.0: kappa_mrp = 0.40
            elif discount >= 75.0: kappa_mrp = 0.70
            else: kappa_mrp = 1.0

        eff_disc = discount * kappa_mrp
        eff_save = max(0, mrp - price) * kappa_mrp

        # 2. Components
        if mrp >= 15000:
            s_disc = 0.0 if eff_disc < 15.0 else min(100.0, ((eff_disc - 15.0) / 35.0) * 100.0)
        else:
            s_disc = 0.0 if eff_disc < 20.0 else min(100.0, ((eff_disc - 20.0) / 60.0) * 100.0)

        s_save = min(100.0, (eff_save / 8000.0) * 100.0)
        s_hist = 100.0 if is_verified_low else 45.0
        
        brand_bonus = 18.0 if is_flagship else (-20.0 if is_generic else 0.0)
        s_ai = max(0.0, min(100.0, 50.0 + brand_bonus))

        exp_comm = price * 0.045
        s_comm = min(100.0, (exp_comm / 500.0) * 100.0)

        base = (s_disc * 0.25) + (s_save * 0.15) + (s_hist * 0.20) + (s_ai * 0.20) + (s_comm * 0.10) + (50.0 * 0.05) + (90.0 * 0.05)
        pop = min(15.0, (qualified_clicks // 10) * 2.5)
        risk_pen = -10.0 if risk >= 80.0 else (-5.0 if risk >= 50.0 else 0.0)

        return max(0.0, min(100.0, base + pop + risk_pen))

    def test_01_fake_mrp_suppression(self):
        """Verify fake 95% discount on unbranded product is heavily suppressed (< 45)."""
        score = self._calc_die_v2("Generic Smart Watch", 499, 9999, 95.0, is_verified_low=False, brand_tier="generic")
        self.assertLess(score, 45.0)

    def test_02_flagship_genuine_discount_promoted(self):
        """Verify genuine flagship discount achieves high score (> 80)."""
        score = self._calc_die_v2("Sony WH-1000XM4 Headphones", 8990, 29990, 70.0, is_verified_low=True, brand_tier="flagship")
        self.assertGreater(score, 80.0)

    def test_03_monotonicity_genuine_savings(self):
        """Increasing savings on verified deal must monotonically increase score."""
        s1 = self._calc_die_v2("Sony Headphones", 5000, 7000, 28.5, is_verified_low=True, brand_tier="flagship")
        s2 = self._calc_die_v2("Sony Headphones", 5000, 10000, 50.0, is_verified_low=True, brand_tier="flagship")
        s3 = self._calc_die_v2("Sony Headphones", 5000, 20000, 75.0, is_verified_low=True, brand_tier="flagship")
        self.assertLess(s1, s2)
        self.assertLess(s2, s3)

    def test_04_popularity_feedback_cap(self):
        """Verify popularity bonus saturates at +15 max even at 10,000 clicks."""
        s_base = self._calc_die_v2("Puma Shoes", 1999, 3999, 50.0, qualified_clicks=0)
        s_100 = self._calc_die_v2("Puma Shoes", 1999, 3999, 50.0, qualified_clicks=100)
        s_10000 = self._calc_die_v2("Puma Shoes", 1999, 3999, 50.0, qualified_clicks=10000)

        self.assertAlmostEqual(s_100 - s_base, 15.0, places=1)
        self.assertEqual(s_100, s_10000)

    def test_05_cancellation_risk_penalty(self):
        """Verify high cancellation risk deal receives substantial penalty."""
        s_safe = self._calc_die_v2("Laptop", 999, 89999, 98.9, risk=0.0)
        s_risky = self._calc_die_v2("Laptop", 999, 89999, 98.9, risk=90.0)
        self.assertGreater(s_safe - s_risky, 9.0)

    def test_06_boundary_limits(self):
        """Score must always be strictly clamped within [0.0, 100.0]."""
        s_min = self._calc_die_v2("Junk", 0, 0, 0.0, brand_tier="generic", risk=100.0)
        s_max = self._calc_die_v2("Sony Flagship", 50000, 150000, 66.7, is_verified_low=True, brand_tier="flagship", qualified_clicks=100)
        self.assertGreaterEqual(s_min, 0.0)
        self.assertLessEqual(s_max, 100.0)


if __name__ == "__main__":
    unittest.main()
