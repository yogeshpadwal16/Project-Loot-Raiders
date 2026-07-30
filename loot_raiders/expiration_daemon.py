import asyncio
import logging
import time
import requests
from database import SessionLocal, Product, PriceHistory

logger = logging.getLogger("loot_raiders.expiration")


class ExpirationDaemon:
    """
    Background daemon loop that periodically scans SQLite database records
    to check if active deals have expired, and updates Telegram posts dynamically.
    """
    def __init__(self, bot_token: str, channel_id: str, scan_interval_seconds: int = 60):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.scan_interval_seconds = scan_interval_seconds
        self.is_running = False
        self.task = None

    async def _scan_and_expire_deals(self):
        """Scans recent active products and flags those whose price has returned to normal."""
        db = SessionLocal()
        try:
            # Get products posted in the last 24 hours that have telegram message IDs
            day_ago = time.time() - 86400
            active_products = db.query(Product).filter(
                Product.created_at >= day_ago,
                Product.telegram_message_id.isnot(None)
            ).all()

            for product in active_products:
                # Retrieve the latest scanned price entry
                latest = db.query(PriceHistory).filter_by(
                    product_id=product.id
                ).order_by(PriceHistory.timestamp.desc()).first()

                if not latest:
                    continue

                # Check expiration rule: if price went back up near MRP
                # e.g., price increase of more than 20% compared to discount price, or price >= 95% of MRP
                if latest.mrp > latest.price and latest.price >= int(latest.mrp * 0.95):
                    logger.info(f"[Daemon] Price glitch/discount ended for {product.title[:35]}. Expiring post.")
                    await self.expire_telegram_post(product.telegram_message_id, product.title, product.url)
                    
                    # Update database product message details to prevent double edits
                    product.telegram_message_id = None
                    db.commit()

        except Exception as e:
            logger.error(f"[Daemon] Expiration sweep failed: {e}")
        finally:
            db.close()

    async def expire_telegram_post(self, message_id: int, title: str, buy_url: str):
        """Dispatches HTML caption edit to Telegram, marking the deal expired."""
        if not self.bot_token or not self.channel_id or "YOUR_TELEGRAM" in self.bot_token:
            return

        new_caption = (
            f"❌ <b>[ DEAL EXPIRED / SOLD OUT ]</b> ❌\n\n"
            f"<s>📦 {title[:80]}...</s>\n\n"
            f"<i>This pricing error or flash deal has expired. Turn on notifications so you never miss another loot!</i>"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "❌ EXPIRED / SOLD OUT ❌", "url": buy_url}
                ]
            ]
        }

        url = f"https://api.telegram.org/bot{self.bot_token}/editMessageCaption"
        payload = {
            "chat_id": self.channel_id,
            "message_id": message_id,
            "caption": new_caption,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }

        try:
            # Run in a non-blocking threadpool to prevent queue blocking
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(
                None, lambda: requests.post(url, json=payload, timeout=8)
            )
            if res.status_code == 200:
                logger.info(f"[Daemon] Expired post successfully edited for message ID: {message_id}")
            else:
                logger.warning(f"[Daemon] Failed to edit expired post: {res.text}")
        except Exception as e:
            logger.error(f"[Daemon] Failed sending telegram edit: {e}")

    async def _daemon_loop(self):
        while self.is_running:
            await self._scan_and_expire_deals()
            await asyncio.sleep(self.scan_interval_seconds)

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.task = asyncio.create_task(self._daemon_loop())
        logger.info("[Daemon] Expiration check daemon task started.")

    def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
        logger.info("[Daemon] Expiration check daemon task stopped.")
