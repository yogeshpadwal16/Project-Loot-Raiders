"""
pipeline/processor.py
Fail-Safe Resilient Pipeline Orchestrator with Stage-by-Stage Telemetry.

Stage 1 [INGEST]    : Ingest raw URL and text.
Stage 2 [UNSHORTEN] : Async HTTP redirect unshortener (aiohttp).
Stage 3 [DEDUP]     : Canonical ID extraction & atomic Redis lock check.
Stage 4 [SCRAPE/FB] : Playwright Stealth JSON-LD scrape with Graceful Text/Title Fallback on CAPTCHA/Timeout.
Stage 5 [RULES]     : India Free Stuff Deal Scoring Rules Engine (utils/rules_engine.py).
Stage 6 [MONETIZE]  : 3-Tier Affiliate Link Monetization.
Stage 7 [BROADCAST] : Rate-limited safe_send_message multi-channel dispatch.
"""

import re
import time
import logging
import asyncio
from typing import Dict, Any, Optional

from utils.normalizer import resolve_final_url, get_canonical_product_id
from utils.deduplicator import is_duplicate_and_lock, release_deal_lock
from scrapers.stealth_scraper import scrape_product_details
from utils.monetizer import convert_to_monetized_url
from utils.rate_limiter import safe_send_message
from utils.rules_engine import evaluate_deal_eligibility

logger = logging.getLogger("LootPipelineProcessor")

BANNER_KEYWORDS = {
    "loot", "deal", "deals", "offer", "offers", "cheap", "sale", "hurry", "fast",
    "join", "subscribe", "buy", "now", "t.me", "hot", "alert", "glitch", "verified",
    "price", "drop", "discount", "off", "best", "super", "unverified"
}


def extract_price_from_text(text: str) -> float:
    """Extracts numeric deal price from text via regex (e.g., 'Rs. 499', '₹1,299')."""
    if not text:
        return 0.0
    match = re.search(r'(?:₹|rs\.?|inr)\s*([0-9,]+)', text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1).replace(',', ''))
        except ValueError:
            pass
    return 0.0


def extract_title_from_text(text: str) -> str:
    """Extracts primary product title line from raw Telegram text, skipping banner headlines."""
    if not text:
        return "Loot Deal Item"
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    for line in lines:
        clean = re.sub(r'https?://\S+', '', line).strip()
        clean = re.sub(r'[\U00010000-\U0010ffff]', '', clean).strip()
        if not clean or len(clean) < 5:
            continue
        # Skip pure banner headlines like "🔥 HOT LOOT DEAL 🔥"
        words = [w.lower() for w in clean.split() if w.isalnum()]
        if words and all(w in BANNER_KEYWORDS for w in words):
            continue
        return clean[:80]

    return lines[0][:80] if lines else "Loot Deal Item"


async def process_incoming_deal(raw_url: str, raw_text: str = "", client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    """
    Fail-Safe Resilient Pipeline Process Entrypoint.
    Executes 7-stage workflow with complete fallback safety and stage telemetry.
    """
    if not raw_url or not isinstance(raw_url, str):
        return None

    logger.info(f"[STAGE 1: INGEST] Ingested raw URL: '{raw_url[:50]}'")

    # Stage 2: Unshorten URL
    final_url = await resolve_final_url(raw_url, timeout_seconds=5)
    if not final_url:
        final_url = raw_url
    logger.info(f"[STAGE 2: UNSHORTEN] Resolved URL: '{final_url[:50]}'")

    # Stage 3: Extract Canonical ID & Atomic Redis Lock Check
    canonical_id = get_canonical_product_id(final_url)
    logger.info(f"[STAGE 3: DEDUP] Canonical ID: '{canonical_id}'")

    if canonical_id and await is_duplicate_and_lock(canonical_id, ttl_seconds=14400):
        logger.info(f"[STAGE 3: DEDUP] Duplicate deal suppressed for canonical_id='{canonical_id}'")
        return None

    # Stage 4: Scrape Product Details with Graceful Text Fallback
    scraped_data = None
    try:
        scraped_data = await scrape_product_details(final_url, timeout_seconds=8.0)
    except Exception as scrape_err:
        logger.warning(f"[STAGE 4: SCRAPE] Scraping exception ({scrape_err}). Activating text fallback...")

    title = ""
    price = 0.0
    mrp = 0.0
    in_stock = True
    image_url = ""

    if scraped_data and scraped_data.get("title") and scraped_data.get("price", 0) > 0:
        title = scraped_data["title"]
        price = scraped_data["price"]
        mrp = scraped_data.get("mrp", price * 1.25)
        in_stock = scraped_data.get("in_stock", True)
        image_url = scraped_data.get("image_url", "")
        logger.info(f"[STAGE 4: SCRAPE] Scraped successfully: '{title[:40]}...' (Price: Rs.{price})")
    else:
        # Graceful Text Fallback Mode: Extract title and price from raw text if scraping failed / CAPTCHA
        logger.info("[STAGE 4: FALLBACK] Scraping returned incomplete payload / CAPTCHA wall. Using Text Fallback Mode...")
        title = extract_title_from_text(raw_text)
        price = extract_price_from_text(raw_text)
        mrp = price * 1.25 if price > 0 else 0.0
        in_stock = True
        logger.info(f"[STAGE 4: FALLBACK] Extracted text fallback: '{title[:40]}...' (Price: Rs.{price})")

    # Drop explicitly confirmed out-of-stock items
    if scraped_data and scraped_data.get("title") and not in_stock:
        logger.info(f"[STAGE 4: SCRAPE] Deal dropped - Out of Stock ({final_url[:40]})")
        await release_deal_lock(canonical_id)
        return None

    # Stage 5: Evaluate India Free Stuff Rules Engine
    rules_res = evaluate_deal_eligibility(
        mrp=mrp if mrp > 0 else None,
        current_price=price if price > 0 else None,
        category="general",
        title=title
    )

    if not rules_res["approved"]:
        logger.info(f"[STAGE 5: RULES] Deal rejected by rules engine: {rules_res.get('reason')}")
        await release_deal_lock(canonical_id)
        return None

    logger.info(f"[STAGE 5: RULES] Deal approved (Tier: {rules_res.get('tier')}, Discount: {rules_res.get('discount_pct')}%)")

    # Stage 6: Multi-Tier Affiliate Link Monetization
    affiliate_url = await convert_to_monetized_url(final_url)
    logger.info(f"[STAGE 6: MONETIZE] Monetized URL: '{affiliate_url[:50]}'")

    # Stage 7: Rate-Limited Broadcast Dispatch
    deal_payload = {
        "status": "APPROVED",
        "canonical_id": str(canonical_id),
        "title": title,
        "price": price,
        "mrp": mrp,
        "discount": rules_res.get("discount_pct", 0.0),
        "tier": rules_res.get("tier", "STANDARD"),
        "is_loot": rules_res.get("is_loot", False),
        "raw_url": raw_url,
        "final_url": final_url,
        "affiliate_url": affiliate_url,
        "image_url": image_url,
        "in_stock": in_stock,
        "timestamp": time.time()
    }

    try:
        if client:
            from config.settings import load_settings
            chat_id = load_settings().get("telegram_chat_id", "@LootRaidersDeals")
            price_str = f"Rs.{price:,.0f}" if price > 0 else "Special Price"
            mrp_str = f" (MRP: Rs.{mrp:,.0f})" if mrp > price > 0 else ""
            disc_str = f" | {rules_res.get('discount_pct', 0):.0f}% OFF" if rules_res.get('discount_pct', 0) > 0 else ""

            msg_text = f"🔥 [{rules_res.get('tier', 'LOOT DEAL')}] 🔥\n{title}\n\n💰 Price: {price_str}{mrp_str}{disc_str}\n👉 Buy Now: {affiliate_url}"
            await safe_send_message(client, chat_id, msg_text)
        else:
            from deal_engine.notifier import send_deal_notification
            send_deal_notification(deal_payload)
        logger.info(f"[STAGE 7: BROADCAST] Deal successfully dispatched: '{title[:45]}...'")
    except Exception as b_err:
        logger.error(f"[STAGE 7: BROADCAST] Broadcast error ({b_err}). Releasing lock for retry...")
        await release_deal_lock(canonical_id)
        return None

    return deal_payload
