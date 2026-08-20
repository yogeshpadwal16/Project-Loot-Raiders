"""
Unit tests for Loot Brain Dashboard & Control Center API.
"""

import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from loot_brain.dashboard_api import router as brain_router
from web.server import brain_store, brain_registry, brain_orchestrator, brain_subconscious

app = FastAPI()
app.include_router(brain_router)
client = TestClient(app)


class TestLootBrainDashboardAPI(unittest.TestCase):

    def test_brain_status_endpoint(self):
        response = client.get("/api/v1/brain/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ONLINE")
        self.assertGreaterEqual(data["registered_agents_count"], 4)

    def test_brain_memories_endpoint(self):
        response = client.get("/api/v1/brain/memories")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_brain_pipeline_process_endpoint(self):
        payload = {
            "title": "Bose QuietComfort 45",
            "original_price": 25000.0,
            "deal_price": 15000.0,  # 40% OFF
            "merchant": "Amazon",
            "url": "https://www.amazon.in/dp/B098765432",
            "in_stock": True,
        }
        response = client.post("/api/v1/brain/pipeline/process", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
