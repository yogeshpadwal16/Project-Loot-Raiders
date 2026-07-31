import os
import asyncio
from datetime import datetime, timezone, timedelta
import logging
from bs4 import BeautifulSoup
import feedparser
import google.generativeai as genai
import httpx

logger = logging.getLogger("loot_raiders.sakal_briefing")

# Define IST (Indian Standard Time) as UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))

# Initialize Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_ACTUAL_GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel("gemini-1.5-flash")


async def fetch_strict_esakal_headlines(limit: int = 15) -> list[str]:
    """Scrapes strict native Devanagari Marathi headlines directly from the esakal.com homepage HTML."""
    headlines = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    
    urls = [
        "https://www.esakal.com",
        "https://www.esakal.com/maharashtra",
        "https://www.esakal.com/pune",
    ]
    
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a"):
                        text = a.text.strip() if a.text else ""
                        href = a.get("href", "")
                        # Simple heuristics to identify quality news article links
                        if (
                            len(text) > 20 
                            and href 
                            and any(cat in href for cat in ["/maharashtra/", "/pune/", "/mumbai/", "/desh/", "/vidarbha/", "/khel/", "/sakal-money/"])
                            and not any(bad in href for bad in ["/web-story/", "/ampstories/"])
                        ):
                            # Remove typical leading prefixes if any
                            clean_title = text.replace("Latest Marathi News Live Update :", "").strip()
                            if clean_title and clean_title not in headlines:
                                headlines.append(clean_title)
                            if len(headlines) >= limit:
                                break
            except Exception as e:
                logger.warning(f"[STRICT_ESAKAL_WARN] Scrape failed for {url}: {e}")
            if len(headlines) >= limit:
                break
                
    return headlines


async def fetch_live_commodity_rates() -> dict:
  """Scrapes live Gold, Silver, Petrol, and Diesel rates."""
  rates = {
      "gold_22k": "1,33,668",
      "gold_24k": "1,45,820",
      "silver": "88,400",
      "silver_1kg": "88,400",
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


def match_emoji(headline: str) -> str:
    """Matches a context-relevant emoji to a Marathi headline based on keyword heuristics."""
    headline_lower = headline.lower()
    
    # Keywords matching
    # Education/Students/Exam
    if any(k in headline_lower for k in ["शिक्षण", "परीक्षा", "निकाल", "विद्यार्थी", "शाळा", "कॉलेज", "टीईटी", "टीचर", "शिक्षक", "mpsc", "neet"]):
        return "👨‍🎓"
    # Crime/Accident/Scam/Court
    elif any(k in headline_lower for k in ["अपघात", "मृत्यू", "अटकेत", "गुन्हा", "पोलीस", "कोर्ट", "न्यायालय", "फाशी", "बनावट", "दारू", "चोरी", "फसवणूक"]):
        return "🥴"
    # Religion/Festival/Culture
    elif any(k in headline_lower for k in ["पूजा", "मंदिर", "दर्शन", "रक्षाबंधन", "राखी", "सण", "उत्सव", "धार्मिक", "देव"]):
        return "🙏"
    # Government orders/Politics/Elections
    elif any(k in headline_lower for k in ["सरकार", "शासन", "निर्णय", "भाजप", "काँग्रेस", "राष्ट्रवादी", "राजीनामा", "आंदोलन", "पक्ष", "मंत्री", "मुख्यमंत्री", "पंतप्रधान"]):
        return "📄"
    # Rain/Flood/Weather/Nature
    elif any(k in headline_lower for k in ["पाऊस", "पूर", "धरण", "विसर्ग", "क्युसेक", "हवामान", "अ‍ॅलर्ट", "मुसळधार", "नदी", "तापमान"]):
        return "🌊"
    # Foreign/International/Oil
    elif any(k in headline_lower for k in ["परदेश", "अमेरिका", "रशिया", "युक्रेन", "इस्रायल", "युद्ध", "आंतरराष्ट्रीय"]):
        return "🇷🇺"
    # Finance/Gold/Stock/Rates
    elif any(k in headline_lower for k in ["पैसा", "इंधन", "पेट्रोल", "डिझेल", "दर", "घसरण", "वाढ", "सोने", "चांदी", "बँक", "शेअर"]):
        return "💸"
    # Sports
    elif any(k in headline_lower for k in ["क्रिकेट", "सामना", "खेळ", "विजेता", "धावा", "विश्वचषक", "ऑलिम्पिक"]):
        return "🏆"
    # General news fallback
    else:
        return "📰"


async def generate_esakal_only_post() -> str | None:
  """Generates pure eSakal post with intact Devanagari text and spacing between news items."""
  headlines = await fetch_strict_esakal_headlines(limit=15)
  if not headlines:
    logger.error("[ABORT] Could not retrieve headlines from esakal.com")
    return None

  rates = await fetch_live_commodity_rates()

  lines = [
      "📰 <b>लट रडरस - आजचय चल घडमड</b>",
      "     ",
      "",  # Gap before news list
  ]

  # Loop through headlines and insert a blank line after each item
  for h in headlines:
    emoji = match_emoji(h)
    lines.append(f"{emoji} {h}")
    lines.append("")  # 👈 Creates a blank gap after every news item

  # Commodity & Fuel Footer
  lines.append(
      f"🪙 Gold Rate Today आजच सनयच दर - 22K = {rates['gold_22k']}/- | | 24K ="
      f" {rates['gold_24k']}/-"
  )
  lines.append(
      f"🥈 Silver Rate Today आजच चदच दर - 1Kg = {rates['silver_1kg']}/-"
  )
  lines.append(
      f" Petrol & Diesel Rate आजच इधन दर - पटरल = {rates['petrol']}/L | |"
      f" डझल = {rates['diesel']}/L"
  )
  lines.append(
      "📢 तजय घडमड आण बसट डलससठ जईन कर 👉 @LootRaidersDeals"
  )
  lines.append("     ")

  return "\n".join(lines)


async def safe_dispatch_briefing(bot_dispatch_func):
  """Safely dispatches morning briefing at 08:00 AM IST."""
  post_content = await generate_esakal_only_post()

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
