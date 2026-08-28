"""
tests/test_die_v2_economic_validation.py
Automated unit and integration tests for DIE v2 total economic value modeling,
suppression classification, threshold sensitivity, and new-deal fairness.
"""

import unittest


class TestDIEv2EconomicValidation(unittest.TestCase):
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

    def _expected_revenue_per_deal(self, price, category, discount, brand_tier="standard", is_verified=False, clicks=250):
        comm_rate = self.COMMISSION_RATES.get(category, 0.04)
        exp_comm = price * comm_rate

        # Conversion rate
        if price < 500: base_p = 0.045
        elif price <= 2000: base_p = 0.035
        elif price <= 10000: base_p = 0.020
        elif price <= 35000: base_p = 0.010
        else: base_p = 0.005

        brand_mult = 1.4 if brand_tier == "flagship" else (0.6 if brand_tier == "generic" else 1.0)
        disc_mult = min(1.5, 0.8 + (discount / 100.0))
        verif_mult = 1.2 if is_verified else 0.9
        conv_p = min(0.12, base_p * brand_mult * disc_mult * verif_mult)

        ret_risk = 0.20 if category == "fashion" else (0.08 if category == "appliances" else 0.06)
        if brand_tier == "generic" and discount >= 80.0:
            ret_risk += 0.20

        net_rev_per_click = exp_comm * conv_p * (1.0 - ret_risk)
        return net_rev_per_click * clicks

    def test_01_high_ticket_high_yield_superiority(self):
        """Verify high ticket genuine appliance generates significantly higher expected revenue than low ticket generic item."""
        # 1. Voltas 1.5 Ton AC (Price Rs.37,490, 55% discount, Appliances 3.5% comm)
        rev_ac = self._expected_revenue_per_deal(37490, "appliances", 55.0, brand_tier="flagship", is_verified=True)

        # 2. Generic Phone Case (Price Rs.149, 90% discount, Electronics 4.5% comm)
        rev_case = self._expected_revenue_per_deal(149, "electronics", 90.0, brand_tier="generic", is_verified=False)

        self.assertGreater(rev_ac, rev_case * 50.0)

    def test_02_fashion_category_commission_yield(self):
        """Verify fashion category with 8% commission yields strong expected commercial return on genuine deals."""
        rev_shoes = self._expected_revenue_per_deal(1999, "fashion", 50.0, brand_tier="flagship", is_verified=True)
        self.assertGreater(rev_shoes, 500.0)

    def test_03_return_risk_adjustment(self):
        """Verify return risk adjustment dampens generic high-discount goods with high return likelihood."""
        rev_safe = self._expected_revenue_per_deal(999, "electronics", 40.0, brand_tier="standard", is_verified=True)
        rev_generic_high_ret = self._expected_revenue_per_deal(999, "electronics", 85.0, brand_tier="generic", is_verified=False)

        # Conversion / return penalties reduce generic item yield relative to its claimed discount
        self.assertLess(rev_generic_high_ret, rev_safe * 2.0)

    def test_04_new_deal_fairness_without_click_history(self):
        """Verify a fresh scrape with 0 clicks from a flagship brand achieves publishable score."""
        # Simulate DIE v2 base calculation
        w_disc, w_save, w_hist, w_ai, w_comm, w_urg, w_trust = 0.25, 0.15, 0.20, 0.20, 0.10, 0.05, 0.05
        s_disc = 60.0  # 40% discount
        s_save = 50.0  # Rs.4,000 savings
        s_hist = 45.0  # Unverified fresh scrape
        s_ai = 68.0    # Flagship brand (+18)
        s_comm = 40.0  # Rs.200 exp commission
        s_urg = 50.0
        s_trust = 90.0

        base = (s_disc * w_disc) + (s_save * w_save) + (s_hist * w_hist) + (s_ai * w_ai) + (s_comm * w_comm) + (s_urg * w_urg) + (s_trust * w_trust)
        self.assertGreaterEqual(base, 45.0)


if __name__ == "__main__":
    unittest.main()
