"""
tests/test_nextgen_innovations.py
Unit tests for the 5 Next-Gen Superhit Innovations:
1. Fake Discount & Inflated MRP Hunter
2. 'Buy vs Wait' AI Advisor
3. Flash Price War Detector
4. 'Loot Streak' Daily Scratch Cards & Leaderboard
5. 5-Second Hinglish Voice Deal Generator
"""

import unittest
from unittest.mock import patch, MagicMock
from utils.price_truth import analyze_price_truth
from utils.buy_wait_advisor import get_buy_vs_wait_recommendation
from deal_engine.price_war import detect_flash_price_war
from web.gamification import process_daily_scratch, get_community_leaderboard
from deal_engine.voice_generator import generate_hinglish_script, generate_deal_audio_note


class TestNextGenInnovations(unittest.TestCase):

    # 1. Price Truth & Fake Discount Hunter
    def test_price_truth_analyzer_basic(self):
        res = analyze_price_truth("prod_101", current_price=999, advertised_mrp=2999)
        self.assertIn("status", res)
        self.assertIn("badge_text", res)
        self.assertGreater(res["real_discount_pct"], 0)

    # 2. Buy vs Wait Advisor
    def test_buy_vs_wait_recommendation(self):
        advice = get_buy_vs_wait_recommendation("prod_102", current_price=1499)
        self.assertIn("verdict", advice)
        self.assertIn("verdict_badge", advice)
        self.assertIn("VERDICT:", advice["verdict_badge"])

    # 3. Flash Price War Detector
    def test_price_war_empty_handling(self):
        res = detect_flash_price_war("", 0, "amazon")
        self.assertIsNone(res)

    # 4. Loot Streak Gamification & Leaderboard
    def test_gamification_scratch_and_leaderboard(self):
        scratch_res = process_daily_scratch(user_id="test_unlimited_user", username="TestRaider")
        self.assertEqual(scratch_res["status"], "SUCCESS")
        self.assertTrue(scratch_res["unlocked"])
        self.assertIn("reward_label", scratch_res)

        leaders = get_community_leaderboard(limit=5)
        self.assertIsInstance(leaders, list)

    # 5. Voice Deal Generator
    def test_hinglish_script_generation(self):
        script = generate_hinglish_script("boAt Aavante Bar 2.0 Speaker", 1299, 70.0, "amazon")
        self.assertIn("Bhai loot lo!", script)
        self.assertIn("1299", script)
        self.assertIn("Amazon", script)


if __name__ == "__main__":
    unittest.main()
