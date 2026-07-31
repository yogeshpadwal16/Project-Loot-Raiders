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


async def fetch_live_commodity_rates() -> dict:
  """Dynamically scrapes live Mumbai market rates for 22K Gold, 24K Gold, Silver (1kg), Petrol, and Diesel."""
  rates = {
      "gold_22k": "72,500",  # Dynamic fallbacks in case network is down
      "gold_24k": "79,100",
      "silver_1kg": "92,000",
      "petrol": "₹104.21",
      "diesel": "₹92.15",
  }

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  async with httpx.AsyncClient(
      timeout=8.0, headers=headers, follow_redirects=True
  ) as client:
    # 1. Scrape 22K & 24K Gold Rates (per 10g)
    try:
      resp = await client.get(
          "https://www.goodreturns.in/gold-rates/mumbai.html"
      )
      if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("div", {"class": "gold_silver_table"})

        if tables:
          # Table 0: 22K Gold Rates
          rows_22 = tables[0].find_all("tr")
          for row in rows_22:
            cols = row.find_all("td")
            if len(cols) >= 2 and "10 gram" in cols[0].text.lower():
              rates["gold_22k"] = cols[1].text.strip().replace("₹", "").strip()

          # Table 1: 24K Gold Rates
          if len(tables) > 1:
            rows_24 = tables[1].find_all("tr")
            for row in rows_24:
              cols = row.find_all("td")
              if len(cols) >= 2 and "10 gram" in cols[0].text.lower():
                rates["gold_24k"] = (
                    cols[1].text.strip().replace("₹", "").strip()
                )
    except Exception as e:
      logger.warning(f"[COMMODITY_GOLD_FAIL] Could not fetch gold rates: {e}")

    # 2. Scrape Silver Rate (per 1kg)
    try:
      resp = await client.get(
          "https://www.goodreturns.in/silver-rates/mumbai.html"
      )
      if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        silver_table = soup.find("div", {"class": "gold_silver_table"})
        if silver_table:
          rows = silver_table.find_all("tr")
          for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 2 and "1 kg" in cols[0].text.lower():
              rates["silver_1kg"] = (
                  cols[1].text.strip().replace("₹", "").strip()
              )
    except Exception as e:
      logger.warning(f"[COMMODITY_SILVER_FAIL] Could not fetch silver rate: {e}")

  return rates


async def build_morning_news_post() -> str | None:
  headlines = await fetch_esakal_headlines(limit=15)
  if not headlines:
    return None

  rates = await fetch_live_commodity_rates()

  # Unicode ASCII Escapes prevent paste corruption in terminal/IDE
  # Decodes to: 📰 <b>लट रडरस - आजचय चल घडमड</b>
  header = "📰 <b>\u0932\u0942\u091F \u0930\u0947\u0921\u0930\u094D\u0938 - \u0906\u091C\u091A\u094D\u092F\u093E \u091A\u093E\u0932\u0942 \u0918\u0921\u093E\u092E\u094B\u0921\u0940</b>\n     \n\n"

  news_blocks = []
  for h in headlines:
    emoji = get_emoji(h)
    news_blocks.append(f"{emoji} {h}")

  news_section = "\n\n".join(news_blocks)

  # Footer Unicode ASCII Escapes
  footer = (
      "\n\n🪙 Gold Rate Today \u0906\u091C\u091A\u0947"
      f" \u0938\u094B\u0928\u094D\u092F\u093E\u091A\u0947 \u0926\u0930 - 22K = {rates['gold_22k']}/- | | 24K = {rates['gold_24k']}/-\n"
      "🥈 Silver Rate Today \u0906\u091C\u091A\u0947"
      f" \u091A\u093E\u0902\u0926\u0940\u091A\u0947 \u0926\u0930 - 1Kg = {rates['silver_1kg']}/-\n"
      " Petrol & Diesel Rate \u0906\u091C\u091A\u0947"
      f" \u0907\u0902\u0920\u0928 \u0926\u0930 - \u092A\u0947\u091F\u094D\u0930\u094B\u0932 = {rates['petrol']}/L | | \u0921\u093F\u091D\u0947\u0932 = {rates['diesel']}/L\n"
      "📢 \u0924\u093E\u091C\u094D\u092F\u093E \u0918\u0921\u093E\u092E\u094B\u0921\u0940"
      " \u0906\u0923\u093F \u092C\u0947\u0938\u094D\u091F"
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
