# -*- coding: utf-8 -*-
import os
import sys

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyrogram import Client
from config.settings import load_settings

def run_login():
    settings = load_settings()
    api_id = settings.get("telegram_api_id")
    api_hash = settings.get("telegram_api_hash")

    if not api_id or not api_hash or "YOUR_TELEGRAM" in str(api_id):
        # Fallback to environment variables
        api_id = os.environ.get("TELEGRAM_API_ID")
        api_hash = os.environ.get("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured in settings.json or .env first.")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_path = os.path.join(base_dir, "pyrogram")

    print("==========================================================================")
    print("Project Loot Raiders - Pyrogram Interactive Login Tool")
    print("==========================================================================")
    print(f"Session path: {session_path}.session")
    print(f"API ID: {api_id}")
    print("Please follow the prompts to log in. You will receive an SMS/Telegram code.")
    print("==========================================================================\n")

    try:
        # We start the client interactively
        client = Client(
            name=session_path,
            api_id=int(api_id),
            api_hash=api_hash,
            workers=4
        )
        with client:
            me = client.get_me()
            print(f"\n✅ SUCCESS! Authenticated as: {me.first_name} (@{me.username or 'NoUsername'})")
            print("You can now start the deal mirroring engine normally.")
    except Exception as e:
        print(f"\n❌ Login failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_login()
