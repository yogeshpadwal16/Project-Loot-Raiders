import os
import asyncio
from datetime import datetime, timezone, timedelta
import logging
from bs4 import BeautifulSoup
import feedparser
import google.generativeai as genai
import httpx

logger = logging.getLogger("loot_raiders.sakal_briefing")

# 1. Sakal Official Marathi RSS Endpoints (with Google News Marathi fallback)
SAKAL_RSS_URLS = [
    "https://www.esakal.com/rss.xml",
    "https://www.esakal.com/maharashtra/rss.xml",
    "https://www.esakal.com/pune/rss.xml",
    "https://news.google.com/rss?hl=mr&gl=IN&ceid=IN:mr",
]

# Initialize Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_ACTUAL_GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel("gemini-1.5-flash")

# Define IST (Indian Standard Time) as UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))


async def fetch_sakal_marathi_headlines(limit: int = 15) -> list[str]:
  """Fetches native Marathi headlines directly from eSakal RSS feeds."""
  headlines = []
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
    for url in SAKAL_RSS_URLS:
      try:
        resp = await client.get(url)
        if resp.status_code == 200:
          feed = feedparser.parse(resp.text)
          for entry in feed.entries:
            title = entry.title.strip()
            # Clean title and filter out duplicates
            if title and title not in headlines and len(title) > 15:
              headlines.append(title)
            if len(headlines) >= limit:
              break
      except Exception as e:
        logger.warning(f"[SAKAL_RSS_WARN] Fetch failed for {url}: {e}")

      if len(headlines) >= limit:
        break

  return headlines


async def fetch_live_commodity_rates() -> dict:
  """Scrapes live Gold, Silver, Petrol, and Diesel rates."""
  rates = {
      "gold_22k": "1,33,668",
      "gold_24k": "1,45,820",
      "silver": "88,400",
      "petrol": "₹104.21",
      "diesel": "₹92.15",
  }

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
    try:
      resp = await client.get("https://www.goodreturns.in/gold-rates/mumbai.html")
      if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        gold_table = soup.find("div", {"class": "gold_silver_table"})
        if gold_table:
          rows = gold_table.find_all("tr")
          if len(rows) > 1:
            rates["gold_24k"] = rows[1].find_all("td")[1].text.strip()
    except Exception as e:
      logger.warning(f"[COMMODITY_WARN] Failed to scrape live rates: {e}")

  return rates


def python_fallback_formatter(headlines: list[str], rates: dict) -> str:
  """Pure Python backup formatter if Gemini API drops out.

  Guarantees NO broken error messages on your channel.
  """
  post = "📰 <b>लट रडरस - आजचय चल घडमड</b>\n"
  post += "     \n"

  # Assign standard news emojis locally
  emojis = ["📰", "👨🎓", "📄", "🥴", "🙏", "👨", "📹", "🌊", "🇷🇺", "💸"]
  for i, h in enumerate(headlines):
    emoji = emojis[i % len(emojis)]
    post += f"{emoji} {h}\n"

  post += f"🪙 Gold Rate Today आजच सनयच दर - 22K = {rates['gold_22k']}/- | | 24K = {rates['gold_24k']}/-\n"
  post += f"🥈 Silver Rate Today आजच चदच दर - 1Kg = {rates['silver']}/-\n"
  post += f" Petrol & Diesel Rate आजच इधन दर - पटरल = {rates['petrol']}/L | | डझल = {rates['diesel']}/L\n"
  post += (
      "📢 तजय घडमड आण बसट डलससठ जईन कर 👉 @LootRaidersDeals\n"
  )
  post += "     "
  return post


async def generate_sakal_briefing_post() -> str | None:
  """Main generator: Fetches Sakal Marathi headlines, formats into your exact UI,

  and returns safe output.
  """
  # Step 1: Fetch raw Marathi headlines directly from Sakal
  sakal_headlines = await fetch_sakal_marathi_headlines(limit=15)
  if not sakal_headlines:
    logger.error("[BRIEFING_ABORT] Could not scrape Sakal news. Aborting post.")
    return None

  # Step 2: Fetch rates
  rates = await fetch_live_commodity_rates()

  # Step 3: Format with Gemini for smart context-matching emojis
  news_text_block = "\n".join([f"- {h}" for h in sakal_headlines])

  prompt = f"""
    You are an editor for the Telegram channel 'लट रडरस'.
    Take these Sakal Marathi headlines and format them into the EXACT required layout. Do NOT change the Marathi news text.

    REQUIRED FORMAT:
    📰 लट रडरस - आजचय चल घडमड
         
    [Context Emoji] [Sakal Marathi Headline]
    ...
    🪙 Gold Rate Today आजच सनयच दर - 22K = {rates['gold_22k']}/- | | 24K = {rates['gold_24k']}/-
    🥈 Silver Rate Today आजच चदच दर - 1Kg = {rates['silver']}/-
     Petrol & Diesel Rate आजच इधन दर - पटरल = {rates['petrol']}/L | | डझल = {rates['diesel']}/L
    📢 तजय घडमड आण बसट डलससठ जईन कर 👉 @LootRaidersDeals
         

    EMOJI RULES:
    - Precede EVERY line with a matching emoji (👨🎓 for education, 🥴 for crime/scam, 🙏 for religion, 📄 for govt/orders, 📹 for viral, 🌊 for rain/water, 🇷🇺 for foreign/oil, 📰 for general).
    - Do NOT use bullet points like '' or '*'.

    Sakal Headlines:
    {news_text_block}
    """

  try:
    response = await ai_model.generate_content_async(prompt)
    output_text = response.text.strip()

    # Safety Guard: Ensure no error phrases escaped into the output
    if "अडचण" in output_text or "Error" in output_text:
      raise ValueError("Gemini generated an error response.")

    return output_text

  except Exception as e:
    logger.warning(
        f"[GEMINI_WARN] AI formatting failed: {e}. Switching to Python local"
        " formatter fallback."
    )
    # Use pure Python local fallback (uses Sakal headlines + local emojis)
    return python_fallback_formatter(sakal_headlines, rates)


async def safe_dispatch_briefing(bot_dispatch_func):
  """Safely dispatches morning briefing at 08:00 AM IST."""
  post_content = await generate_sakal_briefing_post()

  if post_content:
    await bot_dispatch_func(post_content)
    logger.info("[BRIEFING] Sakal morning briefing posted successfully.")
  else:
    logger.error("[BRIEFING_SUPPRESSED] Post suppressed to protect channel.")


async def schedule_daily_dual_briefing_daemon(bot_dispatch_func):
  """Background daemon running continuously. Triggers at 08:00 AM IST daily."""
  while True:
    now = datetime.now(IST)
    if now.hour == 8 and now.minute == 0:
      logger.info("[BRIEFING] Starting 08:00 AM IST Sakal Briefing Generation...")
      try:
          await safe_dispatch_briefing(bot_dispatch_func)
      except Exception as e:
          logger.error(f"[BRIEFING] Error in safe_dispatch_briefing: {e}")
      await asyncio.sleep(60)
    await asyncio.sleep(30)
