import asyncio
from datetime import datetime, timezone, timedelta
import html
import logging
import os
import re
from bs4 import BeautifulSoup
import feedparser
import google.generativeai as genai
import httpx

logger = logging.getLogger("loot_raiders.briefing")

# Google News India RSS Endpoint (Free, no rate limits/Cloudflare blocks)
NEWS_RSS_URL = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"

# Initialize Gemini API for high-precision Marathi journalistic translation
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel("gemini-1.5-flash")

# Define IST (Indian Standard Time) as UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))

# Pre-compiled Regex patterns for taxonomy matching to avoid partial word collisions (e.g. "us" matching in "business")
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


async def fetch_20_categorized_headlines() -> dict:
  """Fetches 20 headlines from Google News RSS and categorizes them into 4 structured sections."""
  async with httpx.AsyncClient(timeout=8.0) as client:
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


async def fetch_commodity_rates() -> dict:
  """Scrapes Gold (24K), Silver (1kg), and Brent Crude Oil prices."""
  rates = {"gold_24k": "₹74,250 (10g)", "silver_1kg": "₹88,400", "crude": "$78.40"}
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
    # 1. Scrape Gold from GoodReturns (updated table structure as of 2026)
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
      logger.warning(f"[COMMODITY_FETCH_FAIL] Gold scrape error: {e}")

    # 2. Scrape Silver from GoodReturns (updated table structure as of 2026)
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
      logger.warning(f"[COMMODITY_FETCH_FAIL] Silver scrape error: {e}")

    # 3. Fetch Crude Oil from Yahoo Finance API
    try:
      resp = await client.get(
          "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F"
      )
      if resp.status_code == 200:
        data = resp.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        rates["crude"] = f"${price:.2f}"
    except Exception as e:
      logger.warning(f"[COMMODITY_FETCH_FAIL] Crude scrape error: {e}")

  return rates


def build_english_post(cats: dict, rates: dict) -> str:
  """Builds primary English Telegram HTML post."""
  today_str = datetime.now(IST).strftime("%A, %d %B %Y")

  caption = " <b>LOOT RAIDERS DAILY MORNING BRIEFING</b>\n"
  caption += f" <i>{today_str}</i>\n\n"

  caption += "<blockquote>"
  caption += " <b>Commodity & Market Snapshot</b>\n"
  caption += f" <b>Gold (24K):</b> {rates['gold_24k']}\n"
  caption += f" <b>Silver (1kg):</b> {rates['silver_1kg']}\n"
  caption += f" <b>Crude Oil:</b> {rates['crude']}/bbl\n"
  caption += "</blockquote>\n\n"

  if cats["national"]:
    caption += "<blockquote>"
    caption += " <b>National & Policy News</b>\n"
    for h in cats["national"]:
      caption += f" {h}\n"
    caption += "</blockquote>\n\n"

  if cats["business"]:
    caption += "<blockquote>"
    caption += " <b>Business, Tech & Economy</b>\n"
    for h in cats["business"]:
      caption += f" {h}\n"
    caption += "</blockquote>\n\n"

  if cats["world"]:
    caption += "<blockquote>"
    caption += " <b>Global News</b>\n"
    for h in cats["world"]:
      caption += f" {h}\n"
    caption += "</blockquote>\n\n"

  if cats["sports"]:
    caption += "<blockquote>"
    caption += " <b>Sports Updates</b>\n"
    for h in cats["sports"]:
      caption += f" {h}\n"
    caption += "</blockquote>\n\n"

  caption += " <i>Stay tuned for top loot deals & price drops coming up today!</i>\n"
  caption += " Join <b>@LootRaidersDeals</b>"

  return caption


async def translate_to_proficient_marathi(english_post: str) -> str:
  """Translates English post into high-proficiency journalistic Marathi (शुद्ध प्रमाण मराठी)."""
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

  try:
    response = await ai_model.generate_content_async(prompt)
    translated_text = response.text.strip()
    
    # Strip markdown code blocks if the model wrapped the response in one
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
    return " <b>लूट रेडर्स : दैनिक प्रभात वृत्त</b>\n\nअनुवाद तयार करताना तांत्रिक अडचण आली."


async def schedule_daily_dual_briefing_daemon(bot_dispatch_func):
  """Background daemon running continuously. Triggers at 08:00 AM IST daily."""
  while True:
    now = datetime.now(IST)
    if now.hour == 8 and now.minute == 0:
      logger.info(
          "[BRIEFING] Starting 08:00 AM IST Dual Briefing Generation..."
      )

      # Fetch news & commodities
      cats = await fetch_20_categorized_headlines()
      rates = await fetch_commodity_rates()

      # Generate English Post
      eng_post = build_english_post(cats, rates)
      await bot_dispatch_func(eng_post)
      logger.info("[BRIEFING] English post dispatched.")

      # Generate & Send Marathi Post 10 Seconds Later
      await asyncio.sleep(10)
      mar_post = await translate_to_proficient_marathi(eng_post)
      await bot_dispatch_func(mar_post)
      logger.info("[BRIEFING] Marathi post dispatched.")

      # Sleep 60 seconds to avoid double trigger during the same minute
      await asyncio.sleep(60)

    # Poll every 30 seconds
    await asyncio.sleep(30)
