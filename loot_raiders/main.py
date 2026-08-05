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
from loot_raiders.template_engine import build_html_caption, build_inline_buttons

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

    async def send_telegram_photo(self, photo_url: str, caption: str, reply_markup: dict = None):
        """Helper to send a photo message using the configured Bot Token."""
        import httpx
        
        # 1. Quality Firewall check by parsing caption
        try:
            import re
            from loot_raiders.compliance_guard import check_quality_firewall
            
            lines = [l.strip() for l in caption.split('\n') if l.strip()]
            parsed_title = ""
            parsed_price = None
            
            if len(lines) > 1:
                parsed_title = re.sub(r'<[^>]*>', '', lines[1]).strip()
                
            for line in lines:
                if "deal price" in line.lower() or "price" in line.lower():
                    price_match = re.search(r'(?:₹|rs\.?)\s*([\d,]+)', line, flags=re.IGNORECASE)
                    if price_match:
                        parsed_price = int(price_match.group(1).replace(',', ''))
                        break
                        
            if not check_quality_firewall(parsed_price, parsed_title, photo_url):
                return None
        except Exception as firewall_err:
            logger.error(f"Quality firewall in send_telegram_photo failed: {firewall_err}")

        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

        
        # Immediate fallback if photo_url is missing or invalid
        if not photo_url or not photo_url.startswith("http"):
            logger.warning("[REJECTED: NO REAL PRODUCT IMAGE]")
            return None
            
        payload = {
            "chat_id": self.chat_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                logger.info("Successfully posted photo to Telegram.")
                return res.json().get("result", {}).get("message_id")
            else:
                logger.warning(f"Failed to post photo, retrying with default banner. Error: {res.text}")
                # Try fallback photo
                payload["photo"] = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Amazon_logo.svg/1024px-Amazon_logo.svg.png"
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    logger.info("Successfully posted fallback photo to Telegram.")
                    return res.json().get("result", {}).get("message_id")
                else:
                    logger.error(f"Failed to post fallback photo to Telegram: {res.text}")
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
                        from loot_raiders.daily_briefing import build_morning_news_post
                        post_content = await build_morning_news_post()
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
            
            # 4. Format telegram deal card caption and keyboard
            deal_dict = {
                "title": deal_title,
                "price": mock_deal_data["price"],
                "mrp": mock_deal_data["mrp"],
                "url": mock_deal_data["url"],
                "platform": "amazon"
            }
            caption = build_html_caption(deal_dict)
            reply_markup = build_inline_buttons(deal_dict)
            
            # Define posting helper to tie DB save and Telegram return ID
            async def dispatch_deal_task(photo_url=og_data.get("image_url"), caption_txt=caption, markup=reply_markup, data=mock_deal_data, disc=discount, summ=summary):
                msg_id = await self.send_telegram_photo(photo_url, caption_txt, markup)
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
