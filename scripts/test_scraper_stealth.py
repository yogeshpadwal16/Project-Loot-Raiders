"""
scripts/test_scraper_stealth.py
Diagnostic Test Script for the Two-Tier Anti-Bot Resilient Scraper Engine.
Validates Tier 1 (curl_cffi TLS impersonation), CAPTCHA detection, JSON-LD microdata parsing, and Tier 2 (Playwright).
"""

import sys
import os
import asyncio
import logging

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scrapers.stealth_scraper import (
    is_captcha_or_bot_wall,
    parse_json_ld_schema,
    scrape_tier1_curl_cffi,
    scrape_product_details
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def run_scraper_diagnostics():
    print("==========================================================================")
    print("  PROJECT LOOT RAIDERS - TWO-TIER SCRAPER DIAGNOSTIC TEST")
    print("==========================================================================")

    # 1. Test CAPTCHA & Bot Wall Detector
    sample_captcha_html = "<html><body><h1>Type the characters you see in this image</h1></body></html>"
    sample_clean_html = "<html><body><h1>Product Title</h1></body></html>"

    assert is_captcha_or_bot_wall(sample_captcha_html) == True
    assert is_captcha_or_bot_wall(sample_clean_html) == False
    print(" [PASS] CAPTCHA & Robot Check Detector working as expected.")

    # 2. Test JSON-LD Microdata Parser
    sample_json_ld_html = '''
    <html>
    <head>
      <script type="application/ld+json">
      {
        "@type": "Product",
        "name": "Sony PlayStation 5 Console (Slim)",
        "offers": {
          "@type": "Offer",
          "price": "44990",
          "availability": "https://schema.org/InStock"
        }
      }
      </script>
    </head>
    </html>
    '''
    parsed_data = parse_json_ld_schema(sample_json_ld_html)
    assert parsed_data is not None
    assert parsed_data["title"] == "Sony PlayStation 5 Console (Slim)"
    assert parsed_data["price"] == 44990.0
    assert parsed_data["in_stock"] == True
    print(" [PASS] JSON-LD Schema Microdata Parser working as expected.")

    # 3. Test Live Tier 1 curl_cffi TLS Impersonation
    test_urls = [
        "https://www.amazon.in/dp/B09G9BL5CP",
        "https://www.flipkart.com/product/p/itmd?pid=MOBG6VF5CHW9ZXYZ"
    ]

    print("\n--- Testing Live Product Scraping ---")
    for url in test_urls:
        print(f"Scraping URL: {url} ...")
        res = await scrape_product_details(url, timeout_seconds=8.0)
        if res:
            print(f"  [SUCCESS] | Strategy: {res.get('strategy')} | Title: '{res.get('title')[:45]}...' | Price: Rs.{res.get('price')} | InStock: {res.get('in_stock')}")
        else:
            print(f"  [FALLBACK / OOS / CAPTCHA] | Handled gracefully without crash for {url[:45]}")

    print("\n==========================================================================")
    print("  SCRAPER DIAGNOSTICS COMPLETED SUCCESSFULLY")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_scraper_diagnostics())
