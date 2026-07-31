# -*- coding: utf-8 -*-
import os
import asyncio
from datetime import datetime, timezone, timedelta
import logging
from bs4 import BeautifulSoup
import feedparser
import httpx

logger = logging.getLogger("loot_raiders.esakal")

ESAKAL_RSS_URL = "https://www.esakal.com/feed/rss.xml"
ESAKAL_HOMEPAGE_URL = "https://www.esakal.com/"

# Define IST (Indian Standard Time) as UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))

# Context Emoji Mapping Rules
EMOJI_RULES = {
    (
        "परकष",
        "नट",
        "cet",
        "नकल",
        "वदयरथ",
        "शळ",
        "शकषण",
        "पपरफट",
    ): "👨🎓",
    (
        "पलस",
        "गनह",
        "अटक",
        "लठचरज",
        "दगडफक",
        "रड",
        "घटळ",
        "चर",
        "जखम",
        "कसळल",
        "मतय",
        "अपघत",
    ): "🥴",
    ("मदर", "जय", "मऊल", "पज", "उतसव", "वरकर", "सहळ"): "🙏",
    (
        "गहमतर",
        "मखयमतर",
        "मद",
        "पवर",
        "ससद",
        "वधनसभ",
        "नवडणक",
        "सरकर",
        "नत",
        "ममत",
        "भजप",
        "रजनम",
    ): "📰",
    (
        "पऊस",
        "पर",
        "धरण",
        "ओवहर फल",
        "पण",
        "नद",
        "जलसठ",
        "अतवषट",
        "तपमन",
        "वसरग",
    ): "🌊",
    ("करट", "नययलय", "दड", "यचक", "नयम", "उचच नययलय", "अलरट"): "📄",
    ("नकर", "भरत", "जवन", "वतन", "पगर", "हमगरड"): "👨",
    ("वहडओ", "वहयरल", "सशल मडय", "video"): "📹",
    ("रशय", "चन", "अमरक", "वमन", "यदध", "पररषटर"): "🇷🇺",
    (
        "कपन",
        "शअर",
        "बक",
        "आयत",
        "नरयत",
        "उदयग",
        "नफ",
        "रपय",
        "गतवणक",
        "दर",
        "दग",
    ): "💸",
}


def get_emoji(headline: str) -> str:
  text_lower = headline.lower()
  for keywords, emoji in EMOJI_RULES.items():
    if any(k in text_lower for k in keywords):
      return emoji
  return "📰"


async def fetch_esakal_headlines(limit: int = 15) -> list[str]:
  """Fetches clean Marathi headlines directly from esakal.com."""
  headlines = []
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  async with httpx.AsyncClient(
      timeout=10.0, headers=headers, follow_redirects=True
  ) as client:
    try:
      resp = await client.get(ESAKAL_RSS_URL)
      if resp.status_code == 200:
        feed = feedparser.parse(resp.text)
        for entry in feed.entries:
          title = entry.title.strip().split(" - ")[0].strip()
          if title and title not in headlines and len(title) > 15:
            headlines.append(title)
          if len(headlines) >= limit:
            break
    except Exception as e:
      logger.warning(f"[ESAKAL_RSS_WARN] {e}")

    if len(headlines) < limit:
      try:
        resp = await client.get(ESAKAL_HOMEPAGE_URL)
        if resp.status_code == 200:
          soup = BeautifulSoup(resp.text, "html.parser")
          for tag in soup.find_all(["h1", "h2", "h3"]):
            text = tag.text.strip().split(" - ")[0].strip()
            if text and len(text) > 20 and text not in headlines:
              if not any(
                  x in text for x in ["सबसकरईब", "सइन इन", "Epaper", "हम"]
              ):
                headlines.append(text)
            if len(headlines) >= limit:
              break
      except Exception as e:
        logger.error(f"[ESAKAL_SCRAPE_FAIL] {e}")

  return headlines[:limit]


RATES_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


async def fetch_live_rates() -> dict:
  """Dynamically fetches real-time Mumbai Gold (22K/24K per 10g), Silver (per 1kg),

  and Petrol/Diesel rates per Liter.
  """
  rates = {
      "gold_22k": "N/A",
      "gold_24k": "N/A",
      "silver_1kg": "N/A",
      "petrol": "\u20b9104.21",
      "diesel": "\u20b992.15",
  }

  async with httpx.AsyncClient(
      timeout=10.0, headers=RATES_HEADERS, follow_redirects=True
  ) as client:

    # 1. FETCH GOLD RATES (MUMBAI)
    #    GoodReturns uses a table where Row 3 has tds=['10', '₹1,44,600...', '₹1,32,550...', ...]
    #    Header Row 0 has ths=['Gram', '24K', '22K', '18K']
    #    So for the 10g row: cols[1] = 24K price, cols[2] = 22K price
    try:
      resp = await client.get(
          "https://www.goodreturns.in/gold-rates/mumbai.html"
      )
      if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")

        for tr in soup.find_all("tr"):
          tds = tr.find_all("td")
          if len(tds) >= 3:
            first_col = tds[0].text.strip()
            if first_col == "10":
              # Extract 24K (col 1) and 22K (col 2) rates for 10 grams
              raw_24k = tds[1].text.strip().split("\n")[0].replace("\u20b9", "").replace(",", "").strip()
              raw_22k = tds[2].text.strip().split("\n")[0].replace("\u20b9", "").replace(",", "").strip()
              if raw_24k.isdigit():
                rates["gold_24k"] = f"{int(raw_24k):,}"
              if raw_22k.isdigit():
                rates["gold_22k"] = f"{int(raw_22k):,}"
              break
    except Exception as e:
      logger.warning(f"[RATES] Failed fetching gold: {e}")

    # 2. FETCH SILVER RATE (MUMBAI)
    #    Silver table row has tds=['1000', '₹2,35,000', '₹2,35,000', '0']
    try:
      resp = await client.get(
          "https://www.goodreturns.in/silver-rates/mumbai.html"
      )
      if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        for tr in soup.find_all("tr"):
          tds = tr.find_all("td")
          if len(tds) >= 2:
            first_col = tds[0].text.strip()
            if first_col == "1000":
              val = tds[1].text.strip().replace("\u20b9", "").replace(",", "").strip()
              if val.isdigit():
                rates["silver_1kg"] = f"{int(val):,}"
              break
    except Exception as e:
      logger.warning(f"[RATES] Failed fetching silver: {e}")

    # 3. FETCH PETROL & DIESEL (MUMBAI)
    #    GoodReturns uses <span id="fp-price" class="fp-price-big">₹111.21</span>
    try:
      resp_p = await client.get(
          "https://www.goodreturns.in/petrol-price-in-mumbai.html"
      )
      if resp_p.status_code == 200:
        soup = BeautifulSoup(resp_p.text, "html.parser")
        p_tag = soup.find("span", {"id": "fp-price"})
        if p_tag:
          rates["petrol"] = p_tag.text.strip()

      resp_d = await client.get(
          "https://www.goodreturns.in/diesel-price-in-mumbai.html"
      )
      if resp_d.status_code == 200:
        soup = BeautifulSoup(resp_d.text, "html.parser")
        d_tag = soup.find("span", {"id": "fp-price"})
        if d_tag:
          rates["diesel"] = d_tag.text.strip()
    except Exception as e:
      logger.warning(f"[RATES] Failed fetching fuel rates: {e}")

  return rates


async def build_morning_news_post() -> str | None:
  headlines = await fetch_esakal_headlines(limit=15)
  if not headlines:
    return None

  # Fetch LIVE rates dynamically
  rates = await fetch_live_rates()

  # Clean Unicode Escape Header
  header = "📰 <b>\u0932\u0942\u091F \u0930\u0947\u0921\u0930\u094D\u0938 - \u0906\u091C\u091A\u094D\u092F\u093E \u091A\u093E\u0932\u0942 \u0918\u0921\u093E\u092E\u094B\u0921\u0940</b>\n     \n\n"

  news_blocks = [f"{get_emoji(h)} {h}" for h in headlines]
  news_section = "\n\n".join(news_blocks)

  # Footer inserting dynamic rates
  footer = (
      f"\n\n🪙 Gold Rate Today \u0906\u091C\u091A\u0947"
      f" \u0938\u094B\u0928\u094D\u092F\u093E\u091A\u0947 \u0926\u0930 - 22K ="
      f" {rates['gold_22k']}/- | | 24K = {rates['gold_24k']}/-\n🥈 Silver Rate"
      f" Today \u0906\u091C\u091A\u0947"
      f" \u091A\u093E\u0902\u0926\u0940\u091A\u0947 \u0926\u0930 - 1Kg ="
      f" {rates['silver_1kg']}/-\n Petrol & Diesel Rate \u0906\u091C\u091A\u0947"
      " \u0907\u0902\u0920\u0928 \u0926\u0930 - \u092A\u0947\u091F\u094D\u0930\u094B\u0932"
      f" = {rates['petrol']}/L | | \u0921\u093F\u091D\u0947\u0932 ="
      f" {rates['diesel']}/L\n📢 \u0924\u093E\u091C\u094D\u092F\u093E"
      " \u0918\u0921\u093E\u092E\u094B\u0921\u0940 \u0906\u0923\u093F"
      " \u092C\u0947\u0938\u094D\u091F"
      " \u0921\u0940\u0932\u094D\u0938\u0938\u093E\u0920\u0940"
      " \u091C\u0949\u0908\u0928 \u0915\u0930\u093E 👉 @LootRaidersDeals\n    "
      " "
  )

  return header + news_section + footer


# Dispatch wrapper
async def dispatch_briefing(send_telegram_func):
  post_text = await build_morning_news_post()
  if post_text:
    await send_telegram_func(post_text)


async def safe_dispatch_briefing(send_telegram_func):
  """Alias for compatibility with the scheduler pipeline."""
  await dispatch_briefing(send_telegram_func)


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
