import urllib.parse
import os

CUELINKS_SUBID = "loot_raiders"
EARNKARO_API_KEY = ""


def get_cuelinks_url(long_url: str) -> str:
    """Wraps target merchant links using Cuelinks redirect wrapper."""
    subid = os.environ.get("CUELINKS_SUBID", CUELINKS_SUBID)
    encoded = urllib.parse.quote(long_url)
    # Standard Cuelinks redirect link template format
    return f"https://cuelinks.com/link?pub_id=123456&sub_id={subid}&txid=&url={encoded}"


def get_earnkaro_url(long_url: str) -> str:
    """Wraps target merchant links using EarnKaro API redirect wrapper."""
    api_key = os.environ.get("EARNKARO_API_KEY", EARNKARO_API_KEY)
    encoded = urllib.parse.quote(long_url)
    return f"https://earnkaro.com/open-share?url={encoded}&api_key={api_key}"


def get_fallback_monetized_url(long_url: str, store_name: str) -> str:
    """
    Selects the best monetization route for stores not natively supported.
    Uses Cuelinks as primary, falling back to EarnKaro.
    """
    store_lower = store_name.lower()
    
    # Simulate custom rules: Myntra/Ajio prefer Cuelinks, Meesho prefers EarnKaro
    if "meesho" in store_lower:
        return get_earnkaro_url(long_url)
        
    return get_cuelinks_url(long_url)
