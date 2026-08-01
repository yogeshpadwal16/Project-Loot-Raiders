import unittest
from deal_engine.mirroring.schemas import NormalizedMessage, ButtonSchema
from deal_engine.mirroring.plugins.filter import FilterPlugin
from deal_engine.mirroring.plugins.replace import ReplacePlugin
from deal_engine.mirroring.plugins.format import FormatPlugin
from deal_engine.mirroring.plugins import apply_plugins, initialize_plugins, get_default_plugin_config

class TestMirrorPlugins(unittest.TestCase):
    def setUp(self):
        self.message = NormalizedMessage(
            channel_id="-10012345678",
            channel_name="test_channel",
            message_id=42,
            raw_text="Check out this awesome deal! Rs. 499 at Amazon. Join our channel @competitor_deals",
            caption="",
            extracted_urls=["https://amazon.in/dp/B08XYZ123"]
        )

    def test_filter_plugin_blacklist(self):
        # 1. Match blacklist keyword
        config = {"enabled": True, "blocklist_keywords": ["competitor_deals"]}
        plugin = FilterPlugin(config)
        res = plugin.apply(self.message)
        self.assertIsNone(res)

        # 2. Skip if disabled
        config["enabled"] = False
        plugin = FilterPlugin(config)
        res = plugin.apply(self.message)
        self.assertIsNotNone(res)

    def test_filter_plugin_whitelist(self):
        # Whitelist mismatch
        config = {"enabled": True, "whitelist_keywords": ["flipkart"]}
        plugin = FilterPlugin(config)
        res = plugin.apply(self.message)
        self.assertIsNone(res)

        # Whitelist match
        config["whitelist_keywords"] = ["awesome", "amazon"]
        plugin = FilterPlugin(config)
        res = plugin.apply(self.message)
        self.assertIsNotNone(res)

    def test_replace_plugin(self):
        # Replace competitor mentions
        config = {
            "enabled": True,
            "patterns": [
                {"find": r"@[a-zA-Z0-9_]+", "replace": "[CLEANED]", "regex": True},
                {"find": "awesome", "replace": "superb", "regex": False}
            ]
        }
        plugin = ReplacePlugin(config)
        res = plugin.apply(self.message)
        self.assertIsNotNone(res)
        self.assertIn("[CLEANED]", res.raw_text)
        self.assertNotIn("@competitor_deals", res.raw_text)
        self.assertIn("superb", res.raw_text)
        self.assertNotIn("awesome", res.raw_text)

    def test_format_plugin(self):
        config = {
            "enabled": True,
            "header": "[HEADER] ",
            "footer": " [FOOTER]"
        }
        plugin = FormatPlugin(config)
        res = plugin.apply(self.message)
        self.assertIsNotNone(res)
        self.assertTrue(res.raw_text.startswith("[HEADER]"))
        self.assertTrue(res.raw_text.endswith("[FOOTER]"))

    def test_pipeline_execution(self):
        # Initialize plugins with specific config
        import config.settings
        original_func = config.settings.load_settings
        
        try:
            # Inject a test mock config for plugins
            test_config = {
                "filter": {"enabled": True, "min_length": 5},
                "replace": {"enabled": True, "patterns": [{"find": "awesome", "replace": "great", "regex": False}]},
                "format": {"enabled": True, "header": "✨ ", "footer": ""},
                "ocr": {"enabled": False}
            }
            
            # Monkey patch settings for test
            def mock_load():
                return {"mirror_plugins": test_config}
            
            config.settings.load_settings = mock_load
            initialize_plugins()
            
            res = apply_plugins(self.message)
            self.assertIsNotNone(res)
            self.assertTrue(res.raw_text.startswith("✨"))
            self.assertIn("great", res.raw_text)
            self.assertNotIn("awesome", res.raw_text)
        finally:
            config.settings.load_settings = original_func
            initialize_plugins()

if __name__ == "__main__":
    unittest.main()
