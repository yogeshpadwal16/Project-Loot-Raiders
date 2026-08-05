import os
import unittest
from unittest.mock import MagicMock, patch
import httpx
from io import BytesIO

# Import target modules
from deal_engine.mirroring.processor import DealMirrorProcessor
from web.server import ScraperAPIHandler, DASHBOARD_DIR
from deal_engine.notifier import _process_and_broadcast_alert_job

class TestFixedFunctions(unittest.TestCase):
    
    # ---------------------------------------------------------
    # TEST 1: HTTPX Redirect Resolver Link Expansion
    # ---------------------------------------------------------
    @patch("httpx.Client")
    def test_expand_url_with_retry_success(self, mock_client_class):
        # Setup mocks for httpx client
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        # Scenario A: Head request resolves successfully with redirect location
        # Target URL must contain a store domain (e.g. amazon.in) to bypass Playwright JS fallback
        mock_head_res = MagicMock()
        mock_head_res.status_code = 200
        mock_head_res.url = httpx.URL("https://www.amazon.in/dp/B08XYZ123")
        mock_client.head.return_value = mock_head_res
        
        processor = DealMirrorProcessor(queue=MagicMock())
        expanded_url = processor._expand_url_with_retry("https://amzn.to/shorturl")
        
        self.assertEqual(expanded_url, "https://www.amazon.in/dp/B08XYZ123")
        mock_client.head.assert_called_once_with("https://amzn.to/shorturl")

    @patch("httpx.Client")
    def test_expand_url_with_retry_head_fail_get_fallback(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        # Scenario B: Head request returns 405 (Not Allowed), fallback to GET request
        mock_head_res = MagicMock()
        mock_head_res.status_code = 405
        mock_head_res.url = httpx.URL("https://amzn.to/shorturl")
        mock_client.head.return_value = mock_head_res
        
        mock_get_res = MagicMock()
        mock_get_res.status_code = 200
        mock_get_res.url = httpx.URL("https://www.flipkart.com/product/p/itm123")
        mock_client.get.return_value = mock_get_res
        
        processor = DealMirrorProcessor(queue=MagicMock())
        expanded_url = processor._expand_url_with_retry("https://amzn.to/shorturl")
        
        self.assertEqual(expanded_url, "https://www.flipkart.com/product/p/itm123")
        mock_client.head.assert_called_once()
        mock_client.get.assert_called_once_with("https://amzn.to/shorturl")

    # ---------------------------------------------------------
    # TEST 2: Path Traversal Security Checks in server.py
    # ---------------------------------------------------------
    def test_do_get_path_traversal_prevention(self):
        # We instantiate a mock Request Handler
        mock_handler = MagicMock(spec=ScraperAPIHandler)
        mock_handler.path = "/../settings.json"
        mock_handler.wfile = BytesIO()
        mock_handler.headers = {}
        
        # Bind the real method logic of is_authorized and do_GET
        mock_handler.is_authorized = lambda: True
        
        # Trigger the real do_GET method code on our mocked handler
        ScraperAPIHandler.do_GET(mock_handler)
        
        # The path resolves to DASHBOARD_DIR/../settings.json which is outside dashboard scope.
        # It must result in 403 Forbidden
        mock_handler.send_response.assert_called_with(403)
        response_body = mock_handler.wfile.getvalue().decode('utf-8')
        self.assertIn("Forbidden: Path traversal detected.", response_body)

    def test_do_get_safe_path_allowed(self):
        # Safe path inside the dashboard directory
        mock_handler = MagicMock(spec=ScraperAPIHandler)
        mock_handler.path = "/index.html"
        mock_handler.wfile = BytesIO()
        mock_handler.headers = {}
        
        mock_handler.is_authorized = lambda: True
        
        # Mock _serve_static to avoid hitting real file read
        mock_handler._serve_static = MagicMock()
        
        # Trigger do_GET
        ScraperAPIHandler.do_GET(mock_handler)
        
        # Safe paths must not raise 403 or 401
        self.assertNotEqual(mock_handler.send_response.call_args_list[0][0][0] if mock_handler.send_response.call_args else None, 403)

    # ---------------------------------------------------------
    # TEST 3: Apprise Image Downloader and Attachment Cleanup
    # ---------------------------------------------------------
    @patch("apprise.Apprise")
    @patch("requests.get")
    @patch("deal_engine.notifier.load_settings")
    @patch("deal_engine.notifier.check_and_dispatch_personal_alerts")
    @patch("deal_engine.notifier.check_deal_against_keyword_alerts")
    def test_apprise_notifier_image_attachment(self, mock_kw_alerts, mock_personal_alerts, mock_load_settings, mock_get, mock_apprise_class):
        # Configure settings to skip Telegram/Discord/Email direct alerts
        mock_load_settings.return_value = {
            "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
            "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
            "notification_uris": ["tgram://12345/67890"]
        }
        
        # Mock personal alerts and keyword wishlists to prevent hitting database
        mock_personal_alerts.return_value = None
        mock_kw_alerts.return_value = None
        
        # Mock requests.get to return a mock binary image stream
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.content = b"fake-image-bytes"
        mock_get.return_value = mock_res
        
        # Mock apprise notifier instance
        mock_apprise = MagicMock()
        mock_apprise.notify.return_value = True
        mock_apprise.__len__.return_value = 1  # Crucial to bypass `len(apobj) > 0` check
        mock_apprise_class.return_value = mock_apprise
        
        # Define alert job details
        job = {
            "platform": "amazon",
            "title": "Test Deal Item",
            "price": 1000,
            "mrp": 2000,
            "discount": 50.0,
            "image_url": "https://images-na.ssl-images-amazon.com/images/I/sample.jpg",
            "url": "https://www.amazon.in/dp/B00SAMPLE",
            "is_verified_low": True,
            "deal_score": 90.0,
            "unique_id": "B00SAMPLE",
            "retries": 0
        }
        
        # Run alert broadcast task
        success = _process_and_broadcast_alert_job(job)
        
        # Verify apprise notify was called
        self.assertTrue(success)
        mock_apprise.notify.assert_called_once()
        
        # Ensure temporary attachment file path was passed and then cleaned up
        kwargs = mock_apprise.notify.call_args[1]
        attach_path = kwargs.get("attach")
        self.assertIsNotNone(attach_path)
        self.assertTrue(attach_path.endswith(".jpg"))
        
        # Confirm cleanup: file must be deleted from filesystem
        self.assertFalse(os.path.exists(attach_path))

    # ---------------------------------------------------------
    # TEST 4: Quality Firewall Validation and Logs
    # ---------------------------------------------------------
    def test_quality_firewall_validation_and_logs(self):
        try:
            from compliance_guard import check_quality_firewall
        except ImportError:
            from loot_raiders.compliance_guard import check_quality_firewall

        # Test Case A: Invalid price (0)
        with self.assertLogs(level="WARNING") as log_watcher:
            res = check_quality_firewall(0, "Apple iPhone 15 Pro", "https://m.media-amazon.com/images/I/sample.jpg")
            self.assertFalse(res)
            self.assertTrue(any("[REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)]" in log for log in log_watcher.output))

        # Test Case B: Dummy title ("Product Deal")
        with self.assertLogs(level="WARNING") as log_watcher:
            res = check_quality_firewall(499, "Product Deal", "https://m.media-amazon.com/images/I/sample.jpg")
            self.assertFalse(res)
            self.assertTrue(any("[REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)]" in log for log in log_watcher.output))

        # Test Case C: Generic store logo image
        with self.assertLogs(level="WARNING") as log_watcher:
            res = check_quality_firewall(499, "Apple iPhone 15 Pro", "https://m.media-amazon.com/images/I/amazon-logo.png")
            self.assertFalse(res)
            self.assertTrue(any("[REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)]" in log for log in log_watcher.output))

        # Test Case D: Valid payload
        res = check_quality_firewall(499, "Apple iPhone 15 Pro", "https://m.media-amazon.com/images/I/sample.jpg")
        self.assertTrue(res)

if __name__ == "__main__":
    unittest.main()

