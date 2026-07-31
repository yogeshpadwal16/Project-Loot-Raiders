import os
import sys
import logging
import asyncio
import signal
from datetime import datetime, timezone, timedelta

# Set up logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "loot_raiders.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("loot_raiders.main")

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Import local components
from loot_raiders.database import init_db, SessionLocal, Deal, Briefing
from loot_raiders.session_manager import SessionManager
from loot_raiders.rate_limiter import TeleRateLimiter
from loot_raiders.expiration_daemon import ExpirationDaemon
from loot_raiders.ai_summarizer import DealSummarizer
from loot_raiders.media_scraper import MediaScraper
from loot_raiders.daily_briefing import (
    safe_dispatch_briefing,
    IST
)

class LootRaidersOrchestrator:
    def __init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        
        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        self.sessions_config_path = os.path.join(self.config_dir, "sessions_config.json")
        
        # Instantiate modules
        self.session_mgr = SessionManager(self.sessions_config_path)
        self.rate_limiter = TeleRateLimiter(min_interval=2.5)
        self.expiration_daemon = ExpirationDaemon(self.bot_token, self.chat_id, check_interval_seconds=300)
        self.summarizer = DealSummarizer(self.gemini_key)
        self.media_scraper = MediaScraper(timeout_seconds=4.0)
        
        self.is_running = False
        self.tasks = []

    async def initialize(self):
        logger.info("Initializing Loot Raiders Platform...")
        init_db()
        await self.session_mgr.start()
        self.rate_limiter.start()
        self.expiration_daemon.start()
        self.is_running = True

    async def shutdown(self):
        if not self.is_running:
            return
        logger.info("Initiating graceful shutdown sequence...")
        self.is_running = False
        
        # Stop background daemons
        await self.expiration_daemon.stop()
        await self.rate_limiter.stop()
        await self.session_mgr.stop()
        
        # Cancel all running asyncio tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        logger.info("Graceful shutdown completed successfully.")

    async def send_telegram_raw(self, text: str):
        """Helper to send a message using the configured Bot Token."""
        import httpx
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                logger.info("Successfully posted message to Telegram.")
                return res.json().get("result", {}).get("message_id")
            else:
                logger.error(f"Failed to post to Telegram: {res.text}")
                return None

    async def schedule_daily_briefing_loop(self):
        """Monitors clock time and runs daily briefing at 08:00 AM IST."""
        logger.info("Daily Briefing Scheduler loop activated.")
        while self.is_running:
            try:
                now = datetime.now(IST)
                if now.hour == 8 and now.minute == 0:
                    logger.info("08:00 AM IST detected. Generating Morning Briefing...")
                    
                    # Enqueue briefing dispatcher (Priority 2: News / Scheduled)
                    await self.rate_limiter.enqueue(
                        priority=2,
                        func=lambda: safe_dispatch_briefing(self.send_telegram_raw),
                        description="Sakal Morning News Briefing"
                    )
                    
                    # Save briefing metadata to DB
                    db = SessionLocal()
                    try:
                        from loot_raiders.daily_briefing import generate_esakal_only_post
                        post_content = await generate_esakal_only_post()
                        if post_content:
                            briefing_record = Briefing(
                                date=now.strftime("%Y-%m-%d"),
                                english_text=post_content,
                                marathi_text=post_content
                            )
                            db.add(briefing_record)
                            db.commit()
                    except Exception as db_err:
                        logger.error(f"Failed to save briefing to DB: {db_err}")
                    finally:
                        db.close()
                        
                    # Avoid double-triggering in the same minute
                    await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in daily briefing scheduler: {e}", exc_info=True)
                
            await asyncio.sleep(30)

    async def simulate_deal_mirroring_listener(self):
        """
        Simulates mirroring listener or intercepts updates from userbots.
        Processes intercepted deal posts, rewrites them, and posts via Bot API.
        """
        logger.info("Starting Deal Mirroring Listener...")
        # For simulation, we wait a moment and post a test deal to demonstrate mirroring functionality.
        await asyncio.sleep(15)
        
        while self.is_running:
            logger.info("Listening for new deals from source channels...")
            
            # Mock transaction data structure simulating an incoming userbot update
            mock_deal_data = {
                "original_msg_id": 9999 + int(datetime.utcnow().timestamp() % 1000),
                "source_channel": "@SampleLootChannel",
                "title": "Amazon Brand - Solimo Water Resistant Cotton Mattress Protector",
                "url": "https://www.amazon.in/dp/B07T4M6B75",
                "price": 499.0,
                "mrp": 1299.0,
                "raw_specs": "Features: Water resistant, cotton fabric, elastic band fitment. 1 Year warranty."
            }
            
            logger.info(f"Mirrored message intercepted: ID {mock_deal_data['original_msg_id']}")
            
            # 1. Scrape OG data for verification
            og_data = await self.media_scraper.scrape_opengraph_data(mock_deal_data["url"])
            deal_title = og_data.get("title") or mock_deal_data["title"]
            
            # 2. Get AI 3-bullet summary
            summary = await self.summarizer.summarize_deal(deal_title, mock_deal_data["raw_specs"])
            
            # 3. Calculate discount percentage
            discount = ((mock_deal_data["mrp"] - mock_deal_data["price"]) / mock_deal_data["mrp"]) * 100
            
            # 4. Format telegram deal card HTML
            deal_card = (
                f"🔥 <b>LOOT DEAL DETECTED!</b> 🔥\n\n"
                f"📦 <b>Product:</b> {deal_title}\n"
                f"💰 <b>Deal Price:</b> <code>₹{mock_deal_data['price']:.0f}</code> (<s>₹{mock_deal_data['mrp']:.0f}</s>)\n"
                f"📉 <b>Discount:</b> {discount:.0f}% OFF!\n\n"
                f"📋 <b>Key Highlights:</b>\n"
                f"{summary}\n\n"
                f"👉 <b><a href='{mock_deal_data['url']}'>GRAB THIS DEAL NOW</a></b>\n"
                f"━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ \n"
                f"📢 Join <b>@LootRaidersDeals</b> for more fast alerts!"
            )
            
            # Define posting helper to tie DB save and Telegram return ID
            async def dispatch_deal_task(card_html=deal_card, data=mock_deal_data, disc=discount, summ=summary):
                msg_id = await self.send_telegram_raw(card_html)
                if msg_id:
                    db = SessionLocal()
                    try:
                        new_deal = Deal(
                            original_message_id=data["original_msg_id"],
                            mirrored_message_id=msg_id,
                            source_channel=data["source_channel"],
                            target_channel=self.chat_id,
                            title=data["title"],
                            url=data["url"],
                            price=data["price"],
                            mrp=data["mrp"],
                            discount=disc,
                            summary=summ
                        )
                        db.add(new_deal)
                        db.commit()
                        logger.info(f"Mirrored deal saved in database with target message ID: {msg_id}")
                    except Exception as db_err:
                        logger.error(f"Error saving deal to DB: {db_err}")
                    finally:
                        db.close()
            
            # 5. Enqueue post task to Rate Limiter (Priority 1: Alerts / Urgent)
            await self.rate_limiter.enqueue(
                priority=1,
                func=dispatch_deal_task,
                description=f"Mirror alert for '{deal_title[:30]}...'"
            )
            
            # Wait 30 minutes before generating next simulated mirroring deal
            await asyncio.sleep(1800)

async def main():
    orchestrator = LootRaidersOrchestrator()
    
    # Graceful shutdown handler registration
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(orchestrator.shutdown()))
        except NotImplementedError:
            # Handle Windows compatibility where add_signal_handler is not implemented
            pass

    try:
        await orchestrator.initialize()
        
        # Gather concurrent daemon tasks
        briefing_task = asyncio.create_task(orchestrator.schedule_daily_briefing_loop())
        mirroring_task = asyncio.create_task(orchestrator.simulate_deal_mirroring_listener())
        
        orchestrator.tasks.extend([briefing_task, mirroring_task])
        
        # Keep orchestrator running
        await asyncio.gather(*orchestrator.tasks)
    except asyncio.CancelledError:
        logger.info("Master tasks cancelled by shutdown signal.")
    except Exception as e:
        logger.error(f"Fatal error in Orchestrator master loop: {e}", exc_info=True)
    finally:
        await orchestrator.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Program exiting.")
