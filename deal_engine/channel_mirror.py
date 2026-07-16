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
        target_channels = ['Loot_shoppingdeals123', 'EPM_Deals', 'idoffers', 'indiafreestuffin', '+jY1FAgS1Wx80Mjk1']
        resolved_chats = []
        
        from telethon.tl.functions.channels import JoinChannelRequest
        from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
        from telethon.tl.types import ChatInviteAlready
        
        for chat in target_channels:
            chat_clean = chat.strip()
            try:
                if chat_clean.startswith("+") or "joinchat/" in chat_clean:
                    # Extract private invite hash
                    invite_hash = chat_clean.split("joinchat/")[-1].split("+")[-1].strip("/")
                    logging.info(f"[Channel Mirror] Processing private invite hash: {invite_hash}")
                    try:
                        # First check if we are already in the channel or retrieve details
                        invite_info = await client(CheckChatInviteRequest(invite_hash))
                        
                        if isinstance(invite_info, ChatInviteAlready):
                            # Already joined
                            entity = await client.get_input_entity(invite_info.chat)
                            resolved_chats.append(entity)
                            logging.info(f"[Channel Mirror] Already participant of private channel: {invite_info.chat.title}")
                        else:
                            # Join the private channel
                            updates = await client(ImportChatInviteRequest(invite_hash))
                            if hasattr(updates, "chats") and updates.chats:
                                entity = await client.get_input_entity(updates.chats[0])
                                resolved_chats.append(entity)
                                logging.info(f"[Channel Mirror] Successfully joined private channel: {updates.chats[0].title}")
                            else:
                                # Fallback: scan dialogue to match
                                logging.info(f"[Channel Mirror] Private invite joined. Loading dialogues...")
                                dialogs = await client.get_dialogs()
                                # We'll check again via CheckChatInviteRequest which now should return ChatInviteAlready
                                double_check = await client(CheckChatInviteRequest(invite_hash))
                                if hasattr(double_check, "chat"):
                                    entity = await client.get_input_entity(double_check.chat)
                                    resolved_chats.append(entity)
                                    logging.info(f"[Channel Mirror] Resolved private channel: {double_check.chat.title}")
                    except Exception as invite_err:
                        # Fallback for UserAlreadyParticipant or other RpcErrors
                        if "ALREADY_PARTICIPANT" in str(invite_err):
                            try:
                                # Try checking the invite again to fetch the chat details
                                invite_info = await client(CheckChatInviteRequest(invite_hash))
                                if hasattr(invite_info, "chat"):
                                    entity = await client.get_input_entity(invite_info.chat)
                                    resolved_chats.append(entity)
                                    logging.info(f"[Channel Mirror] Resolved already joined private channel: {invite_info.chat.title}")
                            except Exception as inner_err:
                                logging.error(f"[Channel Mirror] Failed to resolve already joined private channel {invite_hash}: {inner_err}")
                        else:
                            logging.error(f"[Channel Mirror] Error joining private invite {invite_hash}: {invite_err}")
                else:
                    # Public channel username
                    clean_username = chat_clean.lstrip("@")
                    entity = await client.get_input_entity(clean_username)
                    resolved_chats.append(entity)
                    logging.info(f"[Channel Mirror] Resolved public channel: @{clean_username}")
                    
                    # Join the public channel
                    await client(JoinChannelRequest(entity))
                    logging.info(f"[Channel Mirror] Successfully joined/subscribed to public channel: @{clean_username}")
            except Exception as resolve_err:
                logging.error(f"[Channel Mirror] Error resolving/joining channel {chat_clean}: {resolve_err}")
                
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
