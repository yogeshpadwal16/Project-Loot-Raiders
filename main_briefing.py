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
    # Your Telegram bot client send_message call
    # e.g., await bot.send_message(chat_id=CHANNEL_ID, text=text_content, parse_mode="HTML")
    pass

async def main():
    # Since the daemon runs an infinite loop, direct await keeps the event loop running
    # and completely avoids background task garbage-collection risks.
    await schedule_daily_dual_briefing_daemon(dispatch_to_channel)

if __name__ == "__main__":
    asyncio.run(main())
