import unittest
from fastapi.testclient import TestClient
from app.web.server import app
from app.core.bot_controller import bot_controller
from app.config import config

class TestWebEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_index_html(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("IQ Option Trading Bot", res.text)
        self.assertIn("Martingale", res.text)

    def test_02_status_api(self):
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("is_running", data)
        self.assertIn("risk_summary", data)
        self.assertEqual(data["risk_summary"]["max_steps"], config.get_max_steps())

    def test_03_scanner_api(self):
        res = self.client.get("/api/scanner")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertGreaterEqual(data[0]["payout"], 0.80)

    def test_04_bot_start_stop(self):
        # Start bot
        res_start = self.client.post("/api/bot/start")
        self.assertEqual(res_start.status_code, 200)
        self.assertTrue(bot_controller.is_running)

        # Check status while running
        res_status = self.client.get("/api/status")
        self.assertTrue(res_status.json()["is_running"])

        # Stop bot
        res_stop = self.client.post("/api/bot/stop")
        self.assertEqual(res_stop.status_code, 200)
        self.assertFalse(bot_controller.is_running)

    def test_05_config_update(self):
        payload = {
            "mm_mode": "COMPOUND",
            "base_bet": 2.0,
            "compound_steps": 2,
            "martingale_steps": 5,
            "daily_stop_loss": 60.0,
            "daily_take_profit": 40.0
        }
        res = self.client.post("/api/config", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

    def test_06_websocket(self):
        with self.client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            self.assertIn("status", data)
            self.assertIn("trades", data)
            self.assertIn("scanner", data)

if __name__ == "__main__":
    unittest.main()
