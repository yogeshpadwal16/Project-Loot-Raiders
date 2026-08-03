import os
import sys

# Add project root to sys.path
sys.path.append("/var/www/loot-raiders")

from config.settings import load_settings
settings = load_settings()

bot_token = settings.get("telegram_bot_token")
chat_id = settings.get("telegram_chat_id")

has_telegram = bool(bot_token and chat_id and "YOUR_TELEGRAM" not in bot_token and bot_token.strip() != "")

print("=== SETTINGS TEST ===")
print("telegram_bot_token:", bot_token)
print("telegram_chat_id:", chat_id)
print("has_telegram:", has_telegram)
print("Environment TELEGRAM_BOT_TOKEN:", os.environ.get("TELEGRAM_BOT_TOKEN"))
print("Environment TELEGRAM_CHAT_ID:", os.environ.get("TELEGRAM_CHAT_ID"))
