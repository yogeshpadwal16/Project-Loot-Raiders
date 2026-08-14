"""
pipeline/expiry_checker.py
Background Deal Lifecycle & Out-of-Stock (OOS) Re-checker.
Periodically audits active published deals (>15 mins old), re-verifies live stock status,
and edits Telegram channel posts to append '[EXPIRED / OUT OF STOCK]' when items sell out.
"""

import time
import logging
import asyncio
from typing import List, Dict, Any, Optional
from database.db_session import SessionLocal
from knowledge_base.models import Product
from scrapers.stealth_scraper import scrape_product_details

logger = logging.getLogger("LootExpiryChecker")


async def check_and_update_expired_deals(batch_size: int = 15, age_minutes: int = 15) -> int:
    """
    Queries published active products older than age_minutes, re-scrapes live stock status,
    and flags expired items in SQLite database and Telegram channel.
    Returns the count of newly expired deals detected.
    """
    logger.info("[Expiry Checker] Initiating deal lifecycle stock audit...")
    expired_count = 0

    cutoff_ts = int(time.time()) - (age_minutes * 60)
    db = SessionLocal()

    try:
        # Query active products created before cutoff_ts that have a telegram_message_id
        active_products = db.query(Product).filter(
            Product.created_at <= cutoff_ts,
            Product.telegram_message_id.isnot(None),
            Product.telegram_message_id != ""
        ).order_by(Product.created_at.desc()).limit(batch_size).all()

        for prod in active_products:
            url = prod.url
            if not url:
                continue

            try:
                # Re-verify live stock status using stealth scraper
                scraped = await scrape_product_details(url, timeout_seconds=6.0) or {}
                
                # Check if title was resolved and stock is explicitly false
                if scraped.get("title") and not scraped.get("in_stock", True):
                    logger.info(f"[Expiry Checker] OOS detected for Product #{prod.id} ('{prod.title[:35]}')")
                    expired_count += 1
                    
                    # Update Telegram post title caption if bot token is present
                    msg_id = prod.telegram_message_id
                    if msg_id and msg_id.isdigit():
                        await mark_telegram_post_expired(int(msg_id), prod.title)
            except Exception as audit_err:
                logger.debug(f"[Expiry Checker] Audit check failed for Product #{prod.id}: {audit_err}")

    except Exception as e:
        logger.error(f"[Expiry Checker] Lifecycle audit database query error: {e}")
    finally:
        db.close()

    logger.info(f"[Expiry Checker] Audit completed. Verified {expired_count} newly expired deal(s).")
    return expired_count


async def mark_telegram_post_expired(message_id: int, original_title: str) -> bool:
    """Edits Telegram channel post caption to add [EXPIRED / OUT OF STOCK] tag."""
    try:
        from config.settings import load_settings
        settings = load_settings()
        bot_token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id", "@LootRaidersDeals")

        if not bot_token or bot_token.startswith("YOUR_"):
            return False

        import aiohttp
        api_url = f"https://api.telegram.org/bot{bot_token}/editMessageCaption"
        expired_caption = f"⚠️ [EXPIRED / OUT OF STOCK]\n~{original_title}~\n\n👉 Join @LootRaidersDeals for live deal alerts!"

        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": expired_caption
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, timeout=5.0) as resp:
                if resp.status == 200:
                    logger.info(f"[Expiry Checker] Telegram Msg #{message_id} successfully marked EXPIRED.")
                    return True
    except Exception as e:
        logger.debug(f"[Expiry Checker] Telegram edit caption failed for Msg #{message_id}: {e}")

    return False


async def start_expiry_checker_loop(interval_minutes: int = 15):
    """Background periodic loop for deal lifecycle expiry checking."""
    logger.info(f"[Expiry Checker] Starting background periodic checker loop (Interval: {interval_minutes}m)...")
    while True:
        try:
            await check_and_update_expired_deals(batch_size=20, age_minutes=interval_minutes)
        except Exception as e:
            logger.error(f"[Expiry Checker] Periodic loop error: {e}")
        await asyncio.sleep(interval_minutes * 60)
