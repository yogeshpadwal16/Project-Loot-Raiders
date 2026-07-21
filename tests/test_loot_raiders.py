import unittest
import sys
import os

# Adjust path to import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.parser import extract_amazon_asin, extract_flipkart_pid, calculate_true_discount
from utils.affiliate import get_best_affiliate_url, generate_auto_cart_url
from deal_engine.scorer import calculate_deal_score, calculate_cancellation_risk

class TestLootRaidersCore(unittest.TestCase):
    
    def test_amazon_asin_extraction(self):
        urls = [
            "https://www.amazon.in/dp/B0CX1G2Y4C",
            "https://www.amazon.in/gp/product/B0CX1G2Y4C?ref_=nav_em_all_T1",
            "https://www.amazon.in/dp/B0CX1G2Y4C/ref=sspa_dk_detail_2",
            "https://www.amazon.in/gp/product/B0CX1G2Y4C"
        ]
        for url in urls:
            self.assertEqual(extract_amazon_asin(url), "B0CX1G2Y4C")
            
    def test_flipkart_pid_extraction(self):
        urls = [
            "https://www.flipkart.com/product/p/itm?pid=TSHG4V2NDFEYDKTG",
            "https://www.flipkart.com/indiafreestuff/p/indiafreestuff?pid=TSHG4V2NDFEYDKTG",
            "https://www.flipkart.com/p/TSHG4V2NDFEYDKTG"
        ]
        for url in urls:
            self.assertEqual(extract_flipkart_pid(url), "TSHG4V2NDFEYDKTG")

    def test_calculate_true_discount(self):
        # 1. Test standard currency-prefixed pricing text
        text_1 = "Loot price: ₹499 MRP: ₹1999 (75% OFF)"
        price, mrp, discount = calculate_true_discount(text_1)
        self.assertEqual(price, 499)
        self.assertEqual(mrp, 1999)
        self.assertAlmostEqual(discount, 75.0375, places=2)
        
        # 2. Test text without currency but clear numbers
        text_2 = "Selling at 1500 instead of 3000"
        price, mrp, discount = calculate_true_discount(text_2)
        self.assertEqual(price, 1500)
        self.assertEqual(mrp, 3000)
        self.assertEqual(discount, 50.0)

    def test_affiliate_url_generation(self):
        settings = {
            "amazon_tag": "test-tag-21",
            "flipkart_affid": "testflip",
            "cuelinks_pub_id": "12345",
            "earnkaro_pub_id": "67890"
        }
        
        # Amazon direct routing
        amazon_url = "https://www.amazon.in/dp/B0CX1G2Y4C"
        aff_amazon = get_best_affiliate_url(amazon_url, "amazon", settings)
        self.assertIn("tag=test-tag-21", aff_amazon)
        
        # Ajio should route to EarnKaro (high commission rate 10% vs 8%)
        ajio_url = "https://www.ajio.com/p/12345"
        aff_ajio = get_best_affiliate_url(ajio_url, "ajio", settings)
        self.assertIn("earnkaro.com", aff_ajio)
        self.assertIn("pub_id=67890", aff_ajio)
        
        # Myntra should route to Cuelinks (high commission rate 6% vs 5%)
        myntra_url = "https://www.myntra.com/p/12345"
        aff_myntra = get_best_affiliate_url(myntra_url, "myntra", settings)
        self.assertIn("cuelinks.com", aff_myntra)
        self.assertIn("pub_id=12345", aff_myntra)

    def test_auto_cart_generation(self):
        settings = {"amazon_tag": "test-tag-21", "flipkart_affid": "testflip"}
        
        # Amazon auto-cart link
        amazon_url = "https://www.amazon.in/dp/B0CX1G2Y4C"
        cart_amazon = generate_auto_cart_url(amazon_url, "amazon", settings)
        self.assertEqual(cart_amazon, "https://www.amazon.in/gp/aws/cart/add.html?ASIN.1=B0CX1G2Y4C&Quantity.1=1&tag=test-tag-21")
        
        # Flipkart auto-cart link
        flipkart_url = "https://www.flipkart.com/p/TSHG4V2NDFEYDKTG"
        cart_flipkart = generate_auto_cart_url(flipkart_url, "flipkart", settings)
        self.assertEqual(cart_flipkart, "https://www.flipkart.com/co/add-to-cart?pid=TSHG4V2NDFEYDKTG&affid=testflip")

    def test_deal_scoring_and_cancel_risk(self):
        # High cancellation risk for expensive glitch items
        risk_high = calculate_cancellation_risk("amazon", 999, 15000, 93.3, "Apple iPhone 15 Pro Max")
        self.assertEqual(risk_high, 95.0)
        
        # Low cancellation risk for normal deals
        risk_low = calculate_cancellation_risk("amazon", 800, 1000, 20.0, "Jockey T-Shirt")
        self.assertEqual(risk_low, 5.0)
        
        # Base scoring calculation check
        score = calculate_deal_score("amazon_master_lightning_deals", 499, 1999, 75.0, True, is_lightning=True)
        self.assertTrue(45.0 <= score <= 100.0)

class TestSettingsLoader(unittest.TestCase):
    """Tests for config/settings.py"""
    
    def test_load_settings_returns_dict(self):
        from config.settings import load_settings
        settings = load_settings()
        self.assertIsInstance(settings, dict)
    
    def test_settings_has_required_keys(self):
        from config.settings import load_settings
        settings = load_settings()
        required_keys = [
            'telegram_bot_token', 'gemini_api_key', 'min_discount',
            'min_deal_price', 'blocklist_keywords', 'scoring_rules'
        ]
        for key in required_keys:
            self.assertIn(key, settings, f"Missing required setting: {key}")
    
    def test_blocklist_is_list(self):
        from config.settings import load_settings
        settings = load_settings()
        self.assertIsInstance(settings.get('blocklist_keywords', []), list)
    
    def test_scoring_rules_has_weights(self):
        from config.settings import load_settings
        settings = load_settings()
        scoring = settings.get('scoring_rules', {})
        self.assertIn('weights', scoring)
        self.assertIn('min_publish_score', scoring)

    def test_min_discount_is_numeric(self):
        from config.settings import load_settings
        settings = load_settings()
        self.assertIsInstance(settings['min_discount'], (int, float))
        self.assertGreater(settings['min_discount'], 0)


class TestDatabaseModels(unittest.TestCase):
    """Tests for knowledge_base/models.py schema integrity"""
    
    def test_product_model_columns(self):
        from knowledge_base.models import Product
        required_columns = ['id', 'platform', 'title', 'image_url', 'url', 'created_at']
        table_columns = [c.name for c in Product.__table__.columns]
        for col in required_columns:
            self.assertIn(col, table_columns, f"Product model missing column: {col}")
    
    def test_price_history_model_columns(self):
        from knowledge_base.models import PriceHistory
        required_columns = ['id', 'product_id', 'price', 'mrp', 'discount', 'deal_score', 'timestamp']
        table_columns = [c.name for c in PriceHistory.__table__.columns]
        for col in required_columns:
            self.assertIn(col, table_columns, f"PriceHistory model missing column: {col}")
    
    def test_click_log_model_columns(self):
        from knowledge_base.models import ClickLog
        required_columns = ['id', 'product_id', 'title', 'ip', 'user', 'timestamp']
        table_columns = [c.name for c in ClickLog.__table__.columns]
        for col in required_columns:
            self.assertIn(col, table_columns, f"ClickLog model missing column: {col}")
    
    def test_selector_matrix_model_columns(self):
        from knowledge_base.models import SelectorMatrix
        required_columns = ['id', 'platform', 'url', 'card_selector', 'title_selector', 'link_selector']
        table_columns = [c.name for c in SelectorMatrix.__table__.columns]
        for col in required_columns:
            self.assertIn(col, table_columns, f"SelectorMatrix model missing column: {col}")
    
    def test_user_score_model_columns(self):
        from knowledge_base.models import UserScore
        required_columns = ['user_id', 'username', 'points', 'voted_count', 'referrals_count']
        table_columns = [c.name for c in UserScore.__table__.columns]
        for col in required_columns:
            self.assertIn(col, table_columns, f"UserScore model missing column: {col}")

    def test_channel_growth_log_model(self):
        from knowledge_base.models import ChannelGrowthLog
        required_columns = ['id', 'subscribers', 'timestamp']
        table_columns = [c.name for c in ChannelGrowthLog.__table__.columns]
        for col in required_columns:
            self.assertIn(col, table_columns, f"ChannelGrowthLog model missing column: {col}")


class TestParserEdgeCases(unittest.TestCase):
    """Extended edge case tests for utils/parser.py"""
    
    def test_amazon_asin_invalid_url(self):
        self.assertIsNone(extract_amazon_asin("https://www.flipkart.com/product/p/123"))
    
    def test_amazon_asin_empty_string(self):
        self.assertIsNone(extract_amazon_asin(""))
    
    def test_amazon_asin_no_path(self):
        self.assertIsNone(extract_amazon_asin("https://www.amazon.in/"))
    
    def test_flipkart_pid_invalid_url(self):
        self.assertIsNone(extract_flipkart_pid("https://www.amazon.in/dp/B0CX1G2Y4C"))
    
    def test_flipkart_pid_empty_string(self):
        self.assertIsNone(extract_flipkart_pid(""))
    
    def test_flipkart_pid_no_pid(self):
        self.assertIsNone(extract_flipkart_pid("https://www.flipkart.com/electronics"))
    
    def test_discount_empty_text(self):
        price, mrp, discount = calculate_true_discount("")
        self.assertIsNone(price)
        self.assertIsNone(mrp)
        self.assertIsNone(discount)
    
    def test_discount_none_text(self):
        price, mrp, discount = calculate_true_discount(None)
        self.assertIsNone(price)
        self.assertIsNone(mrp)
        self.assertIsNone(discount)
    
    def test_discount_single_price_only(self):
        # Only one price detected — cannot calculate discount
        price, mrp, discount = calculate_true_discount("₹499 only")
        # Should return the price but no discount or return None for all
        # Either outcome is acceptable; test that it doesn't crash
        self.assertTrue(True)  # No exception thrown
    
    def test_discount_with_commas(self):
        text = "₹1,499 MRP ₹4,999"
        price, mrp, discount = calculate_true_discount(text)
        self.assertEqual(price, 1499)
        self.assertEqual(mrp, 4999)
        self.assertAlmostEqual(discount, 70.014, places=1)


class TestScraperState(unittest.TestCase):
    """Tests for core/engine.py system state and plugin registry"""
    
    def test_retailer_plugins_count(self):
        from core.engine import RETAILER_PLUGINS
        self.assertEqual(len(RETAILER_PLUGINS), 7, "Expected 7 retailer plugins")
    
    def test_retailer_plugins_has_all_platforms(self):
        from core.engine import RETAILER_PLUGINS
        expected_platforms = ['amazon', 'flipkart', 'myntra', 'ajio', 'meesho', 'tatacliq', 'jiomart']
        for platform in expected_platforms:
            self.assertIn(platform, RETAILER_PLUGINS, f"Missing retailer plugin: {platform}")
    
    def test_scraper_state_has_required_keys(self):
        from core.engine import scraper_state
        required_keys = ['is_running', 'scans_completed', 'last_scan_time', 'uptime_start', 'scan_trigger', 'crawler_health']
        for key in required_keys:
            self.assertIn(key, scraper_state, f"Missing scraper state key: {key}")
    
    def test_scraper_state_initial_values(self):
        from core.engine import scraper_state
        self.assertIsInstance(scraper_state['is_running'], bool)
        self.assertIsInstance(scraper_state['scans_completed'], int)
        self.assertIsInstance(scraper_state['crawler_health'], dict)


class TestServiceWorkerAssets(unittest.TestCase):
    """Tests for PWA asset completeness"""
    
    def test_manifest_exists(self):
        manifest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard', 'manifest.json')
        self.assertTrue(os.path.exists(manifest_path), "PWA manifest.json is missing")
    
    def test_service_worker_exists(self):
        sw_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard', 'sw.js')
        self.assertTrue(os.path.exists(sw_path), "Service worker sw.js is missing")
    
    def test_manifest_is_valid_json(self):
        import json
        manifest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard', 'manifest.json')
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        self.assertIn('name', manifest)
        self.assertIn('short_name', manifest)
        self.assertIn('start_url', manifest)
        self.assertIn('icons', manifest)
        self.assertIsInstance(manifest['icons'], list)
        self.assertGreaterEqual(len(manifest['icons']), 2)
    
    def test_pwa_icons_exist(self):
        dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard')
        self.assertTrue(os.path.exists(os.path.join(dashboard_dir, 'icon-192.png')), "icon-192.png missing")
        self.assertTrue(os.path.exists(os.path.join(dashboard_dir, 'icon-512.png')), "icon-512.png missing")

    def test_manifest_has_shortcuts(self):
        import json
        manifest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard', 'manifest.json')
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        self.assertIn('shortcuts', manifest)
        self.assertGreaterEqual(len(manifest['shortcuts']), 2)


if __name__ == "__main__":
    unittest.main()
