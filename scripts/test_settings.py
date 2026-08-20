# scripts/test_settings.py
"""
Safe settings diagnostics script.
Verifies that the settings loading chain works correctly
WITHOUT printing any real credential values.
"""
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.settings import load_settings
settings = load_settings()

bot_token = settings.get("telegram_bot_token", "")
chat_id = settings.get("telegram_chat_id", "")
omniroute_key = settings.get("omniroute_api_key", "")

has_telegram = bool(bot_token and chat_id and "YOUR_TELEGRAM" not in bot_token and bot_token.strip() != "")
has_omniroute = bool(omniroute_key and "YOUR_" not in omniroute_key and omniroute_key.strip() != "")

# SECURITY: Never print real credential values.
# Only report whether credentials are loaded (present/absent).
def _mask(value: str) -> str:
    if not value or "YOUR_" in value:
        return "(placeholder)"
    if len(value) > 8:
        return "****" + value[-4:]
    return "****"

print("=== SETTINGS DIAGNOSTIC (SAFE) ===")
print(f"telegram_bot_token: {_mask(bot_token)}")
print(f"telegram_chat_id: {chat_id}")
print(f"has_telegram: {has_telegram}")
print(f"omniroute_api_key: {_mask(omniroute_key)}")
print(f"has_omniroute: {has_omniroute}")
print(f"env TELEGRAM_BOT_TOKEN set: {bool(os.environ.get('TELEGRAM_BOT_TOKEN'))}")
print(f"env OMNIROUTE_API_KEY set: {bool(os.environ.get('OMNIROUTE_API_KEY'))}")
