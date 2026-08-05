# utils/proxy_validator.py
import time
import random
import logging
import requests
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("ProxyValidator")

# Cache to store validated proxies and expiration time
_validated_pool: List[str] = []
_last_check_time: float = 0.0
_CACHE_TTL = 300  # 5 minutes validation TTL

def validate_proxy(proxy_url: str) -> bool:
    """
    Test a proxy by sending a lightweight HEAD request to Google/Amazon.
    Returns True if the proxy responds within 3 seconds, otherwise False.
    """
    if not proxy_url:
        return False

    if not proxy_url.startswith("http"):
        proxy_url = f"http://{proxy_url}"

    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }
    
    test_urls = ["https://www.google.com", "https://www.amazon.in"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # Attempt checking against test URLs
    for url in test_urls:
        try:
            # We use a strict timeout to ensure we only keep fast proxies
            res = requests.head(url, headers=headers, proxies=proxies, timeout=3.0)
            if res.status_code < 400:
                return True
        except Exception:
            continue
    return False

def get_validated_proxy_pool(settings: dict) -> List[str]:
    """
    Validates all proxies in the configured list concurrently.
    Caches the results for 5 minutes.
    """
    global _validated_pool, _last_check_time
    now = time.time()
    
    raw_list = settings.get("proxy_list", [])
    if not raw_list:
        if settings.get("auto_harvest_proxies", False):
            raw_list = harvest_free_proxies()
        else:
            return []

    # Return cached pool if still fresh (use time-based check so empty results are also cached)
    if _last_check_time > 0 and (now - _last_check_time) < _CACHE_TTL:
        return _validated_pool.copy()

    valid_proxies = [p.strip() for p in raw_list if p.strip()]
    if not valid_proxies:
        return []

    logger.info(f"[Proxy Validator] Initiating concurrent verification of {len(valid_proxies)} proxies...")
    verified = []
    
    # Validate proxies concurrently using a thread pool to avoid blocking the main queue
    with ThreadPoolExecutor(max_workers=min(10, len(valid_proxies))) as executor:
        results = list(executor.map(validate_proxy, valid_proxies))
        
    for proxy, is_valid in zip(valid_proxies, results):
        if is_valid:
            verified.append(proxy)
            
    _validated_pool = verified.copy()
    _last_check_time = now
    
    logger.info(f"[Proxy Validator] Verification completed. Live proxies: {len(verified)}/{len(valid_proxies)}.")
    return verified

def get_next_working_proxy(settings: dict) -> Optional[str]:
    """
    Returns a working proxy from the validated pool in a round-robin/random fashion.
    Falls back to a random raw proxy if validation fails or all are offline.
    """
    pool = get_validated_proxy_pool(settings)
    if pool:
        selected = random.choice(pool)
        if not selected.startswith("http"):
            selected = f"http://{selected}"
        return selected

    # Fallback to raw list if validator couldn't find any live ones
    raw_list = [p.strip() for p in settings.get("proxy_list", []) if p.strip()]
    if raw_list:
        selected = random.choice(raw_list)
        if not selected.startswith("http"):
            selected = f"http://{selected}"
        return selected

    return None


def harvest_free_proxies() -> List[str]:
    """
    Harvests free public HTTP proxies from reliable public API endpoints.
    """
    import re
    apis = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=all&anonymity=all",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt"
    ]
    proxies = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for api in apis:
        try:
            res = requests.get(api, headers=headers, timeout=5.0)
            if res.status_code == 200:
                lines = res.text.splitlines()
                for line in lines:
                    line = line.strip()
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', line):
                        proxies.append(line)
        except Exception as e:
            logger.warning(f"Failed to harvest from {api}: {e}")
            
    proxies = list(set(proxies))
    random.shuffle(proxies)
    return proxies[:50]

