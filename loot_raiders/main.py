import asyncio
import os
import logging
from database import init_db
from async_pipeline import DealIngestionPipeline
from expiration_daemon import ExpirationDaemon
from rate_limiter import PriorityRateLimiter
from session_manager import MultiAccountSessionManager

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("loot_raiders.main")


async def simulate_incoming_deals_stream(pipeline: DealIngestionPipeline):
    """Simulates a continuous stream of scraping events and Telegram channel messages."""
    mock_deals = [
        {
            "title": "Sony WH-1000XM4 Noise Cancelling Wireless Headphones (Black)",
            "price": 19990,
            "mrp": 29990,
            "discount": 33.0,
            "url": "https://www.amazon.in/dp/B0863TXGM3",
            "image_url": "https://images-na.ssl-images-amazon.com/images/I/71o8Q5GLUuL._SL1500_.jpg",
            "bank_offers": ["10% instant discount up to ₹1,500 on ICICI Bank Cards"]
        },
        {
            "title": "Adidas Men Supernova Glide Running Shoes Sneakers",
            "price": 3499,
            "mrp": 7999,
            "discount": 56.0,
            "url": "https://www.flipkart.com/product/p/itmd?pid=SHOFGRPH2TJHNHZM",
            "image_url": "https://rukminim2.flixcart.com/image/832/832/xif0q/shoe/s/b/g/original-imag.jpeg",
            "bank_offers": ["Flat ₹300 off on all UPI app checkouts"]
        },
        {
            "title": "3-Layer Metal Veggie Basket Trolley and Kitchen Organizer Storage Rack",
            "price": 999,
            "mrp": 2499,
            "discount": 60.0,
            "url": "https://www.amazon.in/dp/B0B3JST2F4",
            "image_url": "https://images-na.ssl-images-amazon.com/images/I/61b1R2e2J2L._SL1200_.jpg"
        }
    ]

    for i, deal in enumerate(mock_deals, 1):
        await asyncio.sleep(2) # 2-second sleep gap
        logger.info(f"[Simulator] Discovered deal #{i} on source feeds.")
        await pipeline.enqueue_deal(deal)


async def main():
    logger.info("Initializing Project Loot Raiders Production Orchestrator...")
    
    # 1. Initialize SQLite Database
    init_db()

    # 2. Load Environment Credentials
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "fake_bot_token_12345")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "@LootRaidersDeals")

    # 3. Launch Pyrogram Userbot proxy session manager
    sessions = MultiAccountSessionManager()
    await sessions.initialize_clients()

    # 4. Initialize rate limiter
    limiter = PriorityRateLimiter(min_gap_seconds=2.5)
    asyncio.create_task(limiter.run_limiter_worker())

    # 5. Launch Ingestion Pipeline
    pipeline = DealIngestionPipeline(bot_token=bot_token, chat_id=chat_id)
    pipeline.start()

    # 6. Launch Expiration daemon sweep
    daemon = ExpirationDaemon(bot_token=bot_token, channel_id=chat_id, scan_interval_seconds=30)
    daemon.start()

    # 7. Seed simulated incoming deal streaming loop
    try:
        await simulate_incoming_deals_stream(pipeline)
        
        # Keep running to process queued items and run monitors
        logger.info("Simulation completed. System idle. Monitoring daemons are active.")
        await asyncio.sleep(10)
    finally:
        # Shutdown pipelines cleanly
        await pipeline.stop()
        daemon.stop()
        logger.info("Project Loot Raiders shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
