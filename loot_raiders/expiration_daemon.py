import logging
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from loot_raiders.database import SessionLocal, Deal

logger = logging.getLogger("loot_raiders.expiration_daemon")

class ExpirationDaemon:
    def __init__(self, bot_client, chat_id: str, check_interval_seconds: int = 300):
        self.bot_client = bot_client
        self.chat_id = chat_id
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Starts the expiration daemon background loop."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            logger.info("Expiration Daemon started.")

    async def stop(self):
        """Gracefully stops the expiration daemon."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Expiration Daemon stopped.")

    async def _loop(self):
        while self._running:
            try:
                await self.check_and_expire_deals()
            except Exception as e:
                logger.error(f"Error in Expiration Daemon check loop: {e}", exc_info=True)
            await asyncio.sleep(self.check_interval_seconds)

    async def check_and_expire_deals(self):
        """Fetches active deals from the DB, checks their expiration status, and updates Telegram posts."""
        db: Session = SessionLocal()
        try:
            # Fetch deals that are not expired and are less than 48 hours old
            cutoff = datetime.utcnow() - timedelta(hours=48)
            active_deals = db.query(Deal).filter(
                Deal.is_expired == False,
                Deal.created_at > cutoff,
                Deal.mirrored_message_id != None
            ).all()
            
            logger.info(f"Checking expiration status for {len(active_deals)} active deals...")
            
            for deal in active_deals:
                # Simulation/Rule: deals older than 6 hours are expired.
                # In production, this can also check if the price went up by scraping the URL.
                is_now_expired = False
                
                # Rule 1: Time-based fallback (e.g. > 6 hours old)
                age = datetime.utcnow() - deal.created_at
                if age > timedelta(hours=6):
                    is_now_expired = True
                    reason = "Time limit exceeded (6h)"
                else:
                    # Rule 2: Random simulation or check if the URL is expired (fallback)
                    # For this template, we assume it's valid unless age exceeds limit.
                    pass

                if is_now_expired:
                    logger.info(f"Deal ID {deal.id} ('{deal.title}') marked as expired. Updating Telegram post...")
                    
                    # Update Telegram post text to mark as EXPIRED
                    success = await self.edit_telegram_post_as_expired(deal)
                    if success:
                        deal.is_expired = True
                        db.commit()
                        logger.info(f"Successfully marked Deal ID {deal.id} as expired in DB.")
        except Exception as e:
            logger.error(f"Failed during check_and_expire_deals database transaction: {e}")
        finally:
            db.close()

    async def edit_telegram_post_as_expired(self, deal: Deal) -> bool:
        """Edits an existing Telegram message to prepend '❌ EXPIRED' and strike out the grab link."""
        if not self.bot_client or not deal.mirrored_message_id:
            return False
            
        try:
            # Reconstruct the caption with expired formatting
            original_title = deal.title or "Loot Deal"
            expired_text = (
                f"❌ <b>[DEAL EXPIRED]</b> <s>{original_title}</s>\n"
                f"💰 <b>Price:</b> <s>₹{deal.price}</s> (<s>₹{deal.mrp}</s>)\n"
                f"📉 <b>Discount:</b> <s>{deal.discount}% OFF</s>\n\n"
                f"━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ \n"
                f"🔴 <i>This deal has expired. Join @LootRaidersDeals for live alerts!</i>"
            )
            
            # Using Bot API sendMessage URL if bot_client is an HTTP client,
            # or Hydrogram/Pyrogram client if it's a Client.
            # Let's support both. If bot_client has 'edit_message_text', use it.
            # Else if it is a bot token, use HTTP request.
            if hasattr(self.bot_client, "edit_message_text"):
                await self.bot_client.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=deal.mirrored_message_id,
                    text=expired_text,
                    parse_mode="HTML"
                )
            else:
                # If it's a token, make a direct request
                import httpx
                url = f"https://api.telegram.org/bot{self.bot_client}/editMessageText"
                payload = {
                    "chat_id": self.chat_id,
                    "message_id": deal.mirrored_message_id,
                    "text": expired_text,
                    "parse_mode": "HTML"
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code != 200:
                        logger.error(f"Telegram API editMessageText failed: {res.text}")
                        return False
            return True
        except Exception as e:
            logger.error(f"Failed to edit Telegram message {deal.mirrored_message_id}: {e}")
            return False
