import os
import re
import html
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import feedparser
import httpx
import google.generativeai as genai

logger = logging.getLogger("loot_raiders.daily_briefing")

# Constants
NEWS_RSS_URL = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
SAKAL_RSS_URL = "https://www.esakal.com/rss/maharashtra" # Sakal news backup

# Define IST (Indian Standard Time)
IST = timezone(timedelta(hours=5, minutes=30))

# Pre-compiled Regex patterns for news category matching
BUSINESS_RE = re.compile(r"\b(market|sensex|nifty|profit|tech|bank|shares|ceo|uber|rapido|petrol|tax|startup|funding)\b", re.IGNORECASE)
SPORTS_RE = re.compile(r"\b(cricket|match|trophy|messi|olympic|bcci|won|final|medal|ipl|world cup|football|tennis)\b", re.IGNORECASE)
WORLD_RE = re.compile(r"\b(us|china|iran|pakistan|world|ukraine|russia|un|biden|trump|brics|israel|gaza)\b", re.IGNORECASE)

async def fetch_20_categorized_headlines() -> dict:
    """Fetches and categorizes 20 headlines from Google News RSS and Sakal RSS."""
    categories = {
        "national": [],
        "business": [],
        "world": [],
        "sports": []
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # Try Google News
        try:
            resp = await client.get(NEWS_RSS_URL)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.text)
                for entry in feed.entries:
                    title = entry.title.split(" - ")[0].strip()
                    clean_title = html.escape(title)
                    
                    is_categorized = False
                    if BUSINESS_RE.search(clean_title) and len(categories["business"]) < 5:
                        categories["business"].append(clean_title)
                        is_categorized = True
                    elif SPORTS_RE.search(clean_title) and len(categories["sports"]) < 5:
                        categories["sports"].append(clean_title)
                        is_categorized = True
                    elif WORLD_RE.search(clean_title) and len(categories["world"]) < 5:
                        categories["world"].append(clean_title)
                        is_categorized = True
                        
                    if not is_categorized and len(categories["national"]) < 6:
                        categories["national"].append(clean_title)
                        
                    if sum(len(v) for v in categories.values()) >= 20:
                        break
        except Exception as e:
            logger.error(f"Error fetching Google News RSS: {e}")

        # Fallback / augment with Sakal RSS if needed
        if sum(len(v) for v in categories.values()) < 5:
            try:
                resp = await client.get(SAKAL_RSS_URL)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    for entry in feed.entries:
                        title = entry.title.strip()
                        clean_title = html.escape(title)
                        if clean_title not in categories["national"]:
                            categories["national"].append(clean_title)
                        if len(categories["national"]) >= 10:
                            break
            except Exception as e:
                logger.error(f"Error fetching Sakal RSS: {e}")
                
    # Fill defaults if completely empty
    if not any(categories.values()):
        categories["national"] = ["No active headlines found. Keeping watch for fresh updates."]
        
    return categories

async def fetch_commodity_rates() -> dict:
    """Scrapes Gold (24K), Silver (1kg), and Brent Crude Oil prices."""
    rates = {"gold_24k": "₹74,250 (10g)", "silver_1kg": "₹88,400", "crude": "$78.40"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # Scrape Gold
        try:
            resp = await client.get("https://www.goodreturns.in/gold-rates/mumbai.html")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                table = soup.find("table", class_="gr-table")
                if table:
                    for row in table.find_all("tr"):
                        cells = row.find_all(["td", "th"])
                        if cells and cells[0].text.strip() == "10":
                            if len(cells) > 1:
                                price = cells[1].text.strip().split("\n")[0].strip()
                                rates["gold_24k"] = f"{price} (10g)"
                            break
        except Exception as e:
            logger.warning(f"Gold scrape error: {e}")

        # Scrape Silver
        try:
            resp = await client.get("https://www.goodreturns.in/silver-rates/mumbai.html")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                table = soup.find("table", class_="gr-table")
                if table:
                    for row in table.find_all("tr"):
                        cells = row.find_all(["td", "th"])
                        if cells and cells[0].text.strip() == "1000":
                            if len(cells) > 1:
                                price = cells[1].text.strip().split("\n")[0].strip()
                                rates["silver_1kg"] = price
                            break
        except Exception as e:
            logger.warning(f"Silver scrape error: {e}")

        # Crude Oil
        try:
            resp = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/BZ=F")
            if resp.status_code == 200:
                data = resp.json()
                price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
                rates["crude"] = f"${price:.2f}"
        except Exception as e:
            logger.warning(f"Crude scrape error: {e}")

    return rates

def build_english_post(cats: dict, rates: dict) -> str:
    """Builds English Telegram HTML post."""
    today_str = datetime.now(IST).strftime("%A, %d %B %Y")

    caption = "📢 <b>LOOT RAIDERS DAILY MORNING BRIEFING</b>\n"
    caption += f"📅 <i>{today_str}</i>\n\n"

    caption += "<blockquote>"
    caption += "📈 <b>Commodity & Market Snapshot</b>\n"
    caption += f"🪙 <b>Gold (24K):</b> {rates['gold_24k']}\n"
    caption += f"🥈 <b>Silver (1kg):</b> {rates['silver_1kg']}\n"
    caption += f"🛢️ <b>Crude Oil:</b> {rates['crude']}/bbl\n"
    caption += "</blockquote>\n\n"

    if cats.get("national"):
        caption += "<blockquote>"
        caption += "🇮🇳 <b>National & Policy News</b>\n"
        for h in cats["national"]:
            caption += f"• {h}\n"
        caption += "</blockquote>\n\n"

    if cats.get("business"):
        caption += "<blockquote>"
        caption += "💼 <b>Business, Tech & Economy</b>\n"
        for h in cats["business"]:
            caption += f"• {h}\n"
        caption += "</blockquote>\n\n"

    if cats.get("world"):
        caption += "<blockquote>"
        caption += "🌐 <b>Global News</b>\n"
        for h in cats["world"]:
            caption += f"• {h}\n"
        caption += "</blockquote>\n\n"

    if cats.get("sports"):
        caption += "<blockquote>"
        caption += "🏆 <b>Sports Updates</b>\n"
        for h in cats["sports"]:
            caption += f"• {h}\n"
        caption += "</blockquote>\n\n"

    caption += "✨ <i>Stay tuned for top loot deals & price drops coming up today!</i>\n"
    caption += "👉 Join <b>@LootRaidersDeals</b>"
    return caption

async def translate_to_marathi(english_post: str, gemini_api_key: str) -> str:
    """Translates the English news briefing into high-proficiency journalistic Marathi using Gemini."""
    if not gemini_api_key or "YOUR_" in gemini_api_key or gemini_api_key.strip() == "":
        logger.warning("Gemini API key is not configured. Marathi briefing will use default fallback.")
        return english_post.replace("LOOT RAIDERS DAILY MORNING BRIEFING", "लूट रेडर्स : दैनिक प्रभात वृत्त (मराठी)")

    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
        You are a Senior Editor for a premier Marathi daily newspaper. 
        Translate the following English news briefing into highly proficient, natural, standard Marathi (शुद्ध प्रमाण मराठी).

        LANGUAGE & JOURNALISTIC RULES:
        1. Avoid literal word-for-word translation. Use authentic Marathi news terms:
           - "Paper leak" -> "पेपरफुटी प्रकरण"
           - "Death toll" -> "मृत्यूचा आकडा"
           - "Trial run" -> "यशस्वी चाचणी"
           - "Subsidies" -> "अनुदान"
           - "Retirement" -> "निवृत्ती"
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
        4. PRESERVE NUMBERS, CURRENCIES & EMOJIS: Keep values, numbers, and emojis intact.

        English Text:
        {english_post}
        """
        
        response = await asyncio.to_thread(model.generate_content, prompt)
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
        logger.error(f"Gemini API Marathi translation failed: {e}")
        return english_post.replace("LOOT RAIDERS DAILY MORNING BRIEFING", "लूट रेडर्स : दैनिक प्रभात वृत्त")
