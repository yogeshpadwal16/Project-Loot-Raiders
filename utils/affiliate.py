import os
import re
import urllib.parse
from utils.parser import extract_amazon_asin, extract_flipkart_pid

def get_best_affiliate_url(expanded_url: str, platform: str, settings: dict) -> str:
    """
    Standardized pipeline stage for transforming raw product URLs into tagged affiliate links.
    Compares commission rates dynamically between Cuelinks and EarnKaro and routes through the highest payer.
    """
    if not expanded_url:
        return expanded_url

    platform_lower = (platform or "").lower().strip()

    # Normalize sub-feed platform identifiers to their parent retailer
    if "amazon" in platform_lower:
        parent_platform = "amazon"
    elif "flipkart" in platform_lower:
        parent_platform = "flipkart"
    elif "myntra" in platform_lower:
        parent_platform = "myntra"
    elif "ajio" in platform_lower:
        parent_platform = "ajio"
    elif "meesho" in platform_lower:
        parent_platform = "meesho"
    elif "jiomart" in platform_lower:
        parent_platform = "jiomart"
    elif "tatacliq" in platform_lower or "tata_cliq" in platform_lower:
        parent_platform = "tatacliq"
    else:
        parent_platform = platform_lower
    
    # Direct affiliate overrides (highly preferred for Amazon and Flipkart if configured)
    amazon_tag = (os.environ.get("AMAZON_AFFILIATE_TAG") or os.environ.get("AMAZON_TAG") or settings.get("amazon_tag") or "lootraiders-21").strip()
    flipkart_affid = (os.environ.get("FLIPKART_AFFID") or settings.get("flipkart_affid") or "lootraiders").strip()
    if flipkart_affid == "YOUR_FLIPKART_AFFILIATE_ID" or flipkart_affid == "":
        flipkart_affid = "lootraiders"

    if parent_platform == "amazon" and amazon_tag and amazon_tag != "YOUR_AMAZON_TAG":
        asin = extract_amazon_asin(expanded_url)
        if asin:
            return f"https://www.amazon.in/dp/{asin}?tag={amazon_tag}"
    if parent_platform == "flipkart" and flipkart_affid:
        pid = extract_flipkart_pid(expanded_url)
        if pid:
            return f"https://www.flipkart.com/product/p/itm?pid={pid}&affid={flipkart_affid}"
        else:
            parsed = urllib.parse.urlparse(expanded_url)
            query = urllib.parse.parse_qs(parsed.query)
            query['affid'] = [flipkart_affid]
            new_query = urllib.parse.urlencode(query, doseq=True)
            return urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc or "www.flipkart.com", parsed.path, parsed.params, new_query, parsed.fragment))

    cuelinks_id = settings.get("cuelinks_pub_id", "").strip()
    earnkaro_id = settings.get("earnkaro_pub_id", "").strip()

    # Commission Rate comparison configuration (Feature 11)
    COMMISSION_RATES = {
        "ajio": {"cuelinks": 0.08, "earnkaro": 0.10},
        "myntra": {"cuelinks": 0.06, "earnkaro": 0.05},
        "meesho": {"cuelinks": 0.12, "earnkaro": 0.15},
        "jiomart": {"cuelinks": 0.05, "earnkaro": 0.04},
        "tatacliq": {"cuelinks": 0.04, "earnkaro": 0.03},
        "amazon": {"cuelinks": 0.07, "earnkaro": 0.06},
        "flipkart": {"cuelinks": 0.08, "earnkaro": 0.07}
    }

    rates = COMMISSION_RATES.get(parent_platform, {"cuelinks": 0.05, "earnkaro": 0.05})

    # Calculate best route
    route = "direct"
    if cuelinks_id and earnkaro_id:
        if rates["earnkaro"] > rates["cuelinks"]:
            route = "earnkaro"
        else:
            route = "cuelinks"
    elif cuelinks_id:
        route = "cuelinks"
    elif earnkaro_id:
        route = "earnkaro"

    if route == "cuelinks":
        return f"https://cuelinks.com/link?pub_id={cuelinks_id}&url={urllib.parse.quote(expanded_url)}"
    elif route == "earnkaro":
        return f"https://earnkaro.com/sharedeal?dl={urllib.parse.quote(expanded_url)}&pub_id={earnkaro_id}"

    # Fallback to direct tagging if configured
    if parent_platform == "amazon":
        asin = extract_amazon_asin(expanded_url)
        if asin:
            if amazon_tag and amazon_tag != "YOUR_AMAZON_TAG":
                return f"https://www.amazon.in/dp/{asin}?tag={amazon_tag}"
            else:
                return f"https://www.amazon.in/dp/{asin}"
    elif parent_platform == "flipkart":
        pid = extract_flipkart_pid(expanded_url)
        if pid and flipkart_affid:
            return f"https://www.flipkart.com/product/p/itm?pid={pid}&affid={flipkart_affid}"
        if not expanded_url.startswith("http"):
            expanded_url = f"https://www.flipkart.com{expanded_url}" if expanded_url.startswith("/") else f"https://www.flipkart.com/{expanded_url}"
        return expanded_url

    # Final safety: ensure returned URL is always absolute
    if not expanded_url.startswith("http"):
        return f"https://{expanded_url}" if "." in expanded_url else expanded_url
    return expanded_url

def generate_auto_cart_url(expanded_url: str, platform: str, settings: dict) -> str:
    """
    Formats direct Add-to-Cart links for Amazon and Flipkart with affiliate tracking (Feature 12).
    """
    platform_lower = (platform or "").lower().strip()
    parent_platform = "amazon" if "amazon" in platform_lower else ("flipkart" if "flipkart" in platform_lower else platform_lower)

    if parent_platform == "amazon":
        asin = extract_amazon_asin(expanded_url)
        tag = (os.environ.get("AMAZON_AFFILIATE_TAG") or os.environ.get("AMAZON_TAG") or settings.get("amazon_tag") or "lootraiders-21").strip()
        if asin:
            return f"https://www.amazon.in/gp/aws/cart/add.html?ASIN.1={asin}&Quantity.1=1&tag={tag}"
    elif parent_platform == "flipkart":
        pid = extract_flipkart_pid(expanded_url)
        affid = (os.environ.get("FLIPKART_AFFID") or settings.get("flipkart_affid") or "lootraiders").strip()
        if affid == "YOUR_FLIPKART_AFFILIATE_ID" or affid == "":
            affid = "lootraiders"
        if pid:
            return f"https://www.flipkart.com/co/add-to-cart?pid={pid}&affid={affid}"
    return None
