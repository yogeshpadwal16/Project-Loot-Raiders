import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession

# Load credentials
api_id_str = os.environ.get("TELEGRAM_API_ID", "39413198").strip()
api_hash = os.environ.get("TELEGRAM_API_HASH", "d648fd457db96dffa53ae18d3d1869d8").strip()

try:
    api_id = int(api_id_str)
except:
    print("Error: Invalid TELEGRAM_API_ID. Set it in env or edit the script.")
    sys.exit(1)

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
session_path = os.path.join(base_dir, "channel_mirror.session")

if not os.path.exists(session_path):
    print(f"Error: Local session file not found at {session_path}.")
    print("Please run 'python loot_scraper.py' locally first and complete the login.")
    sys.exit(1)

print("Reading your authenticated local session and converting to string...")
client = TelegramClient(session_path, api_id, api_hash)

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("Error: Your local session is not authorized. Please re-login locally.")
        return
    
    # Extract string session details from the active SQLite session
    string_session = StringSession()
    string_session.set_dc(
        client.session.dc_id,
        client.session.server_address,
        client.session.port
    )
    string_session.auth_key = client.session.auth_key
    session_str = string_session.save()
    
    print("\n" + "="*80)
    print("SUCCESS! COPY YOUR TELEGRAM STRING SESSION BELOW:")
    print("="*80)
    print(session_str)
    print("="*80)
    print("\nInstructions:")
    print("1. Go to your GitHub repository -> Settings -> Secrets and variables -> Actions.")
    print("2. Create a new repository secret named: TELEGRAM_STRING_SESSION")
    print("3. Paste the long session string above as the value.")
    print("4. This allows the cloud scraper to monitor competitor channels securely without files!")
    print("="*80)

client.loop.run_until_complete(main())
