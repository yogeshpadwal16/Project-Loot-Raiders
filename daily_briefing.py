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

import html
NEWS_RSS_URL = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"

BUSINESS_RE = re.compile(
    r"\b(market|sensex|nifty|profit|tech|bank|shares|ceo|uber|rapido|petrol|tax)\b",
    re.IGNORECASE,
)
SPORTS_RE = re.compile(
    r"\b(cricket|match|trophy|messi|olympic|bcci|won|final|medal|ipl)\b",
    re.IGNORECASE,
)
WORLD_RE = re.compile(
    r"\b(us|china|iran|pakistan|world|ukraine|russia|un|biden|trump)\b",
    re.IGNORECASE,
)

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
    Fetches all Batmya headlines from Sakal's RSS feed & Topic Scrape.
    Duplicates are filtered using the database posted_briefings table.
    """
    headlines = []
    seen_urls = set()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # 1. FETCH RSS FEED
        try:
            res_rss = await client.get("https://www.esakal.com/sindhudurg/rss.xml")
            if res_rss.status_code == 200:
                feed = feedparser.parse(res_rss.text)
                for entry in feed.entries:
                    title = entry.title.strip()
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
                        
                        title = a.text.strip()
                        # Clean prefix/suffixes (e.g. "Sindhudurg : ")
                        title = re.sub(r'^(?:sindhudurg|sinhudurg)\s*:\s*', '', title, flags=re.IGNORECASE).strip()
                        # Strip English title tags / subtitles (e.g. "Snake in Tourist Car : ")
                        title = re.sub(r'^[A-Za-z0-9\s\'\&\-\:\,\(\)]+\s*:\s*(?=[\u0900-\u097F])', '', title).strip()
                        
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
        f"\U0001f7e1 Gold Rate Today \u0906\u091c\u091a\u0947 \u0938\u094b\u0928\u094d\u092f\u093e\u091a\u0947 \u0926\u0930 - 22K = {gold_22k}/- | | 24K = {gold_24k}/-\n\n"
        f"\u26aa Silver Rate Today \u0906\u091c\u091a\u0947 \u091a\u093e\u0902\u0926\u0940\u091a\u0947 \u0926\u0930 - 1Kg = {silver_1kg}/-\n\n"
        f"\u26fd Petrol & Diesel Rate \u0906\u091c\u091a\u0947 \u0907\u0902\u0927\u0928 \u0926\u0930 - \u092A\u0947\u091F\u094D\u0930\u094B\u0932 = {petrol_rate}/L | | \u0921\u093F\u091D\u0947\u0932 = {diesel_rate}/L\n\n"
        f"\U0001f4e2 \u0924\u093e\u091c\u094d\u092f\u093e \u0918\u0921\u093e\u092e\u094b\u0921\u0940 \u0906\u0923\u093f \u092c\u0947\u0938\u094d\u091f \u0921\u0940\u0932\u094d\u0938\u0938\u093e\u0920\u0940 \u091c\u0949\u0908\u0928 \u0915\u0930\u093e  @{channel_handle}"
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

async def fetch_20_categorized_headlines() -> dict:
    """Fetches 20 headlines from Google News RSS and categorizes them into 4 structured sections."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(NEWS_RSS_URL)
            feed = feedparser.parse(resp.text)

            categories = {
                "national": [],
                "business": [],
                "world": [],
                "sports": [],
            }

            for entry in feed.entries:
                # Strip publisher suffix (e.g. " - The Hindu")
                title = entry.title.split(" - ")[0].strip()
                clean_title = html.escape(title)

                is_categorized = False

                # Apply Taxonomy matching with Regex word boundary searches
                if BUSINESS_RE.search(clean_title):
                    if len(categories["business"]) < 5:
                        categories["business"].append(clean_title)
                        is_categorized = True

                if not is_categorized and SPORTS_RE.search(clean_title):
                    if len(categories["sports"]) < 5:
                        categories["sports"].append(clean_title)
                        is_categorized = True

                if not is_categorized and WORLD_RE.search(clean_title):
                    if len(categories["world"]) < 5:
                        categories["world"].append(clean_title)
                        is_categorized = True

                # Fallback to national if it doesn't match any category, or if matched categories are full
                if not is_categorized:
                    if len(categories["national"]) < 6:
                        categories["national"].append(clean_title)

                # Stop once we have reached 20 headlines total
                if sum(len(v) for v in categories.values()) >= 20:
                    break

            return categories

        except Exception as e:
            logger.error(f"[BRIEFING_ERROR] Failed fetching RSS headlines: {e}")
            return {
                "national": ["Major national updates loading..."],
                "business": [],
                "world": [],
                "sports": [],
            }

def build_english_post(cats: dict, rates: dict) -> str:
    """Builds primary English Telegram HTML post."""
    today_str = datetime.now(IST).strftime("%A, %d %B %Y")

    caption = "📰 <b>LOOT RAIDERS DAILY MORNING BRIEFING</b>\n"
    caption += f"<i>{today_str}</i>\n\n"

    caption += "<blockquote>"
    caption += "<b>Commodity & Market Snapshot</b>\n"
    caption += f"🪙 <b>Gold (24K):</b> {rates['gold_24k']}\n"
    caption += f"🥈 <b>Silver (1kg):</b> {rates['silver_1kg']}\n"
    caption += f"⛽ <b>Petrol & Diesel:</b> Petrol = {rates['petrol']}/L | Diesel = {rates['diesel']}/L\n"
    caption += "</blockquote>\n\n"

    if cats["national"]:
        caption += "<blockquote>"
        caption += "<b>National & Policy News</b>\n"
        for h in cats["national"]:
            caption += f"• {h}\n"
        caption += "</blockquote>\n\n"

    if cats["business"]:
        caption += "<blockquote>"
        caption += "<b>Business, Tech & Economy</b>\n"
        for h in cats["business"]:
            caption += f"• {h}\n"
        caption += "</blockquote>\n\n"

    if cats["world"]:
        caption += "<blockquote>"
        caption += "<b>Global News</b>\n"
        for h in cats["world"]:
            caption += f"• {h}\n"
        caption += "</blockquote>\n\n"

    if cats["sports"]:
        caption += "<blockquote>"
        caption += "<b>Sports Updates</b>\n"
        for h in cats["sports"]:
            caption += f"• {h}\n"
        caption += "</blockquote>\n\n"

    caption += "<i>Stay tuned for top loot deals & price drops coming up today!</i>\n"
    caption += "Join <b>@LootRaidersDeals</b>"

    return caption

async def translate_to_proficient_marathi(english_post: str) -> str:
    """Translates English post into high-proficiency journalistic Marathi (शुद्ध प्रमाण मराठी) using Gemini."""
    try:
        from config.settings import load_settings
        import google.generativeai as genai
        
        settings = load_settings()
        api_key = settings.get("gemini_api_key")
        if not api_key or "YOUR_GEMINI" in api_key or api_key.strip() == "":
            logger.warning("[MARATHI_FAIL] Gemini API key not configured. Returning untranslated post.")
            return english_post
            
        genai.configure(api_key=api_key)
        ai_model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
        You are a Senior Editor for a premier Marathi daily newspaper. 
        Translate the following English news briefing into highly proficient, natural, standard Marathi (शुद्ध प्रमाण मराठी).

        LANGUAGE & JOURNALISTIC RULES:
        1. Avoid literal word-for-word translation. Use authentic Marathi news terms:
           - "Paper leak" -> "पेपरफुटी प्रकरण"
           - "Death toll" -> "मृत्यूचा आकडा"
           - "Trial run" -> "यशस्वी चाचणी"
           - "Subsidies" -> "अनुदान"
           - "Retirement" -> "सर्व प्रकारच्या क्रिकेटमधून निवृत्ती"
        2. SECTION HEADINGS STANDARD:
           - "LOOT RAIDERS DAILY MORNING BRIEFING" -> "लूट रेडर्स : दैनिक प्रभात वृत्त"
           - "Commodity & Market Snapshot" -> "बाजारभाव आणि धातूंचे दर"
           - "National & Policy News" -> "राष्ट्रीय व धोरणात्मक घडामोडी"
           - "Business, Tech & Economy" -> "उद्योग, तंत्रज्ञान आणि अर्थकारण"
           - "Global News" -> "जागतिक घडामोडी"
           - "Sports Updates" -> "क्रीडा जगत"
           - "Stay tuned for top loot deals & price drops coming up today!" -> "आजच्या धमाकेदार डील्स आणि डिस्काउंट्ससाठी चॅनलवर अपडेट राहा!"
           - "Join @LootRaidersDeals" -> "सामील व्हा @LootRaidersDeals"
        3. STRICTLY PRESERVE ALL HTML TAGS: Do not modify or delete <blockquote>, </blockquote>, <b>, </b>, <i>, </i> tags.
        4. PRESERVE NUMBERS & CURRENCIES: Keep values, numbers, and emojis intact.

        English Text:
        {english_post}
        """

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: ai_model.generate_content(prompt))
        translated_text = response.text.strip()
        
        if translated_text.startswith("```"):
            lines = translated_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            translated_text = "\n".join(lines).strip()
            
        return translated_text
    except Exception as e:
        logger.error(f"[MARATHI_FAIL] Gemini API translation failed: {e}")
        return english_post

async def dispatch_general_briefing(send_telegram_func):
    """Fetches, builds, and dispatches the general news briefing in English, followed by Marathi."""
    try:
        cats = await fetch_20_categorized_headlines()
        rates = await fetch_live_rates()
        
        rates_snapshot = {
            "gold_24k": f"₹{rates['gold_24k']} (10g)" if rates['gold_24k'] != "N/A" else "₹74,250 (10g)",
            "silver_1kg": f"₹{rates['silver_1kg']}" if rates['silver_1kg'] != "N/A" else "₹88,400",
            "petrol": rates["petrol"],
            "diesel": rates["diesel"]
        }

        eng_post = build_english_post(cats, rates_snapshot)
        logger.info("[BRIEFING] English general news briefing compiled (dispatch skipped per user preference).")

        # Translate to Marathi and dispatch
        mar_post = await translate_to_proficient_marathi(eng_post)
        await send_telegram_func(mar_post)
        logger.info("[BRIEFING] Marathi general news briefing dispatched.")
        
    except Exception as e:
        logger.error(f"[BRIEFING_ERROR] General news briefing dispatch failed: {e}", exc_info=True)

# ==========================================
# RUNNERS & SCHEDULERS (Backward Compatible)
# ==========================================
async def dispatch_briefing(send_telegram_func):
    post_text, fresh_headlines = await build_morning_news_post()
    if post_text and fresh_headlines:
        await send_telegram_func(post_text)
        mark_headlines_posted(fresh_headlines)

async def safe_dispatch_briefing(send_telegram_func):
    """Alias for compatibility with the scheduler pipeline."""
    await dispatch_briefing(send_telegram_func)

async def schedule_daily_dual_briefing_daemon(bot_dispatch_func):
    """Triggers at 08:00 AM and 08:00 PM IST daily for BOTH briefings (Sindhudurg and General News)."""
    while True:
        now = datetime.now(IST)
        if (now.hour == 8 or now.hour == 20) and now.minute == 0:
            logger.info(f"[BRIEFING] Generating {now.strftime('%I:%M %p')} IST News Briefings...")
            
            # 1. Dispatch Sindhudurg news briefing
            try:
                await safe_dispatch_briefing(bot_dispatch_func)
            except Exception as e:
                logger.error(f"[BRIEFING] Error executing safe_dispatch_briefing: {e}")
                
            # 2. Dispatch General news briefing 30 seconds later
            await asyncio.sleep(30)
            try:
                await dispatch_general_briefing(bot_dispatch_func)
            except Exception as e:
                logger.error(f"[BRIEFING] Error executing dispatch_general_briefing: {e}")
                
            await asyncio.sleep(60)
        await asyncio.sleep(30)
