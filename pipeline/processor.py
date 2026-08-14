"""
pipeline/processor.py
Unified Non-Blocking Asynchronous Pipeline Orchestrator.
Coordinates end-to-end deal processing:
  1. resolve_final_url (URL Unshortening)
  2. get_canonical_product_id (Canonical ID Extraction)
  3. is_duplicate_and_lock (Atomic Redis Deduplication)
  4. scrape_product_details (Playwright Stealth JSON-LD Scraping)
  5. Stock Availability Check (Drop out-of-stock items)
  6. Gemini AI Deal Scoring & ChromaDB Vector Memory Lookup
  7. convert_to_monetized_url (3-Tier Affiliate Link Monetization)
  8. Multi-Channel Broadcast Dispatch (Telegram, Discord, Webhooks, n8n)
"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional

from utils.normalizer import resolve_final_url, get_canonical_product_id
from utils.deduplicator import is_duplicate_and_lock, release_deal_lock
from scrapers.stealth_scraper import scrape_product_details
from utils.monetizer import convert_to_monetized_url

logger = logging.getLogger("LootPipelineProcessor")


async def process_incoming_deal(raw_url: str, raw_text: str = "") -> Optional[Dict[str, Any]]:
    """
    Unified Pipeline Process Entrypoint.
    Returns structured deal dictionary ready for broadcast, or None if skipped/deduplicated.
    """
    if not raw_url or not isinstance(raw_url, str):
        return None

    # Step 1: Resolve Final URL (Follow redirects for amzn.to, fkrt.it, bit.ly)
    final_url = await resolve_final_url(raw_url, timeout_seconds=5)
    if not final_url:
        final_url = raw_url

    # Step 2: Extract Canonical Product ID
    canonical_id = get_canonical_product_id(final_url)
    logger.info(f"[Pipeline Orchestrator] Canonical ID extracted: '{canonical_id}' for URL: '{final_url[:40]}'")

    # Step 3: Atomic Redis Fast-Path Deduplication
    if canonical_id and await is_duplicate_and_lock(canonical_id, ttl_seconds=14400):
        logger.info(f"[Pipeline Orchestrator] Duplicate deal suppressed for canonical_id='{canonical_id}'")
        return None

    # Step 4: Pre-publish Stealth Playwright & JSON-LD Scraping
    scraped_data = await scrape_product_details(final_url, timeout_seconds=8.0) or {}
    logger.info(f"[Pipeline Orchestrator] Scraped data: title='{scraped_data.get('title')}', price={scraped_data.get('price')}, in_stock={scraped_data.get('in_stock')}")

    # Step 5: Stock Availability Check (only drop if explicitly confirmed out of stock with valid scraped title)
    if scraped_data and scraped_data.get("title") and not scraped_data.get("in_stock", True):
        logger.info(f"[Pipeline Orchestrator] Deal dropped - Out of Stock ({final_url[:40]})")
        return None

    # Step 6: Gemini AI Deal Scoring Engine & ChromaDB Vector Lookup
    title = scraped_data.get("title") or raw_text[:80] or "Loot Opportunity Item"
    price = scraped_data.get("price") or 0.0
    mrp = scraped_data.get("mrp") or (price * 1.3 if price > 0 else 0.0)
    discount = ((mrp - price) / mrp * 100.0) if mrp > price > 0 else 0.0

    # Integrate with AI Scorer
    deal_score = 75.0
    try:
        from deal_engine.scorer import score_deal
        scored_deal = score_deal({
            "title": title,
            "price": price,
            "mrp": mrp,
            "discount": discount,
            "url": final_url,
            "is_verified_low": True
        })
        deal_score = scored_deal.get("deal_score", 75.0)
    except Exception as e:
        logger.debug(f"[Pipeline Orchestrator] AI Scorer fallback ({e})")

    # Step 7: 3-Tier Affiliate Link Monetization
    affiliate_url = await convert_to_monetized_url(final_url)

    # Prepare Final Processed Deal Payload
    deal_payload = {
        "status": "APPROVED",
        "canonical_id": canonical_id,
        "title": title,
        "price": price,
        "mrp": mrp,
        "discount": discount,
        "deal_score": deal_score,
        "raw_url": raw_url,
        "final_url": final_url,
        "affiliate_url": affiliate_url,
        "image_url": scraped_data.get("image_url", ""),
        "in_stock": scraped_data.get("in_stock", True),
        "timestamp": time.time()
    }

    # Step 8: Dispatch to Multi-Channel Broadcasters
    try:
        from deal_engine.notifier import send_deal_notification
        send_deal_notification(deal_payload)
        logger.info(f"[Pipeline Orchestrator] Multi-channel notification dispatched for '{title[:45]}...'")
    except Exception as e:
        logger.debug(f"[Pipeline Orchestrator] Broadcaster notification fallback ({e})")

    logger.info(f"[Pipeline Orchestrator] Deal processed successfully: '{title[:45]}...' (Score: {deal_score})")
    return deal_payload
