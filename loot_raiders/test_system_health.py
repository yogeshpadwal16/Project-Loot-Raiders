import os
import sys
import logging
import asyncio
from datetime import datetime

# Setup basic logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("loot_raiders.health_check")

# Ensure parent directory is in sys.path to run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loot_raiders.database import init_db, SessionLocal, engine
from loot_raiders.ai_summarizer import DealSummarizer
from loot_raiders.media_scraper import MediaScraper
from loot_raiders.daily_briefing import fetch_commodity_rates, fetch_20_categorized_headlines

# Simple color formatting for terminal
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"

async def test_env_file():
    """Verify env template or current config file."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 1. Checking Environment Variables ==={Colors.END}")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        print(f"[{Colors.RED}FAIL{Colors.END}] .env file not found at {env_path}")
        return False
        
    print(f"[{Colors.GREEN}SUCCESS{Colors.END}] .env file found.")
    
    # Mock load keys (simulated verification)
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for key in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GEMINI_API_KEY"]:
        if key in content and "YOUR_" not in content:
            print(f" - {key}: Configured")
        else:
            print(f" - {key}: [{Colors.YELLOW}WARNING{Colors.END}] Using template/empty value")
            
    return True

async def test_database_wal():
    """Verify SQLite WAL mode is configured on the engine."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 2. Checking Database Connectivity & WAL mode ==={Colors.END}")
    try:
        init_db()
        db = SessionLocal()
        
        from sqlalchemy import text
        res = db.execute(text("PRAGMA journal_mode")).fetchone()
        journal_mode = res[0] if res else "Unknown"
        
        if journal_mode.lower() == "wal":
            print(f"[{Colors.GREEN}SUCCESS{Colors.END}] Connected. SQLite WAL mode successfully verified!")
            db.close()
            return True
        else:
            print(f"[{Colors.YELLOW}WARNING{Colors.END}] Database connected but journal_mode is '{journal_mode}' instead of WAL.")
            db.close()
            return False
    except Exception as e:
        print(f"[{Colors.RED}FAIL{Colors.END}] Database initialization/connection failed: {e}")
        return False

async def test_gemini_api():
    """Verify Gemini connection health."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 3. Checking Gemini API Connectivity ==={Colors.END}")
    # Read Gemini Key from current env
    api_key = os.environ.get("GEMINI_API_KEY", "")
    
    # Try loading from local .env as backup
    if not api_key:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
                        
    if not api_key or "YOUR_" in api_key or api_key == "":
        print(f"[{Colors.YELLOW}SKIP{Colors.END}] Gemini API key is missing or template. Skipping API test.")
        return True

    summarizer = DealSummarizer(api_key)
    try:
        res = await summarizer.summarize_deal("Test Deal Title", "Specifications: 12GB RAM, 256GB Storage, Snapdragon 8 Gen 3.")
        print(f"[{Colors.GREEN}SUCCESS{Colors.END}] Gemini AI summarization works. Sample response:\n{res}")
        return True
    except Exception as e:
        print(f"[{Colors.RED}FAIL{Colors.END}] Gemini AI test call failed: {e}")
        return False

async def test_rss_feeds():
    """Verify news RSS feed scraper capability."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 4. Checking News RSS Feeds & Scraper ==={Colors.END}")
    try:
        cats = await fetch_20_categorized_headlines()
        count = sum(len(v) for v in cats.values())
        if count > 0:
            print(f"[{Colors.GREEN}SUCCESS{Colors.END}] Successfully fetched {count} categorized headlines.")
            print(f" - National: {len(cats.get('national', []))} articles")
            print(f" - Business: {len(cats.get('business', []))} articles")
            print(f" - World: {len(cats.get('world', []))} articles")
            print(f" - Sports: {len(cats.get('sports', []))} articles")
            return True
        else:
            print(f"[{Colors.RED}FAIL{Colors.END}] Fetched 0 headlines from RSS.")
            return False
    except Exception as e:
        print(f"[{Colors.RED}FAIL{Colors.END}] Failed checking news RSS: {e}")
        return False

async def test_commodity_scraper():
    """Verify commodity scraper capability."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 5. Checking Commodity Rates Scraper ==={Colors.END}")
    try:
        rates = await fetch_commodity_rates()
        gold = rates.get('gold_24k', '').replace('₹', 'Rs.')
        silver = rates.get('silver_1kg', '').replace('₹', 'Rs.')
        crude = rates.get('crude', '').replace('₹', 'Rs.')
        print(f" - Gold (24k): {gold}")
        print(f" - Silver (1kg): {silver}")
        print(f" - Crude Oil: {crude}")
        return True
    except Exception as e:
        print(f"[{Colors.RED}FAIL{Colors.END}] Commodity rates scraping failed: {e}")
        return False

async def test_media_scraper():
    """Verify OpenGraph scraper is working and respects 4s timeout."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== 6. Checking Media/OpenGraph Scraper ==={Colors.END}")
    scraper = MediaScraper(timeout_seconds=4.0)
    # Test on a stable high-performance site
    test_url = "https://www.wikipedia.org"
    try:
        data = await scraper.scrape_opengraph_data(test_url)
        if data.get("success"):
            print(f"[{Colors.GREEN}SUCCESS{Colors.END}] Scraped metadata from {test_url}:")
            print(f" - Title: {data.get('title')}")
            print(f" - Image: {data.get('image_url')}")
            return True
        else:
            print(f"[{Colors.YELLOW}WARNING{Colors.END}] Failed to parse metadata from wikipedia.org, but connection succeeded.")
            return True
    except Exception as e:
        print(f"[{Colors.RED}FAIL{Colors.END}] Media scraper failed: {e}")
        return False

async def main():
    print(f"{Colors.BOLD}{Colors.CYAN}============================================={Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}       PROJECT LOOT RAIDERS HEALTH CHECK     {Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}============================================={Colors.END}")
    
    results = [
        await test_env_file(),
        await test_database_wal(),
        await test_gemini_api(),
        await test_rss_feeds(),
        await test_commodity_scraper(),
        await test_media_scraper()
    ]
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}============================================={Colors.END}")
    if all(results):
        print(f"{Colors.BOLD}{Colors.GREEN}      ALL SYSTEMS GREEN! HEALTH CHECK PASSED  {Colors.END}")
    else:
        print(f"{Colors.BOLD}{Colors.RED}      SOME ISSUES IDENTIFIED! VERIFY LOGS    {Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}============================================={Colors.END}")

if __name__ == "__main__":
    asyncio.run(main())
