"""
scripts/clear_telegram_channel.py
Cleans and purges all previous bot messages from the Telegram channel for a fresh start.
Deletes tracked messages from database and sweeps recent channel message IDs.
"""

import os
import sys
import time
import logging
import requests
from config.settings import load_settings
from database.db_session import SessionLocal
from knowledge_base.models import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ChannelCleaner")


def clear_telegram_channel_messages():
    settings = load_settings()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or settings.get("telegram_bot_token")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or settings.get("telegram_chat_id")

    if not bot_token or not chat_id or "YOUR_TELEGRAM" in bot_token:
        logger.error("Telegram bot token or chat ID is missing/invalid.")
        return

    logger.info(f"Initiating channel purge for target channel: {chat_id}")
    
    # 1. Collect all known message IDs from the database
    db = SessionLocal()
    db_message_ids = set()
    try:
        products = db.query(Product).filter(Product.telegram_message_id != None).all()
        for p in products:
            if p.telegram_message_id:
                db_message_ids.add(int(p.telegram_message_id))
    except Exception as db_err:
        logger.warning(f"Error querying database message IDs: {db_err}")
    finally:
        db.close()

    logger.info(f"Found {len(db_message_ids)} tracked message IDs in database.")

    # 2. Determine maximum message ID range to sweep
    max_id = max(db_message_ids) if db_message_ids else 500
    sweep_ids = set(range(1, max_id + 150)).union(db_message_ids)

    delete_url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
    deleted_count = 0

    for msg_id in sorted(sweep_ids, reverse=True):
        try:
            res = requests.post(
                delete_url,
                json={"chat_id": chat_id, "message_id": msg_id},
                timeout=5
            )
            if res.status_code == 200 and res.json().get("ok"):
                deleted_count += 1
                logger.info(f"🗑️ Deleted message ID: {msg_id}")
                time.sleep(0.08) # Rate-limit protection
        except Exception as e:
            logger.debug(f"Failed deleting message {msg_id}: {e}")

    logger.info(f"Purge complete! Successfully deleted {deleted_count} messages from {chat_id}.")

    # 3. Reset database publication state for fresh discovery
    db = SessionLocal()
    try:
        db.query(Product).update({
            Product.telegram_message_id: None,
            Product.telegram_caption: None,
            Product.last_published_at: None,
            Product.last_published_price: None,
            Product.daily_post_count: 0
        })
        db.commit()
        logger.info("Database publication tracking reset to 0.")
    except Exception as reset_err:
        db.rollback()
        logger.warning(f"Database reset error: {reset_err}")
    finally:
        db.close()


if __name__ == "__main__":
    clear_telegram_channel_messages()
