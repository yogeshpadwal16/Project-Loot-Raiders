import re
import requests
import logging

logger = logging.getLogger("loot_raiders.cleaner")

# Affiliate configuration overrides
AMAZON_TAG = "loot_raiders-21"
FLIPKART_AFFID = "loot_raiders"


def extract_asin(url: str) -> str | None:
    """Extracts 10-character Amazon ASIN code from product URL."""
    match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
    return match.group(1) if match else None


def extract_flipkart_pid(url: str) -> str | None:
    """Extracts 16-character Flipkart PID code from product URL query or path."""
    match = re.search(r'pid=([a-zA-Z0-9]{16})', url)
    if match:
        return match.group(1)
    match_p = re.search(r'/p/([a-zA-Z0-9]{16})', url)
    return match_p.group(1) if match_p else None


def clean_and_tag_url(url: str) -> tuple[str, str]:
    """
    Follows redirects to expand URLs, strips query parameter tracking codes,
    and injects platform-specific affiliate monetization parameters.
    Returns (cleaned_monetized_url, platform_name).
    """
    if not url:
        return "", "generic"

    expanded_url = url
    try:
        # Resolve short URLs via requests HEAD (non-blocking simulation)
        if any(short in url.lower() for short in ["amzn.to", "fkrt.it", "bit.ly", "tinyurl", "t.co"]):
            res = requests.head(url, allow_redirects=True, timeout=5)
            expanded_url = res.url
    except Exception as e:
        logger.warning(f"URL expansion failed for {url}: {e}")

    expanded_lower = expanded_url.lower()

    if "amazon.in" in expanded_lower:
        asin = extract_asin(expanded_url)
        if asin:
            cleaned = f"https://www.amazon.in/dp/{asin}?tag={AMAZON_TAG}"
            return cleaned, "amazon"
        return expanded_url, "amazon"

    if "flipkart.com" in expanded_lower:
        pid = extract_flipkart_pid(expanded_url)
        if pid:
            cleaned = f"https://www.flipkart.com/product/p/itmd?pid={pid}&affid={FLIPKART_AFFID}"
            return cleaned, "flipkart"
        return expanded_url, "flipkart"

    if "myntra.com" in expanded_lower:
        # Myntra fallback cloaker routing
        from network_fallback import get_fallback_monetized_url
        return get_fallback_monetized_url(expanded_url, "myntra"), "myntra"

    return expanded_url, "generic"


def generate_auto_cart_url(url: str, platform: str) -> str | None:
    """Creates a direct checkout/cart URL to expedite price glitches (Feature 12)."""
    if platform.lower() == "amazon":
        asin = extract_asin(url)
        if asin:
            # Direct Amazon buy now cart link
            return f"https://www.amazon.in/gp/aws/cart/add.html?ASIN.1={asin}&Quantity.1=1&AssociateTag={AMAZON_TAG}"
    return None
