"""
utils/auto_cart.py
1-Click Direct Auto-Cart and Checkout URL Generator for Flash Sales.
Bypasses product page latency to add items directly into the user's shopping cart.
"""

import re
import urllib.parse
from typing import Optional


def generate_amazon_auto_cart_url(asin: str, affiliate_tag: Optional[str] = None) -> str:
    """
    Generates Amazon Direct Add-to-Cart URL.
    Format: https://www.amazon.in/gp/aws/cart/add.html?ASIN.1={ASIN}&Quantity.1=1&tag={TAG}
    """
    if not asin:
        return ""
    tag_param = f"&tag={affiliate_tag}" if affiliate_tag else ""
    return f"https://www.amazon.in/gp/aws/cart/add.html?ASIN.1={asin}&Quantity.1=1{tag_param}"


def generate_flipkart_auto_cart_url(pid: str, affid: Optional[str] = None) -> str:
    """
    Generates Flipkart Direct 1-Click Buy / Checkout URL.
    Format: https://www.flipkart.com/checkout/init?pid={PID}&affid={AFFID}
    """
    if not pid:
        return ""
    aff_param = f"&affid={affid}" if affid else ""
    return f"https://www.flipkart.com/checkout/init?pid={pid}{aff_param}"


def get_1click_buy_url(product_url: str, platform: str, affiliate_id: Optional[str] = None) -> Optional[str]:
    """
    Detects platform and product ID to generate direct 1-click buy URL.
    """
    if not product_url:
        return None

    url_lower = product_url.lower()

    if "amazon" in platform.lower() or "amazon" in url_lower:
        # Extract ASIN
        asin_match = re.search(r'/(?:dp|gp/product|product)/([A-Z0-9]{10})', product_url, re.IGNORECASE)
        if asin_match:
            return generate_amazon_auto_cart_url(asin_match.group(1), affiliate_id)

    elif "flipkart" in platform.lower() or "flipkart" in url_lower:
        # Extract PID
        pid_match = re.search(r'pid=([A-Z0-9]{16})', product_url, re.IGNORECASE)
        if not pid_match:
            pid_match = re.search(r'/p/([a-zA-Z0-9]+)', product_url)
        if pid_match:
            return generate_flipkart_auto_cart_url(pid_match.group(1), affiliate_id)

    return None
