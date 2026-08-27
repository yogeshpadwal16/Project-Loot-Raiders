"""
utils/normalizer.py
Non-blocking async URL unshortening and platform-agnostic canonical ID extraction.
Follows redirects for amzn.to, fkrt.it, bit.ly, cuelinks.com, t.co using aiohttp.
Extracts ASIN (Amazon), PID (Flipkart), Product IDs (Ajio/Myntra), or SHA-256 fallback.
"""

import re
import hashlib
import logging
import urllib.parse
import asyncio
import aiohttp
from typing import Optional, Tuple, Union

logger = logging.getLogger("LootNormalizer")

# Known URL Shorteners
SHORT_DOMAINS = [
    "amzn.to", "fkrt.it", "bit.ly", "cuelinks.com", "t.co", 
    "cutt.ly", "shrk.in", "tinyurl.com", "shorturl.at", "dl.flipkart.com", "mynt.in", "a.co"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class CanonicalID(str):
    """
    String subclass that seamlessly supports both single string evaluation ('AMAZON:B0B39C29')
    and 2-element tuple unpacking (key, platform).
    """
    def __new__(cls, canonical_id: str, platform: str = "generic"):
        obj = super().__new__(cls, canonical_id)
        obj.platform = platform
        return obj

    def __iter__(self):
        return iter((str(self), self.platform))


def resolve_final_sync(short_url: str, max_redirects: int = 10, timeout: float = 5.0) -> str:
    """Synchronous fallback wrapper for URL unshortening."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(resolve_final_url(short_url, int(timeout)))
        else:
            return asyncio.run(resolve_final_url(short_url, int(timeout)))
    except Exception:
        return asyncio.run(resolve_final_url(short_url, int(timeout)))


async def resolve_final_url(short_url: str, timeout_seconds: int = 5, **kwargs) -> str:
    """
    Non-blocking async HTTP redirect resolution.
    Follows HTTP redirects recursively for shortlinks (amzn.to, bit.ly, etc.) using aiohttp.
    Returns the final destination landing page URL or short_url on timeout/failure.
    """
    if not short_url or not isinstance(short_url, str):
        return ""

    current_url = short_url.strip()
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            for _ in range(8):
                parsed = urllib.parse.urlparse(current_url)
                domain = parsed.netloc.lower()

                if not any(sd in domain for sd in SHORT_DOMAINS) and len(parsed.path) > 3:
                    break

                try:
                    async with session.head(current_url, allow_redirects=True) as resp:
                        if resp.url and str(resp.url) != current_url:
                            current_url = str(resp.url)
                            continue
                except Exception:
                    pass

                try:
                    async with session.get(current_url, allow_redirects=True) as resp_get:
                        if resp_get.url:
                            current_url = str(resp_get.url)
                        break
                except Exception:
                    break

    except Exception as e:
        logger.debug(f"[URL Unshortener] Resolution for '{short_url[:40]}' ended: {e}")

    return current_url


def extract_amazon_asin(url: str) -> Optional[str]:
    """Extracts 10-character Amazon ASIN code from product URL."""
    match = re.search(r'/(?:dp|gp/product|product)/([A-Z0-9]{10})', url, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    match_query = re.search(r'[?&]asin=([A-Z0-9]{10})', url, re.IGNORECASE)
    if match_query:
        return match_query.group(1).upper()
    return None


def extract_flipkart_pid(url: str) -> Optional[str]:
    """Extracts Flipkart PID code from product URL query or path."""
    if not url or not isinstance(url, str):
        return None
    match_query = re.search(r'[?&]pid=([a-zA-Z0-9]+)', url)
    if match_query:
        return match_query.group(1)
    match_path = re.search(r'/p/([a-zA-Z0-9]+)', url)
    if match_path:
        return match_path.group(1)
    match_item = re.search(r'itm[a-zA-Z0-9]+', url)
    if match_item:
        return match_item.group(0)
    return None


def extract_ajio_code(url: str) -> Optional[str]:
    """Extracts numeric product code from Ajio product URL."""
    match = re.search(r'/p/([0-9]{8,12})', url)
    if match:
        return match.group(1)
    return None


def extract_myntra_id(url: str) -> Optional[str]:
    """Extracts numeric style ID from Myntra product URL."""
    match = re.search(r'/([0-9]{6,10})/buy', url, re.IGNORECASE)
    if match:
        return match.group(1)
    match_p = re.search(r'myntra\.com/.*?/([0-9]{6,10})', url, re.IGNORECASE)
    if match_p:
        return match_p.group(1)
    return None


def get_canonical_product_id(url: str) -> CanonicalID:
    """
    Extracts platform-agnostic canonical product identifier.
    Returns CanonicalID instance that evaluates as string ("AMAZON:B0B39C29")
    and unpacks as tuple ("AMAZON:B0B39C29", "amazon").
    """
    if not url or not isinstance(url, str):
        return CanonicalID("generic:empty", "generic")

    lower_url = url.lower()

    # Amazon
    if "amazon." in lower_url:
        asin = extract_amazon_asin(url)
        if asin:
            return CanonicalID(f"AMAZON:{asin}", "amazon")
        clean_path = urllib.parse.urlparse(url).path
        sha_hash = hashlib.sha256(f"amazon.in{clean_path}".encode("utf-8")).hexdigest()[:16].upper()
        return CanonicalID(f"AMAZON:{sha_hash}", "amazon")

    # Flipkart
    if "flipkart.com" in lower_url:
        pid = extract_flipkart_pid(url)
        if pid:
            return CanonicalID(f"FLIPKART:{pid}", "flipkart")
        clean_path = urllib.parse.urlparse(url).path
        sha_hash = hashlib.sha256(f"flipkart.com{clean_path}".encode("utf-8")).hexdigest()[:16].upper()
        return CanonicalID(f"FLIPKART:{sha_hash}", "flipkart")

    # Ajio
    if "ajio.com" in lower_url:
        code = extract_ajio_code(url)
        if code:
            return CanonicalID(f"AJIO:{code}", "ajio")
        clean_path = urllib.parse.urlparse(url).path
        sha_hash = hashlib.sha256(f"ajio.com{clean_path}".encode("utf-8")).hexdigest()[:16].upper()
        return CanonicalID(f"AJIO:{sha_hash}", "ajio")

    # Myntra
    if "myntra.com" in lower_url:
        style_id = extract_myntra_id(url)
        if style_id:
            return CanonicalID(f"MYNTRA:{style_id}", "myntra")
        clean_path = urllib.parse.urlparse(url).path
        sha_hash = hashlib.sha256(f"myntra.com{clean_path}".encode("utf-8")).hexdigest()[:16].upper()
        return CanonicalID(f"MYNTRA:{sha_hash}", "myntra")

    # Generic Fallback
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.rstrip('/')
    combined = f"{domain}{path}"
    sha_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16].upper()
    platform_name = domain.split('.')[-2].lower() if '.' in domain else "generic"

    return CanonicalID(f"{platform_name.upper()}:{sha_hash}", platform_name)
