import asyncio
import logging
from daily_briefing import schedule_daily_dual_briefing_daemon

# Set up logging to monitor task health
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

async def dispatch_to_channel(text_content: str):
    """Helper to post raw text captions to Telegram channel."""
    try:
        from config.settings import load_settings
        import httpx

        settings = load_settings()
        bot_token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")

        if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "" or not chat_id:
            logging.error("[BRIEFING] Telegram bot credentials or chat_id not configured in settings.json.")
            return

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text_content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                logging.info("[BRIEFING] Daily Morning Briefing posted successfully to Telegram!")
            else:
                logging.error(f"[BRIEFING] Telegram API failed: {res.status_code} - {res.text}")
    except Exception as e:
        logging.error(f"[BRIEFING] Error dispatching briefing to channel: {e}", exc_info=True)

async def main():
    import sys
    if "--now" in sys.argv or "--test" in sys.argv:
        logging.info("[BRIEFING] Test mode activated: generating and posting Sakal briefing immediately...")
        from daily_briefing import safe_dispatch_briefing
        try:
            await safe_dispatch_briefing(dispatch_to_channel)
            logging.info("[BRIEFING] Sakal briefing dispatched in test/now mode.")
        except Exception as e:
            logging.error(f"[BRIEFING] Error in test/now mode: {e}", exc_info=True)
    else:
        # Since the daemon runs an infinite loop, direct await keeps the event loop running
        # and completely avoids background task garbage-collection risks.
        await schedule_daily_dual_briefing_daemon(dispatch_to_channel)

if __name__ == "__main__":
    asyncio.run(main())
