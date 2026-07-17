import os
import re
import logging
import threading
import asyncio
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from deal_engine.deal_processor import process_deal_url
from config.settings import load_settings

def start_channel_mirror():
    """Spawns the Telegram Client mirror listener in a separate daemon thread."""
    thread = threading.Thread(target=run_mirror_loop, daemon=True)
    thread.start()
    logging.info("[Channel Mirror] Background scraping daemon thread started.")

def run_mirror_loop():
    """Initializes a dedicated asyncio event loop for Telethon client with auto-restart capability."""
    while True:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(mirror_main())
        except Exception as loop_err:
            logging.error(f"[Channel Mirror] Loop crashed: {loop_err}")
            
        logging.warning("[Channel Mirror] Telethon client disconnected or loop finished. Re-initiating connection in 20 seconds...")
        time.sleep(20)

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
    
    session_str = os.environ.get("TELEGRAM_STRING_SESSION", "").strip()
    if session_str:
        logging.info("[Channel Mirror] Initializing Telethon Client using StringSession...")
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
    else:
        logging.info(f"[Channel Mirror] Initializing Telethon Client using file session: {session_path}")
        client = TelegramClient(session_path, api_id, api_hash)
    
    try:
        # Prevent interactive login prompts in non-interactive cloud environments
        is_interactive = not (os.environ.get("GITHUB_ACTIONS") == "true" or session_str)
        if is_interactive:
            await client.start()
        else:
            await client.connect()
            if not await client.is_user_authorized():
                logging.error("[Channel Mirror] Telegram Client session is not authorized. Non-interactive run aborted.")
                return
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

def run_mirror_single_run():
    """Runs a one-time scan of the last 20 messages in competitor channels (suitable for CI/Actions)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(mirror_single_run_async())
    finally:
        loop.close()

async def mirror_single_run_async():
    api_id_str = os.environ.get("TELEGRAM_API_ID", "39413198").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "d648fd457db96dffa53ae18d3d1869d8").strip()
    try:
        api_id = int(api_id_str)
    except ValueError:
        logging.error(f"[Channel Mirror Single-Run] Invalid API ID: {api_id_str}")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_path = os.path.join(base_dir, "channel_mirror.session")
    
    logging.info("[Channel Mirror Single-Run] Authenticating Telethon Client...")
    session_str = os.environ.get("TELEGRAM_STRING_SESSION", "").strip()
    if session_str:
        logging.info("[Channel Mirror Single-Run] Initializing Telethon Client using StringSession...")
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
    else:
        logging.info(f"[Channel Mirror Single-Run] Initializing Telethon Client using file session: {session_path}")
        client = TelegramClient(session_path, api_id, api_hash)
    
    try:
        is_interactive = not (os.environ.get("GITHUB_ACTIONS") == "true" or session_str)
        if is_interactive:
            await client.start()
        else:
            await client.connect()
            if not await client.is_user_authorized():
                logging.error("[Channel Mirror Single-Run] Telegram Client session is not authorized. Non-interactive run aborted.")
                return
        logging.info("[Channel Mirror Single-Run] Telegram Client authenticated successfully.")
        
        target_channels = ['Loot_shoppingdeals123', 'EPM_Deals', 'idoffers', 'indiafreestuffin', '+jY1FAgS1Wx80Mjk1']
        
        from telethon.tl.functions.channels import JoinChannelRequest
        from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
        from telethon.tl.types import ChatInviteAlready
        
        resolved_chats = []
        for chat in target_channels:
            chat_clean = chat.strip()
            try:
                if chat_clean.startswith("+") or "joinchat/" in chat_clean:
                    invite_hash = chat_clean.split("joinchat/")[-1].split("+")[-1].strip("/")
                    try:
                        invite_info = await client(CheckChatInviteRequest(invite_hash))
                        if isinstance(invite_info, ChatInviteAlready):
                            entity = await client.get_input_entity(invite_info.chat)
                            resolved_chats.append((entity, invite_hash))
                        else:
                            updates = await client(ImportChatInviteRequest(invite_hash))
                            if hasattr(updates, "chats") and updates.chats:
                                entity = await client.get_input_entity(updates.chats[0])
                                resolved_chats.append((entity, invite_hash))
                    except Exception as invite_err:
                        if "ALREADY_PARTICIPANT" in str(invite_err):
                            try:
                                invite_info = await client(CheckChatInviteRequest(invite_hash))
                                if hasattr(invite_info, "chat"):
                                    entity = await client.get_input_entity(invite_info.chat)
                                    resolved_chats.append((entity, invite_hash))
                            except: pass
                        else:
                            logging.warning(f"[Channel Mirror Single-Run] Error joining invite {invite_hash}: {invite_err}")
                else:
                    clean_username = chat_clean.lstrip("@")
                    entity = await client.get_input_entity(clean_username)
                    resolved_chats.append((entity, clean_username))
                    try:
                        await client(JoinChannelRequest(entity))
                    except: pass
            except Exception as resolve_err:
                logging.error(f"[Channel Mirror Single-Run] Error resolving {chat_clean}: {resolve_err}")

        for entity, name in resolved_chats:
            try:
                logging.info(f"[Channel Mirror Single-Run] Scanning last 20 messages from competitor: @{name}")
                async for message in client.iter_messages(entity, limit=20):
                    text = message.text or ""
                    urls = re.findall(r'(https?://[^\s>]+)', text)
                    if urls:
                        logging.info(f"[Channel Mirror Single-Run] Found {len(urls)} links in post from @{name}")
                    for url in urls:
                        clean_url = url.rstrip('.,;()[]{}*#"\'')
                        logging.info(f"[Channel Mirror Single-Run] Extracted raw link: {clean_url}")
                        try:
                            # Process deal URL in a separate thread to bypass Playwright asyncio constraints
                            import threading
                            t = threading.Thread(target=process_deal_url, args=(clean_url,))
                            t.start()
                            t.join()
                        except Exception as proc_err:
                            logging.error(f"[Channel Mirror Single-Run] Error processing URL {clean_url}: {proc_err}")
            except Exception as scan_err:
                logging.error(f"[Channel Mirror Single-Run] Error scanning channel {name}: {scan_err}")
                
        await client.disconnect()
        logging.info("[Channel Mirror Single-Run] One-time mirror scan finished.")
    except Exception as e:
        logging.error(f"[Channel Mirror Single-Run] Encountered fatal error: {e}")
