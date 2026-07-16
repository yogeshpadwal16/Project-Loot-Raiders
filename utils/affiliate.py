import re
import urllib.parse
from utils.parser import extract_amazon_asin, extract_flipkart_pid

def generate_affiliate_url(raw_url: str, platform: str, settings: dict) -> str:
    """
    Standardized pipeline stage for transforming raw product URLs into tagged affiliate links.
    Never hardcoded inside scrapers; resolved dynamically via active dashboard settings.
    """
    if not raw_url:
        return raw_url

    platform_lower = platform.lower()
    
    # Convert relative URLs to absolute URLs
    if not raw_url.startswith("http"):
        base_host = "https://www.amazon.in"
        if "flipkart" in platform_lower:
            base_host = "https://www.flipkart.com"
        elif "myntra" in platform_lower:
            base_host = "https://www.myntra.com"
        elif "ajio" in platform_lower:
            base_host = "https://www.ajio.com"
        elif "meesho" in platform_lower:
            base_host = "https://www.meesho.com"
        elif "tatacliq" in platform_lower:
            base_host = "https://www.tatacliq.com"
        elif "jiomart" in platform_lower:
            base_host = "https://www.jiomart.com"
            
        raw_url = urllib.parse.urljoin(base_host, raw_url)
    
    # 1. Amazon Affiliate Tagging
    if "amazon" in platform_lower:
        asin = extract_amazon_asin(raw_url)
        if asin:
            tag = settings.get("amazon_tag", "lootraiders-21").strip()
            return f"https://www.amazon.in/dp/{asin}?tag={tag}"
            
    # 2. Flipkart Affiliate Tagging
    elif "flipkart" in platform_lower:
        pid = extract_flipkart_pid(raw_url)
        if pid:
            affid = settings.get("flipkart_affid", "YOUR_FLIPKART_AFFILIATE_ID").strip()
            # Clean up default placeholder
            if affid == "YOUR_FLIPKART_AFFILIATE_ID":
                affid = "lootraiders"
            return f"https://www.flipkart.com/product/p/itm?pid={pid}&affid={affid}"
            
    # 3. Future Retailers (Ajio, Myntra, Meesho, TataCliq, JioMart)
    # Most of these require third-party network wrappers (e.g. Cuelinks, EarnKaro, vCommission)
    # We can implement a generic sub-tagging system or redirect resolver
    elif "ajio" in platform_lower:
        # Cuelinks / EarnKaro wrapper can be added here
        pass
    elif "myntra" in platform_lower:
        pass
        
    return raw_url
