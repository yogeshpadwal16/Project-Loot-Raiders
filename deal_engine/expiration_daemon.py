import asyncio
import logging
import httpx
import time
import threading
from datetime import datetime, timedelta
from database.db_session import SessionLocal
from knowledge_base.models import Product

logger = logging.getLogger("loot_raiders.expiration")

async def check_deal_stock(url: str) -> bool:
    """Simple HTTP checker to verify if item is currently out of stock."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    # Follow redirects so that we reach the final destination page (Amazon/Flipkart)
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
        try:
            resp = await client.get(url)
            text = resp.text.lower()
            out_keywords = [
                "currently unavailable",
                "out of stock",
                "sold out",
                "item not found",
                "unavailable.",
                "temporarily out of stock",
                "out of stock."
            ]
            return not any(kw in text for kw in out_keywords)
        except Exception as e:
            logger.warning(f"Stock check failed for {url}: {e}")
            return True  # Assume in stock on network error to avoid false flags

def expire_telegram_deal(product_id: str):
    from database.db_session import SessionLocal
    from knowledge_base.models import Product
    from config.settings import load_settings
    import requests
    import json

    settings = load_settings()
    bot_token = settings.get("telegram_bot_token")
    channel_id = settings.get("telegram_chat_id")
    if not bot_token or not channel_id or "YOUR_TELEGRAM" in bot_token:
        return

    db = SessionLocal()
    try:
        product = db.query(Product).filter_by(id=product_id).first()
        if not product or not product.telegram_message_id or not product.telegram_caption:
            return

        message_id = product.telegram_message_id
        original_caption = product.telegram_caption
        buy_url = product.url

        # Avoid double-expiration prefixing
        if "DEAL EXPIRED" in original_caption or "[EXPIRED]" in original_caption:
            return

        new_caption = f"❌ <b>[ DEAL EXPIRED / SOLD OUT ]</b> ❌\n\n<s>{original_caption}</s>"
        endpoint = f"https://api.telegram.org/bot{bot_token}/editMessageCaption"
        payload = {
            "chat_id": channel_id,
            "message_id": message_id,
            "caption": new_caption,
            "parse_mode": "HTML"
        }
        if buy_url and (str(buy_url).startswith("http://") or str(buy_url).startswith("https://")):
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "❌ EXPIRED / SOLD OUT ❌",
                            "url": buy_url
                        }
                    ]
                ]
            }
            payload["reply_markup"] = json.dumps(reply_markup)
        res = requests.post(endpoint, json=payload, timeout=15)
        if res.status_code == 200:
            logger.info(f"[EXPIRATION] Telegram message {message_id} marked as EXPIRED for product {product_id}.")
            product.telegram_caption = new_caption
            db.commit()
        else:
            logger.warning(f"[EXPIRATION] Failed to mark message {message_id} expired: {res.text}")
    except Exception as e:
        logger.error(f"[EXPIRATION] Error in expire_telegram_deal: {e}")
    finally:
        db.close()

async def run_expiration_daemon_loop():
    """Background loop checking active deals availability every 3 hours."""
    logger.info("Deal Expiration Daemon loop started.")
    while True:
        try:
            db = SessionLocal()
            # Fetch unexpired products created in the last 24 hours
            one_day_ago = datetime.utcnow() - timedelta(hours=24)
            active_products = db.query(Product).filter(
                Product.created_at >= one_day_ago,
                Product.telegram_message_id.isnot(None)
            ).all()
            
            logger.info(f"[EXPIRATION_DAEMON] Running deal availability check on {len(active_products)} active deals...")
            
            for p in active_products:
                if not p.telegram_caption or "DEAL EXPIRED" in p.telegram_caption or "[EXPIRED]" in p.telegram_caption:
                    continue
                    
                is_available = await check_deal_stock(p.url)
                if not is_available:
                    logger.info(f"[EXPIRED] Deal #{p.id} ({p.title[:30]}) is out of stock. Expiring on Telegram.")
                    expire_telegram_deal(p.id)
                    
            db.close()
        except Exception as loop_err:
            logger.error(f"[EXPIRATION_DAEMON] Error in daemon loop iteration: {loop_err}")
            
        await asyncio.sleep(3 * 3600)  # Sleep 3 hours

_DAEMON_STARTED = False
_DAEMON_LOCK = threading.Lock()

def start_expiration_daemon():
    """Starts the Expiration Daemon loop in a dedicated background thread (singleton)."""
    global _DAEMON_STARTED
    with _DAEMON_LOCK:
        if _DAEMON_STARTED:
            logger.info("[EXPIRATION_DAEMON] Daemon thread already running. Skipping duplicate spawn.")
            return
        _DAEMON_STARTED = True

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_expiration_daemon_loop())
        finally:
            loop.close()
        
    t = threading.Thread(target=_run, name="ExpirationDaemon", daemon=True)
    t.start()
    logger.info("Background Deal Expiration Daemon Thread launched.")
