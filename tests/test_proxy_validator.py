import unittest
from utils.proxy_validator import validate_proxy, get_validated_proxy_pool, get_next_working_proxy

class TestProxyValidator(unittest.TestCase):
    def test_invalid_proxy_fails(self):
        # Using a dummy offline IP that should timeout/fail immediately
        self.assertFalse(validate_proxy("127.0.0.2:9999"))

    def test_pool_and_fallback_rotation(self):
        # Configure test settings
        settings = {
            "proxy_list": [
                "127.0.0.2:9999",
                "127.0.0.3:9999"
            ]
        }
        
        # All proxies are offline so validated pool should be empty
        pool = get_validated_proxy_pool(settings)
        self.assertEqual(len(pool), 0)
        
        # Falling back to random selection if all are offline
        proxy = get_next_working_proxy(settings)
        self.assertIsNotNone(proxy)
        self.assertTrue(proxy.startswith("http://127.0.0."))

if __name__ == "__main__":
    unittest.main()
