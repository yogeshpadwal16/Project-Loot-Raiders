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

    platform_lower = platform.lower()
    
    # Direct affiliate overrides (highly preferred for Amazon and Flipkart if configured)
    amazon_tag = settings.get("amazon_tag", "lootraiders-21").strip()
    flipkart_affid = settings.get("flipkart_affid", "YOUR_FLIPKART_AFFILIATE_ID").strip()
    
    if platform_lower == "amazon" and amazon_tag and amazon_tag != "YOUR_AMAZON_TAG" and amazon_tag != "":
        asin = extract_amazon_asin(expanded_url)
        if asin:
            return f"https://www.amazon.in/dp/{asin}?tag={amazon_tag}"
    if platform_lower == "flipkart" and flipkart_affid and flipkart_affid != "YOUR_FLIPKART_AFFILIATE_ID" and flipkart_affid != "":
        pid = extract_flipkart_pid(expanded_url)
        if pid:
            return f"https://www.flipkart.com/product/p/itm?pid={pid}&affid={flipkart_affid}"
            
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
    
    rates = COMMISSION_RATES.get(platform_lower, {"cuelinks": 0.05, "earnkaro": 0.05})
    
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
    if platform_lower == "amazon":
        asin = extract_amazon_asin(expanded_url)
        if asin:
            return f"https://www.amazon.in/dp/{asin}?tag={amazon_tag}"
    elif platform_lower == "flipkart":
        pid = extract_flipkart_pid(expanded_url)
        if pid:
            return f"https://www.flipkart.com/product/p/itm?pid={pid}&affid=lootraiders"
            
    return expanded_url

def generate_auto_cart_url(expanded_url: str, platform: str, settings: dict) -> str:
    """
    Formats direct Add-to-Cart links for Amazon and Flipkart with affiliate tracking (Feature 12).
    """
    platform_lower = platform.lower()
    if platform_lower == "amazon":
        asin = extract_amazon_asin(expanded_url)
        tag = settings.get("amazon_tag", "lootraiders-21").strip()
        if asin:
            return f"https://www.amazon.in/gp/aws/cart/add.html?ASIN.1={asin}&Quantity.1=1&tag={tag}"
    elif platform_lower == "flipkart":
        pid = extract_flipkart_pid(expanded_url)
        affid = settings.get("flipkart_affid", "lootraiders").strip()
        if affid == "YOUR_FLIPKART_AFFILIATE_ID" or affid == "":
            affid = "lootraiders"
        if pid:
            return f"https://www.flipkart.com/co/add-to-cart?pid={pid}&affid={affid}"
    return None
