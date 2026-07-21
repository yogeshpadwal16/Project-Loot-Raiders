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

if __name__ == "__main__":
    unittest.main()
