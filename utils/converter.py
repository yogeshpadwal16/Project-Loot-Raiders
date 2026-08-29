"""
Phase 3: Multi-Tier Monetization Converter Module.
Provides 3-tier fallback monetization engine for Amazon, Flipkart, Myntra, Ajio & TataCliq.
"""

import os
import re
import logging
import urllib.parse
import requests
from typing import Tuple, Optional
from config.settings import load_settings
from utils.normalizer import extract_amazon_asin, extract_flipkart_pid

logger = logging.getLogger("LootConverter")

DEFAULT_AMAZON_TAG = "lootraiders-21"
DEFAULT_FLIPKART_AFFID = "lootraiders"


def monetize_url(url: str, platform_hint: Optional[str] = None) -> Tuple[str, str, Optional[str]]:
    """
    3-Tier Fallback Monetization Engine:
      Tier 1: Direct RegEx & tag injection (Amazon / Flipkart).
      Tier 2: Affiliate Network API routing (Cuelinks / EarnKaro).
      Tier 3: Fallback clean URL (returns within 3s timeout with zero crashes).
    
    Returns (monetized_url, platform_name, auto_cart_url).
    """
    if not url or not isinstance(url, str):
        return ("", "generic", None)

    settings = load_settings()
    amazon_tag = os.environ.get("AMAZON_TAG") or settings.get("amazon_tag") or DEFAULT_AMAZON_TAG
    flipkart_affid = os.environ.get("FLIPKART_AFFID") or settings.get("flipkart_affid") or DEFAULT_FLIPKART_AFFID
    cuelinks_pub_id = os.environ.get("CUELINKS_PUB_ID") or settings.get("cuelinks_pub_id") or ""
    earnkaro_pub_id = os.environ.get("EARNKARO_PUB_ID") or settings.get("earnkaro_pub_id") or ""

    lower_url = url.lower()

    # -------------------------------------------------------------
    # TIER 1: Direct RegEx & Tag Injection
    # -------------------------------------------------------------

    # Amazon Direct Monetization
    if "amazon." in lower_url:
        asin = extract_amazon_asin(url)
        if asin:
            monetized = f"https://www.amazon.in/dp/{asin}?tag={amazon_tag}"
            auto_cart = f"https://www.amazon.in/gp/aws/cart/add.html?ASIN.1={asin}&Quantity.1=1&AssociateTag={amazon_tag}"
            return (monetized, "amazon", auto_cart)
        # Fallback Amazon URL with tag
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        query['tag'] = [amazon_tag]
        new_query = urllib.parse.urlencode(query, doseq=True)
        monetized = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        return (monetized, "amazon", None)

    # Flipkart Direct Monetization
    if "flipkart.com" in lower_url:
        pid = extract_flipkart_pid(url)
        if pid:
            monetized = f"https://www.flipkart.com/product/p/itmd?pid={pid}&affid={flipkart_affid}"
            return (monetized, "flipkart", None)

    # -------------------------------------------------------------
    # TIER 2: Affiliate Network API Routing (Cuelinks / EarnKaro)
    # -------------------------------------------------------------
    if cuelinks_pub_id and cuelinks_pub_id != "YOUR_CUELINKS_PUB_ID":
        try:
            # Route via Cuelinks Link API with 2.5s strict timeout
            encoded_url = urllib.parse.quote(url, safe="")
            api_endpoint = f"https://www.cuelinks.com/api/v2/links.json?channel_id={cuelinks_pub_id}&url={encoded_url}"
            headers = {"Authorization": f"Token token={cuelinks_pub_id}"}
            res = requests.get(api_endpoint, headers=headers, timeout=2.5)
            if res.status_code == 200:
                data = res.json()
                aff_url = data.get("affiliate_url") or data.get("url")
                if aff_url:
                    platform = "flipkart" if "flipkart" in lower_url else ("myntra" if "myntra" in lower_url else "generic")
                    return (aff_url, platform, None)
        except Exception as e:
            logger.debug(f"[Monetization Converter] Tier 2 Cuelinks API failed/timed out: {e}")

    # -------------------------------------------------------------
    # TIER 3: Fallback Clean Original URL (Guaranteed Safety)
    # -------------------------------------------------------------
    parsed = urllib.parse.urlparse(url)
    # Strip tracking query params (utm_*, ref, tag, affid, s, q)
    query_params = urllib.parse.parse_qs(parsed.query)
    clean_params = {k: v for k, v in query_params.items() if not k.startswith("utm_") and k not in ["ref", "tag", "affid", "fbclid", "gclid"]}
    new_query = urllib.parse.urlencode(clean_params, doseq=True)
    clean_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    platform = "amazon" if "amazon" in lower_url else ("flipkart" if "flipkart" in lower_url else ("myntra" if "myntra" in lower_url else ("ajio" if "ajio" in lower_url else "generic")))

    return (clean_url, platform, None)
