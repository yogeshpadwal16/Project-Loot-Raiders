"""
core/autonomous_harvester.py
Autonomous High-Frequency Native Deal Harvester.
Scrapes direct retailer lightning deals, goldbox feeds, and glitch discounts independently of competitor channels.
"""

import re
import time
import logging
import threading
import requests
from typing import List, Dict, Any, Optional
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from config.settings import load_settings
from utils.parser import extract_amazon_asin, calculate_true_discount
from utils.image_extractor import resolve_best_product_image
from deal_engine.notifier import enqueue_alert
from deal_engine.scorer import calculate_deal_score, should_publish_deal
from utils.affiliate import get_best_affiliate_url

logger = logging.getLogger("loot_raiders.autonomous_harvester")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# High-yield autonomous deal target feeds
NATIVE_DEAL_TARGETS = [
    {
        "name": "Amazon 60%+ Lightning Clearance",
        "platform": "amazon",
        "url": "https://www.amazon.in/s?k=deals+of+the+day&pct-off=60-&s=price-asc-rank"
    },
    {
        "name": "Amazon Electronics & Gadgets Flash Drops",
        "platform": "amazon",
        "url": "https://www.amazon.in/s?k=headphones+smartwatch+speaker&pct-off=50-&s=price-asc-rank"
    },
    {
        "name": "Amazon Home & Kitchen Glitch Radar",
        "platform": "amazon",
        "url": "https://www.amazon.in/s?k=kitchen+appliances&pct-off=50-&s=price-asc-rank"
    },
    {
        "name": "Flipkart Flash Steal Deals",
        "platform": "flipkart",
        "url": "https://www.flipkart.com/search?q=deals+of+the+day&p%5B%5D=facets.discount_range_v1%255B%255D%3D50%2525%2Bor%2Bmore"
    }
]


def harvest_amazon_search_feed(target_url: str) -> List[Dict[str, Any]]:
    """Fast-harvests Amazon search results for high-discount lightning deals."""
    deals = []
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=12)
        if res.status_code != 200:
            return []

        html = res.text
        # Extract product blocks using regex
        asin_blocks = re.findall(r'data-asin=["\']([A-Z0-9]{10})["\']', html)
        asin_blocks = list(dict.fromkeys(asin_blocks)) # Deduplicate ASINs

        for asin in asin_blocks[:15]:
            if not asin or asin.startswith("0000"):
                continue

            # Build direct permanent high-res image
            img_url = f"https://images-eu.ssl-images-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg"
            product_url = f"https://www.amazon.in/dp/{asin}"

            deals.append({
                "id": asin,
                "platform": "amazon",
                "url": product_url,
                "image_url": img_url
            })
    except Exception as e:
        logger.warning(f"Amazon feed harvest exception: {e}")

    return deals


def process_harvested_candidate(candidate: Dict[str, Any]) -> bool:
    """Scrapes, scores, and enqueues a native harvested candidate deal."""
    platform = candidate["platform"]
    url = candidate["url"]
    candidate_id = candidate["id"]
    
    settings = load_settings()
    
    # 1. Scrape full product price & title details
    from core.engine import scrape_product_details
    details = scrape_product_details(url)
    if not details or details.get("price", 0) <= 0:
        return False

    title = details.get("title", "Product Deal")
    price = int(details.get("price", 0))
    mrp = int(details.get("mrp", price))
    
    if mrp <= price:
        return False

    discount = round(((mrp - price) / mrp) * 100.0, 1)
    
    # Check minimum savings threshold
    min_savings = settings.get("min_deal_savings", 100)
    if (mrp - price) < min_savings or discount < 20.0:
        return False

    # Check blocklist keywords
    blocklist = settings.get("blocklist_keywords", [])
    title_lower = title.lower()
    if any(b.lower() in title_lower for b in blocklist):
        return False

    # 2. Concurrency & duplicate check
    from utils.deduplicator import find_duplicate_deal
    final_url = get_best_affiliate_url(url, platform, settings)
    is_dup, _ = find_duplicate_deal(title=title, price=price, platform=platform, url=final_url, time_window_hours=24)
    if is_dup:
        return False

    # 3. Resolve best image
    img_url = resolve_best_product_image(
        raw_img_url=candidate.get("image_url") or details.get("image_url"),
        product_url=final_url,
        platform=platform,
        unique_id=candidate_id
    )

    # 4. Score and Enqueue
    deal_score = calculate_deal_score(
        platform=platform,
        discount=discount,
        price=price,
        mrp=mrp,
        is_verified_low=True,
        is_lightning=True,
        rating=details.get("rating"),
        reviews=details.get("reviews")
    )

    if not should_publish_deal(platform, deal_score):
        return False

    logger.info(f"⚡ [Autonomous Harvester] Enqueueing top native deal: {title[:40]} (₹{price} / {discount}% OFF / Score: {deal_score})")

    # Generate auto-cart link
    from utils.affiliate import generate_auto_cart_url
    auto_cart_url = generate_auto_cart_url(url, platform, settings)

    enqueue_alert(
        platform=platform,
        title=title,
        price=price,
        mrp=mrp,
        discount=discount,
        img_url=img_url,
        final_url=final_url,
        is_verified_low=True,
        deal_score=deal_score,
        unique_id=candidate_id,
        bank_offers=details.get("bank_offers", []),
        coupon_detail=details.get("coupon_detail", ""),
        auto_cart_url=auto_cart_url
    )
    return True


def run_native_harvest_cycle():
    """Runs a single pass across all native direct retailer deal targets."""
    logger.info("⚡ [Autonomous Harvester] Starting native lightning deal harvest cycle...")
    for target in NATIVE_DEAL_TARGETS:
        try:
            candidates = harvest_amazon_search_feed(target["url"])
            for cand in candidates:
                try:
                    process_harvested_candidate(cand)
                except Exception as cand_err:
                    logger.debug(f"Candidate processing error: {cand_err}")
                time.sleep(1.0)
        except Exception as target_err:
            logger.warning(f"Harvester target {target['name']} error: {target_err}")


def start_autonomous_harvester(interval_seconds: int = 180):
    """Starts the autonomous background deal harvesting daemon."""
    def _loop():
        logger.info(f"⚡ [Autonomous Harvester] Daemon active (Interval: {interval_seconds}s).")
        while True:
            try:
                run_native_harvest_cycle()
            except Exception as e:
                logger.error(f"[Autonomous Harvester] Cycle exception: {e}")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_loop, daemon=True, name="AutonomousHarvesterThread")
    thread.start()
