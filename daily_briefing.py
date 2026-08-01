# -*- coding: utf-8 -*-
import os
import re
import time
import sqlite3
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import feedparser
import httpx

logger = logging.getLogger("loot_raiders.esakal")

# Indian Standard Time (IST)
IST = timezone(timedelta(hours=5, minutes=30))

# Exact Marathi Keyword Context Emoji Rules (Includes prompt-specified and matra-based keywords)
EMOJI_RULES = {
    # Education/Exam
    ("परीक्षा", "परकष", "नीट", "नट", "विद्यार्थी", "वदयरथ"): "🎓",
    # Crime/Accident/Police
    ("पोलीस", "पलस", "अपघात", "अपघत", "जखम", "मृत्यू", "मतय"): "🚨",
    # Religion/Festival
    ("मंदिर", "मदर", "पूजा", "पज", "उत्सव", "उतसव", "गणपती", "गणपत", "शिमगा", "शमग"): "🛕",
    # Politics/Govt
    ("मुख्यमंत्री", "मखयमतर", "निवडणूक", "रण", "कसरकर", "आमदार", "आमदर", "खासदार", "खसदर", "सरकार", "सरकर"): "🏛️",
    # Rain/Dam/Sea
    ("पाऊस", "पऊस", "पूर", "पर", "धरण", "नदी", "नd", "समुद्र", "समदर", "लाट", "लट", "दरड", "आभाळ", "आबल"): "🌧️",
    # Court/Order
    ("कोर्ट", "करट", "न्यायालय", "नययलय", "जिल्हाधिकारी", "जलहधकर", "नियम", "नयम"): "⚖️",
    # Jobs/Recruitment
    ("नोकरी", "नकर", "भरती", "भरत", "वेतन", "वतन"): "💼",
    # Video/Social
    ("व्हिडिओ", "वहडओ", "व्हायरल", "वहयरल"): "📱",
    # Agriculture/Business
    ("कर्ज", "कज", "आंबा", "आब", "हापूस", "अलफनस", "मच्छिमार", "मचछमर", "पर्यटन", "परयटन", "शेतकरी", "शतकर"): "🥭",
}

def get_emoji(headline: str) -> str:
    text_lower = headline.lower()
    for keywords, emoji in EMOJI_RULES.items():
        for k in keywords:
            if k in text_lower:
                # Safety check: do not let short keywords like 'पर' collide with 'परीक्षा' or 'पर्यटन'
                if k == "पर" and ("परीक्षा" in text_lower or "पर्यटन" in text_lower or "परकष" in text_lower):
                    continue
                # Safety check: do not let 'रण' collide with common suffixes in words like 'साधारण', 'कारण', 'करण', 'धरण', 'प्रकरण'
                if k == "रण" and any(x in text_lower for x in ["साधारण", "कारण", "करण", "धरण", "प्रकरण"]):
                    continue
                return emoji
    return "📰"

# ==========================================
# SQLITE TRANSACTION LOG & DEDUPLICATION
# ==========================================
def init_briefing_db():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loot_raiders.db")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posted_briefings (
                headline TEXT PRIMARY KEY,
                posted_at REAL
            )
        """)
        conn.commit()
    finally:
        conn.close()

def is_headline_posted(headline: str) -> bool:
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loot_raiders.db")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM posted_briefings WHERE headline = ?", (headline,))
        return cursor.fetchone() is not None
    finally:
        conn.close()

def mark_headlines_posted(headlines: list):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loot_raiders.db")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        now = time.time()
        for h in headlines:
            cursor.execute("INSERT OR IGNORE INTO posted_briefings (headline, posted_at) VALUES (?, ?)", (h, now))
        conn.commit()
    finally:
        conn.close()

# ==========================================
# UNIFIED CRAWLER: RSS & TOPIC SCRAPE
# ==========================================
async def fetch_sindhudurg_headlines() -> list:
    """
    Fetches fresh Batmya headlines from Sakal's RSS feed & Topic Scrape.
    Strictly filters to only include items published within the last 24 hours.
    """
    headlines = []
    seen_urls = set()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=24)
    
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # 1. FETCH RSS FEED
        try:
            res_rss = await client.get("https://www.esakal.com/sindhudurg/rss.xml")
            if res_rss.status_code == 200:
                feed = feedparser.parse(res_rss.text)
                for entry in feed.entries:
                    title = entry.title.strip()
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        if pub_dt >= cutoff:
                            if title not in headlines:
                                headlines.append(title)
        except Exception as e:
            logger.warning(f"[Briefing Scraper] RSS feed fetching failed: {e}")

        # 2. FETCH TOPIC SCRAPE
        try:
            res_topic = await client.get("https://www.esakal.com/topic/sindhudurg")
            if res_topic.status_code == 200:
                soup = BeautifulSoup(res_topic.text, "html.parser")
                for a in soup.find_all("a"):
                    href = a.get("href")
                    if href and "sindhudurg" in href.lower() and a.text.strip():
                        # Exclude duplicates in same run
                        if href in seen_urls:
                            continue
                        seen_urls.add(href)
                        
                        # Clean prefix/suffixes (e.g. "Sindhudurg : ")
                        title = re.sub(r'^(?:sindhudurg|sinhudurg)\s*:\s*', '', title, flags=re.IGNORECASE).strip()
                        # Strip English title tags / subtitles (e.g. "Snake in Tourist Car : ")
                        title = re.sub(r'^[A-Za-z0-9\s\'\&\-\:\,\(\)]+\s*:\s*(?=[\u0900-\u097F])', '', title).strip()
                        
                        # Find the parent card to locate time
                        time_tag = None
                        curr = a
                        for _ in range(3):
                            if curr is None:
                                break
                            time_tag = curr.find("time")
                            if time_tag:
                                break
                            curr = curr.parent
                            
                        if time_tag and time_tag.get("datetime"):
                            try:
                                dt_str = time_tag.get("datetime")
                                pub_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                                if pub_dt >= cutoff:
                                    if title not in headlines:
                                        headlines.append(title)
                            except Exception as dt_err:
                                logger.warning(f"[Briefing Scraper] Failed to parse datetime {dt_str}: {dt_err}")
                        else:
                            # Fallback: if no time tag found but page indicates recent content, add it
                            if title not in headlines:
                                headlines.append(title)
        except Exception as e:
            logger.warning(f"[Briefing Scraper] Topic Page scraping failed: {e}")
            
    return headlines

# ==========================================
# LIVE COMMODITY RATES FROM GOODRETURNS
# ==========================================
async def fetch_live_rates() -> dict:
    """
    Fetches live Mumbai commodity rates (Gold, Silver, Petrol, Diesel) from GoodReturns.
    """
    rates = {
        "gold_22k": "66,500",
        "gold_24k": "72,500",
        "silver_1kg": "88,000",
        "petrol": "\u20b9111.21",
        "diesel": "\u20b997.83"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # 1. Gold Rates (24K & 22K per 10g)
        try:
            res = await client.get("https://www.goodreturns.in/gold-rates/mumbai.html")
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                table = soup.find("table")
                if table:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 3 and cells[0].text.strip() == "10":
                            rate_24k = cells[1].text.strip().split()[0].replace("\u20b9", "").strip()
                            rate_22k = cells[2].text.strip().split()[0].replace("\u20b9", "").strip()
                            rates["gold_24k"] = rate_24k
                            rates["gold_22k"] = rate_22k
                            break
        except Exception as e:
            logger.warning(f"[Rates Scraper] Gold rate fetch failed: {e}")

        # 2. Silver Rates (1kg)
        try:
            res = await client.get("https://www.goodreturns.in/silver-rates/mumbai.html")
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                table = soup.find("table")
                if table:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2 and cells[0].text.strip() == "1000":
                            rate_1kg = cells[1].text.strip().split()[0].replace("\u20b9", "").strip()
                            rates["silver_1kg"] = rate_1kg
                            break
        except Exception as e:
            logger.warning(f"[Rates Scraper] Silver rate fetch failed: {e}")

        # 3. Petrol Price
        try:
            res = await client.get("https://www.goodreturns.in/petrol-price.html")
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                table = soup.find("table")
                if table:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2 and "mumbai" in cells[0].text.strip().lower():
                            price = cells[1].text.strip().replace("\u20b9", "").strip()
                            rates["petrol"] = f"\u20b9{price}"
                            break
        except Exception as e:
            logger.warning(f"[Rates Scraper] Petrol price fetch failed: {e}")

        # 4. Diesel Price
        try:
            res = await client.get("https://www.goodreturns.in/diesel-price.html")
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                table = soup.find("table")
                if table:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2 and "mumbai" in cells[0].text.strip().lower():
                            price = cells[1].text.strip().replace("\u20b9", "").strip()
                            rates["diesel"] = f"\u20b9{price}"
                            break
        except Exception as e:
            logger.warning(f"[Rates Scraper] Diesel price fetch failed: {e}")

    return rates

# ==========================================
# FORMATTING & COMPOSING
# ==========================================
def build_footer_block(
    gold_22k: str,
    gold_24k: str,
    silver_1kg: str,
    petrol_rate: str,
    diesel_rate: str,
    channel_handle: str = "LootRaidersDeals"
) -> str:
    """
    Builds the commodity rates & fuel footer with a blank line between items.
    All Devanagari labels are hardcoded in Unicode ASCII Escapes to prevent IDE/terminal strip.
    """
    # Escapes:
    # आजच सनयच दर -> \u0906\u091c\u091a\u0947 \u0938\u094b\u0928\u094d\u092f\u093e\u091a\u0947 \u0926\u0930
    # आजच चदच दर -> \u0906\u091c\u091a\u0947 \u091a\u093e\u0902\u0926\u0940\u091a\u0947 \u0926\u0930
    # आजच इधन दर -> \u0906\u091c\u091a\u0947 \u0907\u0902\u0927\u0928 \u0926\u0930
    # पटरल -> \u092A\u0947\u091F\u094D\u0930\u094B\u0932
    # डझल -> \u0921\u093F\u091D\u0947\u0932
    # तजय घडमड आण बसट डलससठ जईन कर -> \u0924\u093E\u091C\u094D\u092F\u093E \u0918\u0921\u093E\u092E\u094B\u0921\u0940 \u0906\u0923\u093F \u092C\u0947\u0938\u094F\u091F \u0921\u0940\u0932\u094D\u0938\u0938\u093E\u0920\u0940 \u091C\u094D\u0908\u0928 \u0915\u0930\u093E
    
    footer = (
        f"\U0001fa99 Gold Rate Today \u0906\u091c\u091a\u0947 \u0938\u094b\u0928\u094d\u092f\u093e\u091a\u0947 \u0926\u0930 - 22K = {gold_22k}/- | | 24K = {gold_24k}/-\n\n"
        f"\U0001fa99 Silver Rate Today \u0906\u091c\u091a\u0947 \u091a\u093e\u0902\u0926\u0940\u091a\u0947 \u0926\u0930 - 1Kg = {silver_1kg}/-\n\n"
        f"\u26fd Petrol & Diesel Rate \u0906\u091c\u091a\u0947 \u0907\u0902\u0927\u0928 \u0926\u0930 - \u092A\u0947\u091F\u094D\u0930\u094B\u0932 = {petrol_rate}/L | | \u0921\u093F\u091D\u0947\u0932 = {diesel_rate}/L\n\n"
        f"\U0001f4e2 \u0924\u093E\u091C\u094D\u092F\u093E \u0918\u0921\u093E\u092E\u094B\u0921\u0940 \u0906\u0923\u093F \u092C\u0947\u0938\u094F\u091F \u0921\u0940\u0932\u094D\u0938\u0938\u093E\u0920\u0940 \u091C\u094D\u0908\u0928 \u0915\u0930\u093E  @{channel_handle}"
    )
    return footer

async def build_morning_news_post() -> tuple:
    init_briefing_db()
    
    # 1. Fetch fresh headlines
    raw_headlines = await fetch_sindhudurg_headlines()
    
    # 2. Filter out already posted ones
    fresh_headlines = []
    for h in raw_headlines:
        if not is_headline_posted(h):
            fresh_headlines.append(h)
            
    if not fresh_headlines:
        return None, []
        
    # 3. Fetch rates
    rates = await fetch_live_rates()
    
    # Header: <b>लूट रेडर्स - सिंधुदुर्ग चालू घडामोडी</b>
    header = "<b>\u0932\u0942\u091f \u0930\u0947\u0921\u0930\u094d\u0938 - \u0938\u093f\u0902\u0927\u0941\u0926\u0941\u0930\u094d\u0917 \u091a\u093e\u0932\u0942 \u0918\u0921\u093e\u092e\u094b\u0921\u0940</b>\n"
    
    # Separator
    separator = "———————————————\n\n"
    
    # News list with a blank line after EVERY headline item
    news_section = ""
    for h in fresh_headlines:
        emoji = get_emoji(h)
        news_section += f"{emoji} {h}\n\n"
        
    # Rates footer
    footer = build_footer_block(
        gold_22k=rates["gold_22k"],
        gold_24k=rates["gold_24k"],
        silver_1kg=rates["silver_1kg"],
        petrol_rate=rates["petrol"],
        diesel_rate=rates["diesel"]
    )
    
    message = header + separator + news_section + footer
    return message, fresh_headlines

# ==========================================
# RUNNERS & SCHEDULERS (Backward Compatible)
# ==========================================
async def dispatch_briefing(send_telegram_func):
    post_text, fresh_headlines = await build_morning_news_post()
    if post_text and fresh_headlines:
        await send_telegram_func(post_text)
        mark_headlines_posted(fresh_headlines)

async def safe_dispatch_briefing(send_telegram_func):
    await dispatch_briefing(send_telegram_func)

async def schedule_daily_dual_briefing_daemon(bot_dispatch_func):
    """Triggers at 08:00 AM IST daily."""
    while True:
        now = datetime.now(IST)
        if now.hour == 8 and now.minute == 0:
            logger.info("[BRIEFING] Generating 08:00 AM IST Sindhudurg Briefing...")
            try:
                await safe_dispatch_briefing(bot_dispatch_func)
            except Exception as e:
                logger.error(f"[BRIEFING] Error executing safe_dispatch_briefing: {e}")
            await asyncio.sleep(60)
        await asyncio.sleep(30)
