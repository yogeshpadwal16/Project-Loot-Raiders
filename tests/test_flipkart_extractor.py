import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractors.flipkart import (
    extract_flipkart_data_from_html,
    sanitize_flipkart_title,
    is_generic_or_search_title,
    upgrade_flipkart_image_url
)
from web.auth_engine import format_e164_phone, mask_mobile_number

MOCK_FLIPKART_SNEAKER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Neu Pager Men Stylish & Comfortable Sneakers - Buy Online</title>
    <meta property="og:title" content="Neu Pager Men Stylish &amp; Comfortable Sneakers: Buy Online at Best Prices in India | Flipkart.com" />
    <meta property="og:image" content="https://rukminim2.flixcart.com/image/128/128/xif0q/shoe/7/2/m/6-sneaker-neu-pager-white-original-imagp87xyz.jpeg?q=70" />
</head>
<body>
    <input type="text" name="q" class="Pke_EE" value="clearance sale" />
    
    <div class="product-wrapper">
        <span class="mEh187">Neu Pager</span>
        <h1 class="B_NuCI">
            <span class="VU-ZEz">Neu Pager Men Stylish &amp; Comfortable Sneakers | Lightweight | Trendy Walking Shoes</span>
        </h1>
        
        <div class="image-gallery">
            <div class="_2r_T1I">
                <img class="_396cs4 DByuf4" 
                     src="https://rukminim2.flixcart.com/image/128/128/xif0q/shoe/7/2/m/6-sneaker-neu-pager-white-original-imagp87xyz.jpeg?q=70" 
                     data-src="https://rukminim2.flixcart.com/image/416/416/xif0q/shoe/7/2/m/6-sneaker-neu-pager-white-original-imagp87xyz.jpeg?q=70"
                     srcset="https://rukminim2.flixcart.com/image/128/128/xif0q/shoe/7/2/m/6-sneaker-neu-pager-white-original-imagp87xyz.jpeg 128w, https://rukminim2.flixcart.com/image/832/832/xif0q/shoe/7/2/m/6-sneaker-neu-pager-white-original-imagp87xyz.jpeg 832w"
                     alt="Neu Pager Sneaker" />
            </div>
        </div>
        
        <div class="pricing-container">
            <div class="Nx9bqj CxhGGd">₹373</div>
            <div class="yRaY8j _18RivS">₹1,499</div>
            <div class="UkUFwK"><span>75% off</span></div>
        </div>
        
        <div class="bank-offers-subtext">
            <span>Special Price: Get extra ₹20 off (price inclusive of cashback/coupon ₹353)</span>
            <span>Exchange offer up to ₹2,999</span>
        </div>
    </div>
</body>
</html>
"""


class TestFlipkartExtractor(unittest.TestCase):
    def test_mock_sneaker_extraction(self):
        """Verify Sneaker fixture correctly extracts Title, Image, Prices, Discount without bank pollution."""
        page_url = "https://www.flipkart.com/neu-pager-men-sneakers/p/itme987654321012"
        deal = extract_flipkart_data_from_html(MOCK_FLIPKART_SNEAKER_HTML, page_url)
        
        self.assertIsNotNone(deal, "Extraction returned None")
        
        # 1. Product Title
        self.assertTrue(deal["title"].startswith("Neu Pager Men"), f"Title was: {deal['title']}")
        self.assertNotIn("clearance sale", deal["title"].lower())
        self.assertNotIn("|", deal["title"])
        
        # 2. Brand
        self.assertEqual(deal["brand"], "Neu Pager")
        
        # 3. Selling Price & MRP (must ignore ₹353 and ₹2,999)
        self.assertEqual(deal["currentPrice"], 373.0)
        self.assertEqual(deal["originalPrice"], 1499.0)
        
        # 4. Discount Percentage (strictly Math.round(((1499 - 373) / 1499) * 100) = 75)
        self.assertEqual(deal["discountPercentage"], 75)
        
        # 5. Image Resolution Upgrade
        self.assertIn("832/832", deal["imageUrl"])
        self.assertNotIn("128/128", deal["imageUrl"])
        self.assertIn("rukminim2.flixcart.com", deal["imageUrl"])
        
        # 6. Merchant
        self.assertEqual(deal["merchant"], "Flipkart")

    def test_generic_title_rejection(self):
        """Verify search breadcrumbs / generic banners are rejected."""
        self.assertTrue(is_generic_or_search_title("Clearance Sale"))
        self.assertTrue(is_generic_or_search_title("Showing 1 - 24 of 1000"))
        self.assertTrue(is_generic_or_search_title("Trending Deals"))
        self.assertFalse(is_generic_or_search_title("Apple iPhone 15 (128 GB) - Blue"))

    def test_image_url_upgrade_and_filter(self):
        """Verify resolution upgrade and placeholder rejection."""
        # Generic flixcart logo must be rejected
        logo_url = "https://static-assets-web.flixcart.com/fk-p-linchpin-web/fk-cp-zion/img/flipkart-plus_8d85f4.png"
        self.assertEqual(upgrade_flipkart_image_url(logo_url), "")
        
        # Standard product thumbnail must be upgraded to 832x832
        thumb_url = "https://rukminim2.flixcart.com/image/312/312/xif0q/mobile/k/l/f/-original-imagtc5fz9spysyk.jpeg"
        upgraded = upgrade_flipkart_image_url(thumb_url)
        self.assertIn("832/832", upgraded)

    def test_e164_phone_formatting(self):
        """Verify E.164 phone formatting for Indian mobile numbers."""
        self.assertEqual(format_e164_phone("7302427167"), "+917302427167")
        self.assertEqual(format_e164_phone("07302427167"), "+917302427167")
        self.assertEqual(format_e164_phone("917302427167"), "+917302427167")
        self.assertEqual(format_e164_phone("+91 73024 27167"), "+917302427167")
        self.assertEqual(mask_mobile_number("+917302427167"), "+91 ******7167")


if __name__ == "__main__":
    unittest.main()
