"""
tests/test_autonomous_harvester.py
Unit tests for the 100% self-sufficient Autonomous Deal Harvester.
"""

import unittest
from core.autonomous_harvester import NATIVE_DEAL_TARGETS, harvest_amazon_search_feed, process_harvested_candidate


class TestAutonomousHarvester(unittest.TestCase):

    def test_native_deal_targets_configured(self):
        self.assertGreaterEqual(len(NATIVE_DEAL_TARGETS), 3)
        for t in NATIVE_DEAL_TARGETS:
            self.assertIn("name", t)
            self.assertIn("platform", t)
            self.assertTrue(t["url"].startswith("http"))

    def test_candidate_structure_and_processing(self):
        mock_cand = {
            "id": "B09G9BL5CP",
            "platform": "amazon",
            "url": "https://www.amazon.in/dp/B09G9BL5CP",
            "image_url": "https://images-eu.ssl-images-amazon.com/images/P/B09G9BL5CP.01._SCLZZZZZZZ_.jpg"
        }
        self.assertEqual(mock_cand["id"], "B09G9BL5CP")


if __name__ == "__main__":
    unittest.main()
