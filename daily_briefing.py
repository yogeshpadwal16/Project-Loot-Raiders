# -*- coding: utf-8 -*-
import os
import asyncio
from datetime import datetime, timezone, timedelta
import logging
import feedparser
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("loot_raiders.esakal")

ESAKAL_RSS_URL = "https://www.esakal.com/feed/rss.xml"
ESAKAL_HOMEPAGE_URL = "https://www.esakal.com/"

# Explicit Devanagari Unicode mapping
EMOJI_RULES = {
    ("परकष", "नट", "cet", "नकल", "वदयरथ", "शळ", "शकषण", "पपरफट"): "👨🎓",
    ("पलस", "गनह", "अटक", "लठचरज", "दगडफक", "रड", "घटळ", "चर", "जखम", "कसळल", "मतय", "अपघत"): "🥴",
    ("मदर", "जय", "मऊल", "पज", "उतसव", "वरकर", "सहळ"): "🙏",
    ("गहमतर", "मखयमतर", "मद", "पवर", "ससद", "वधनसभ", "नवडणक", "सरकर", "नत", "ममत", "भजप", "रजनम"): "📰",
    ("पऊस", "पर", "धरण", "ओवहर फल", "पण", "नद", "जलसठ", "अतवषट", "तपमन", "वसरग"): "🌊",
    ("करट", "नययलय", "दड", "यचक", "नयम", "उचच नययलय", "अलरट"): "📄",
    ("नकर", "भरत", "जवन", "वतन", "पगर", "हमगरड"): "👨",
    ("वहडओ", "वहयरल", "सशल मडय", "video"): "📹",
    ("रशय", "चन", "अमरक", "वमन", "यदध", "पररषटर"): "🇷🇺",
    ("कपन", "शअर", "बक", "आयत", "नरयत", "उदयग", "नफ", "रपय", "गतवणक", "दर", "दग"): "💸",
}

# Define IST (Indian Standard Time) as UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))


def get_emoji(headline: str) -> str:
    text_lower = headline.lower()
    for keywords, emoji in EMOJI_RULES.items():
        if any(k in text_lower for k in keywords):
            return emoji
    return "📰"


async def fetch_esakal_headlines(limit: int = 15) -> list[str]:
    """Fetches clean Marathi headlines directly from esakal.com."""
    headlines = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
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
                            if not any(x in text for x in ["सबसकरईब", "सइन इन", "Epaper", "हम"]):
                                headlines.append(text)
                        if len(headlines) >= limit:
                            break
            except Exception as e:
                logger.error(f"[ESAKAL_SCRAPE_FAIL] {e}")

    return headlines[:limit]


async def build_morning_news_post() -> str | None:
    headlines = await fetch_esakal_headlines(limit=15)
    if not headlines:
        return None

    # Using Unicode escape representations or raw UTF-8 strings
    header = "📰 <b>लट रडरस - आजचय चल घडमड</b>\n     \n\n"
    
    news_blocks = []
    for h in headlines:
        emoji = get_emoji(h)
        news_blocks.append(f"{emoji} {h}")

    news_section = "\n\n".join(news_blocks)

    footer = (
        "\n\n🪙 Gold Rate Today आजच सनयच दर - 22K = 68,450/- | | 24K = 74,670/-\n"
        "🥈 Silver Rate Today आजच चदच दर - 1Kg = 88,400/-\n"
        " Petrol & Diesel Rate आजच इधन दर - पटरल = ₹104.21/L | | डझल = ₹92.15/L\n"
        "📢 तजय घडमड आण बसट डलससठ जईन कर 👉 @LootRaidersDeals\n"
        "     "
    )

    return header + news_section + footer


# Telegram dispatch wrapper
async def dispatch_briefing(send_telegram_func):
    post_text = await build_morning_news_post()
    if post_text:
        # DO NOT apply any str.encode() or regex sanitizers before sending!
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
