import unittest
from utils.proxy_validator import validate_proxy, get_validated_proxy_pool, get_next_working_proxy

class TestProxyValidator(unittest.TestCase):
    def test_invalid_proxy_fails(self):
        from unittest.mock import patch
        import requests
        with patch("requests.head", side_effect=requests.exceptions.ConnectionError("Proxy offline")):
            self.assertFalse(validate_proxy("127.0.0.2:9999"))

    def test_pool_and_fallback_rotation(self):
        from unittest.mock import patch
        import requests
        settings = {
            "proxy_list": [
                "127.0.0.2:9999",
                "127.0.0.3:9999"
            ]
        }
        with patch("requests.head", side_effect=requests.exceptions.ConnectionError("Proxy offline")):
            pool = get_validated_proxy_pool(settings)
            self.assertEqual(len(pool), 0)
            proxy = get_next_working_proxy(settings)
            self.assertIsNotNone(proxy)
            self.assertTrue(proxy.startswith("http://127.0.0."))

if __name__ == "__main__":
    unittest.main()
