"""
tests/test_growth_suite.py
Unit tests for the Full Growth Suite:
1. Auto-Coupon Hunter & Stacked Deal Pricing
2. Native Web Push Notifications
3. Daily Affiliate Revenue Estimator
4. Multi-Item Wishlist Matcher
"""

import unittest
from utils.coupon_hunter import extract_coupon_discount, calculate_stacked_deal_pricing
from utils.web_push import register_push_subscription, broadcast_web_push_notification
from deal_engine.revenue_estimator import estimate_daily_affiliate_revenue
from deal_engine.wishlist_matcher import add_user_wishlist_target, match_deal_against_all_wishlists


class TestGrowthSuite(unittest.TestCase):

    # 1. Coupon Hunter & Stacked Deal Pricing
    def test_coupon_extraction_and_stacked_pricing(self):
        val, desc = extract_coupon_discount("Apply 10% coupon checkbox", 5000)
        self.assertEqual(val, 500.0)
        self.assertIn("10% Coupon", desc)

        flat_val, flat_desc = extract_coupon_discount("Apply ₹250 coupon", 2000)
        self.assertEqual(flat_val, 250.0)
        self.assertIn("Flat ₹250", flat_desc)

        stacked = calculate_stacked_deal_pricing(
            base_price=3000,
            advertised_mrp=4500,
            coupon_text="Apply ₹300 coupon",
            bank_offer_text="10% Instant Discount up to ₹500 on HDFC Cards"
        )
        self.assertEqual(stacked["coupon_discount"], 300)
        self.assertEqual(stacked["bank_discount"], 270) # 10% of 2700
        self.assertEqual(stacked["net_final_price"], 2430)
        self.assertIn("Effective Bottom Line", stacked["breakdown_text"])

    # 2. Web Push Engine
    def test_web_push_registration_and_broadcast(self):
        success = register_push_subscription({"endpoint": "https://fcm.googleapis.com/fcm/send/test_sub_1"})
        self.assertTrue(success)
        count = broadcast_web_push_notification("🔥 Test Deal Alert", "boAt Speaker at ₹1,299")
        self.assertGreaterEqual(count, 1)

    # 3. Daily Revenue Estimator
    def test_revenue_estimator(self):
        report = estimate_daily_affiliate_revenue(lookback_hours=24)
        self.assertIn("total_clicks", report)
        self.assertIn("estimated_revenue_inr", report)
        self.assertIn("summary_text", report)

    # 4. Multi-Item Wishlist Matcher
    def test_wishlist_matcher(self):
        add_user_wishlist_target("user_98765", "apple airpods pro", 19000)
        matches = match_deal_against_all_wishlists(
            title="Apple AirPods Pro (2nd Generation) with MagSafe Case",
            current_price=17990,
            buy_url="https://amazon.in/dp/B09G9BL5CP"
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["user_id"], "user_98765")
        self.assertEqual(matches[0]["savings_vs_target"], 1010)


if __name__ == "__main__":
    unittest.main()
