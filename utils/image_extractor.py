"""
utils/image_extractor.py
Multi-Retailer High-Resolution Product Image Extraction Engine.
Extracts, repairs, and upscales product images from Amazon, Flipkart, Myntra, Ajio, Meesho, and TataCliq.
"""

import re
import logging
import urllib.parse
import requests
from typing import Optional

logger = logging.getLogger("loot_raiders.image_extractor")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def extract_amazon_asin(url_or_id: str) -> Optional[str]:
    """Extracts 10-character Amazon ASIN from any URL or string."""
    if not url_or_id:
        return None
    match = re.search(r'(?:/dp/|/gp/product/|/d/|/ASIN/|/)([A-Z0-9]{10})(?:[/?&]|$)', url_or_id)
    if match:
        return match.group(1)
    if len(url_or_id) == 10 and url_or_id.isalnum():
        return url_or_id
    return None


def get_amazon_highres_image_url(asin: str) -> str:
    """Generates high-res permanent Amazon CDN image URL from ASIN."""
    return f"https://images-eu.ssl-images-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg"


def upscale_flipkart_image_url(img_url: str) -> str:
    """Upscales low-res Flipkart thumbnail URLs (e.g. /128/128/) to high-res (832x832)."""
    if not img_url:
        return img_url
    return re.sub(r'/\d+/\d+/', '/832/832/', img_url)


def upscale_myntra_image_url(img_url: str) -> str:
    """Upscales Myntra asset URLs to high-res 800px."""
    if not img_url:
        return img_url
    return re.sub(r'w_\d+', 'w_800', img_url)


def scrape_page_opengraph_image(url: str) -> Optional[str]:
    """Extracts og:image or twitter:image from a retailer product page."""
    if not url or not url.startswith("http"):
        return None
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            html = res.text
            # Look for og:image or twitter:image
            og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
            if not og_match:
                og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.I)
            if not og_match:
                og_match = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
            
            if og_match:
                found_url = og_match.group(1).strip()
                if found_url.startswith("http") and not found_url.endswith(".svg"):
                    return found_url
    except Exception as e:
        logger.debug(f"OpenGraph scrape failed for {url[:50]}: {e}")
    return None


def resolve_best_product_image(
    raw_img_url: Optional[str] = None,
    product_url: Optional[str] = None,
    platform: str = "amazon",
    unique_id: Optional[str] = None
) -> Optional[str]:
    """
    Intelligently resolves and validates the highest-quality product image URL available across retailers.
    """
    clean_platform = (platform or "amazon").lower()
    
    # 1. Amazon Resolution
    if "amazon" in clean_platform or (product_url and "amazon.in" in product_url):
        asin = extract_amazon_asin(product_url or "") or extract_amazon_asin(unique_id or "") or extract_amazon_asin(raw_img_url or "")
        if asin:
            return get_amazon_highres_image_url(asin)

    # 2. Flipkart Upscaling
    if raw_img_url and ("flixcart.com" in raw_img_url or "flipkart" in clean_platform):
        return upscale_flipkart_image_url(raw_img_url)

    # 3. Myntra Upscaling
    if raw_img_url and ("myntassets.com" in raw_img_url or "myntra" in clean_platform):
        return upscale_myntra_image_url(raw_img_url)

    # 4. Valid raw image check (Filter out temporary expired Telegram CDN URLs)
    if raw_img_url and raw_img_url.startswith("http"):
        if not any(blocked in raw_img_url for blocked in ["telesco.pe", "telegram.org", "base64"]):
            return raw_img_url

    # 5. Direct Page OpenGraph Scrape Fallback
    if product_url and product_url.startswith("http"):
        scraped_img = scrape_page_opengraph_image(product_url)
        if scraped_img:
            return scraped_img

    return None
