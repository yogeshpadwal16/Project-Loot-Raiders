import os
import re
import logging
import threading
import asyncio
from telethon import TelegramClient, events
from deal_engine.deal_processor import process_deal_url
from config.settings import load_settings

def start_channel_mirror():
    """Spawns the Telegram Client mirror listener in a separate daemon thread."""
    thread = threading.Thread(target=run_mirror_loop, daemon=True)
    thread.start()
    logging.info("[Channel Mirror] Background scraping daemon thread started.")

def run_mirror_loop():
    """Initializes a dedicated asyncio event loop for Telethon client."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(mirror_main())

async def mirror_main():
    # Load API credentials from environment
    api_id_str = os.environ.get("TELEGRAM_API_ID", "39413198").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "d648fd457db96dffa53ae18d3d1869d8").strip()
    
    try:
        api_id = int(api_id_str)
    except ValueError:
        logging.error(f"[Channel Mirror] Invalid API ID in configuration: {api_id_str}. Listener halted.")
        return

    # Path to store session file in base directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_path = os.path.join(base_dir, "channel_mirror.session")
    
    logging.info("[Channel Mirror] Preparing Telethon Client setup...")
    # Authentication warning on startup
    logging.info("==========================================================================")
    logging.info("🌟 [Channel Mirror] REAL-TIME TELEGRAM MONITOR INITIATING 🌟")
    logging.info("👉 Note: If this is your first run, check your terminal/console! ")
    logging.info("   You will be prompted to enter your phone number and login code.")
    logging.info("==========================================================================")
    
    client = TelegramClient(session_path, api_id, api_hash)
    
    try:
        # Start and authenticate client first
        await client.start()
        logging.info("[Channel Mirror] Telegram Client authenticated successfully.")
        
        # Now resolve and join target channels
        target_channels = ['Loot_shoppingdeals123', 'EPM_Deals']
        resolved_chats = []
        for chat in target_channels:
            try:
                entity = await client.get_input_entity(chat)
                resolved_chats.append(entity)
                logging.info(f"[Channel Mirror] Resolved channel entity: @{chat}")
                
                # Join the channel to receive real-time push updates from Telegram
                from telethon.tl.functions.channels import JoinChannelRequest
                await client(JoinChannelRequest(entity))
                logging.info(f"[Channel Mirror] Successfully joined and subscribed to channel: @{chat}")
            except Exception as resolve_err:
                logging.error(f"[Channel Mirror] Error resolving/joining channel @{chat}: {resolve_err}")
                
        if not resolved_chats:
            logging.error("[Channel Mirror] No channels could be resolved or joined. Mirror listener halted.")
            return
            
        # Define message handler
        async def handler(event):
            chat_name = getattr(event.chat, 'username', None) or str(event.chat_id)
            logging.info(f"[Channel Mirror] Captured post from competitor channel (@{chat_name})")
            
            text = event.raw_text or ""
            urls = re.findall(r'(https?://[^\s>]+)', text)
            if not urls:
                logging.info("[Channel Mirror] Post contains no links. Ignored.")
                return
                
            for url in urls:
                clean_url = url.rstrip('.,;()[]{}*#"\'')
                logging.info(f"[Channel Mirror] Extracted raw link: {clean_url}")
                t = threading.Thread(target=process_deal_url, args=(clean_url,), daemon=True)
                t.start()
                
        # Register handler dynamically
        client.add_event_handler(handler, events.NewMessage(chats=resolved_chats))
        logging.info("[Channel Mirror] Dynamic listener event handler registered. Monitoring active.")
        
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"[Channel Mirror] Telethon client encountered fatal execution error: {e}")
