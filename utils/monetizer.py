"""
utils/monetizer.py
3-tier fallback affiliate monetization engine.
Tier 1: Direct Amazon Associate tag injection (?tag=AMAZON_AFFILIATE_TAG).
Tier 2: Async Cuelinks/EarnKaro Affiliate API routing via aiohttp.
Tier 3: Clean Fallback URL stripping tracking parameters with zero crashes.
"""

import os
import urllib.parse
import logging
import aiohttp
from typing import Optional
from config.settings import load_settings
from utils.normalizer import extract_amazon_asin, extract_flipkart_pid

logger = logging.getLogger("LootMonetizer")

DEFAULT_AMAZON_TAG = "lootraiders-21"
DEFAULT_FLIPKART_AFFID = "lootraiders"


async def convert_to_monetized_url(canonical_url: str) -> str:
    """
    Asynchronously converts canonical_url to a monetized affiliate URL.
    Tier 1: Direct Amazon tag injection.
    Tier 2: Async Cuelinks / EarnKaro API routing.
    Tier 3: Clean stripped canonical fallback URL.
    """
    if not canonical_url or not isinstance(canonical_url, str):
        return ""

    settings = load_settings()
    amazon_tag = os.environ.get("AMAZON_AFFILIATE_TAG") or os.environ.get("AMAZON_TAG") or settings.get("amazon_tag") or DEFAULT_AMAZON_TAG
    flipkart_affid = os.environ.get("FLIPKART_AFFID") or settings.get("flipkart_affid") or DEFAULT_FLIPKART_AFFID
    cuelinks_api_key = os.environ.get("CUELINKS_API_KEY") or os.environ.get("CUELINKS_PUB_ID") or settings.get("cuelinks_pub_id") or ""

    lower_url = canonical_url.lower()

    # -------------------------------------------------------------
    # TIER 1: Direct Amazon RegEx & Tag Injection
    # -------------------------------------------------------------
    if "amazon." in lower_url:
        asin = extract_amazon_asin(canonical_url)
        if asin:
            return f"https://www.amazon.in/dp/{asin}?tag={amazon_tag}"
        
        parsed = urllib.parse.urlparse(canonical_url)
        query = urllib.parse.parse_qs(parsed.query)
        query['tag'] = [amazon_tag]
        new_query = urllib.parse.urlencode(query, doseq=True)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    # Flipkart Direct Monetization
    if "flipkart.com" in lower_url:
        pid = extract_flipkart_pid(canonical_url)
        if pid:
            return f"https://www.flipkart.com/product/p/itmd?pid={pid}&affid={flipkart_affid}"

    # -------------------------------------------------------------
    # TIER 2: Async Cuelinks / Affiliate Network API Routing
    # -------------------------------------------------------------
    if cuelinks_api_key and cuelinks_api_key not in ["YOUR_CUELINKS_API_KEY", "YOUR_CUELINKS_PUB_ID"]:
        try:
            encoded_target = urllib.parse.quote(canonical_url, safe="")
            api_endpoint = f"https://www.cuelinks.com/api/v2/links.json?channel_id={cuelinks_api_key}&url={encoded_target}"
            headers = {"Authorization": f"Token token={cuelinks_api_key}"}
            timeout = aiohttp.ClientTimeout(total=2.5)

            async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                async with session.get(api_endpoint) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        aff_url = data.get("affiliate_url") or data.get("url")
                        if aff_url:
                            return str(aff_url)
        except Exception as e:
            logger.debug(f"[Monetizer Engine] Tier 2 Cuelinks API failed/timed out: {e}")

    # -------------------------------------------------------------
    # TIER 3: Clean Fallback URL (Stripped Query Params)
    # -------------------------------------------------------------
    parsed = urllib.parse.urlparse(canonical_url)
    query_params = urllib.parse.parse_qs(parsed.query)
    # Strip tracking parameters
    clean_params = {k: v for k, v in query_params.items() if not k.startswith("utm_") and k not in ["ref", "tag", "affid", "fbclid", "gclid"]}
    new_query = urllib.parse.urlencode(clean_params, doseq=True)
    
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
