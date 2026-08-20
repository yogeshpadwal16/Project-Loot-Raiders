"""
tests/test_image_engine.py
Unit tests for the multi-retailer Image Extractor & Premium Deal Card Generator.
"""

import os
import unittest
from utils.image_extractor import (
    extract_amazon_asin,
    get_amazon_highres_image_url,
    upscale_flipkart_image_url,
    upscale_myntra_image_url,
    resolve_best_product_image
)
from utils.image_generator import generate_deal_image


class TestImageEngine(unittest.TestCase):

    def test_amazon_asin_extraction_and_cdn(self):
        url = "https://www.amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY/ref=sr_1_1"
        asin = extract_amazon_asin(url)
        self.assertEqual(asin, "B0CHX1W1XY")
        
        cdn_url = get_amazon_highres_image_url(asin)
        self.assertIn("B0CHX1W1XY.01._SCLZZZZZZZ_.jpg", cdn_url)

    def test_flipkart_and_myntra_upscaling(self):
        fk_url = "https://rukminim1.flixcart.com/image/128/128/xif0q/mobile/k/l/f/-original-imagtc5fz9spysyk.jpeg"
        upscaled_fk = upscale_flipkart_image_url(fk_url)
        self.assertIn("/832/832/", upscaled_fk)

        myntra_url = "https://assets.myntassets.com/dpr_1.5,q_60,w_200,c_limit,fl_progressive/assets/images/123/img.jpg"
        upscaled_myntra = upscale_myntra_image_url(myntra_url)
        self.assertIn("w_800", upscaled_myntra)

    def test_best_image_resolver(self):
        res = resolve_best_product_image(
            product_url="https://www.amazon.in/dp/B09G9BL5CP",
            platform="amazon"
        )
        self.assertIsNotNone(res)
        self.assertIn("B09G9BL5CP", res)

    def test_premium_deal_card_generator(self):
        card_path = generate_deal_image(
            unique_id="test_deal_lux",
            platform="amazon",
            title="Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
            price=24990,
            mrp=34990,
            discount=28.5,
            deal_score=94.0,
            is_verified_low=True
        )
        self.assertIsNotNone(card_path)
        self.assertTrue(os.path.exists(card_path))
        self.assertGreater(os.path.getsize(card_path), 5000)
        
        # Cleanup
        try:
            os.remove(card_path)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
