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

active_client = None
should_terminate = False

# Auth-error patterns that indicate a corrupted/invalid session
AUTH_ERROR_PATTERNS = [
    "authorization key",
    "auth_key_duplicated",
    "session revoked",
    "user deactivated",
    "not authorized",
]

# Non-product URL patterns to skip (search pages, category listings, etc.)
SKIP_URL_PATTERNS = [
    r'amazon\.in/s\?',        # Amazon search pages
    r'flipkart\.com/.*/pr\?', # Flipkart category pages
    r'/gp/goldbox',            # Amazon deals hub
    r'/gp/bestsellers',        # Amazon bestsellers
    r'/gp/new-releases',       # Amazon new releases
]

# Bounded concurrency control to prevent OOM errors on VPS by limiting parallel browser runs (Feature 2)
process_semaphore = threading.Semaphore(3)

def process_deal_url_sem(url: str, platform_hint: str = None):
    with process_semaphore:
        try:
            process_deal_url(url, platform_hint)
        except Exception as e:
            logging.error(f"[Channel Mirror] Error processing deal URL {url}: {e}")

def start_channel_mirror():
    """Spawns the Telegram Client mirror listener in a separate daemon thread."""
    thread = threading.Thread(target=run_mirror_loop, daemon=True)
    thread.start()
    logging.info("[Channel Mirror] Background scraping daemon thread started.")

def stop_channel_mirror():
    """Disconnects the active Telethon client cleanly to prevent session locks."""
    global active_client, should_terminate
    should_terminate = True
    if active_client:
        logging.info("[Channel Mirror] Shutting down Telethon client cleanly...")
        try:
            loop = active_client.loop
            if loop and loop.is_running():
                # We can't disconnect directly synchronously from here since it's another thread,
                # so schedule it.
                asyncio.run_coroutine_threadsafe(active_client.disconnect(), loop)
            else:
                try:
                    asyncio.run(active_client.disconnect())
                except Exception:
                    pass
            logging.info("[Channel Mirror] Telethon client disconnect signal sent.")
        except Exception as shutdown_err:
            logging.error(f"[Channel Mirror] Error during clean client shutdown: {shutdown_err}")

def _load_string_session() -> str:
    """Load TELEGRAM_STRING_SESSION from env var or from the text file fallback."""
    session_str = os.environ.get("TELEGRAM_STRING_SESSION", "").strip()
    if session_str:
        return session_str
    # Fallback: read from TELEGRAM_STRING_SESSION.txt in project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_file = os.path.join(base_dir, "TELEGRAM_STRING_SESSION.txt")
    if os.path.exists(session_file):
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                logging.info("[Channel Mirror] Loaded StringSession from TELEGRAM_STRING_SESSION.txt")
                return content
        except Exception as e:
            logging.warning(f"[Channel Mirror] Failed to read TELEGRAM_STRING_SESSION.txt: {e}")
    return ""

def _is_auth_error(error_str: str) -> bool:
    """Check if an error indicates a corrupted or revoked session."""
    error_lower = error_str.lower()
    return any(pattern in error_lower for pattern in AUTH_ERROR_PATTERNS)

def _invalidate_file_session():
    """Delete the corrupted file-based session to allow re-authentication."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_path = os.path.join(base_dir, "channel_mirror.session")
    for ext in ["", "-journal", "-shm", "-wal"]:
        path = session_path + ext
        if os.path.exists(path):
            try:
                os.remove(path)
                logging.info(f"[Channel Mirror] Removed corrupted session file: {path}")
            except Exception as e:
                logging.warning(f"[Channel Mirror] Failed to remove {path}: {e}")

def _extract_urls_from_message(event) -> list:
    """Extract URLs from both raw text AND message entities (buttons, hyperlinks)."""
    urls = []
    text = event.raw_text or ""
    
    # 1. Extract from raw text
    text_urls = re.findall(r'(https?://[^\s>]+)', text)
    urls.extend(text_urls)
    
    # 2. Extract from message entities (inline URLs, text links)
    if hasattr(event, 'message') and event.message and hasattr(event.message, 'entities') and event.message.entities:
        from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl
        for entity in event.message.entities:
            if isinstance(entity, MessageEntityTextUrl):
                # Hyperlinked text with a different URL
                if entity.url and entity.url.startswith("http"):
                    urls.append(entity.url)
            elif isinstance(entity, MessageEntityUrl):
                # URL visible in the text (already captured by regex, but be safe)
                start = entity.offset
                end = entity.offset + entity.length
                entity_url = text[start:end]
                if entity_url.startswith("http") and entity_url not in urls:
                    urls.append(entity_url)
    
    # 3. Extract from reply_markup buttons (inline keyboards)
    if hasattr(event, 'message') and event.message and hasattr(event.message, 'reply_markup') and event.message.reply_markup:
        markup = event.message.reply_markup
        if hasattr(markup, 'rows'):
            for row in markup.rows:
                if hasattr(row, 'buttons'):
                    for button in row.buttons:
                        if hasattr(button, 'url') and button.url:
                            urls.append(button.url)
    
    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for u in urls:
        clean = u.rstrip('.,;()[]{}*#"\'') 
        if clean not in seen:
            seen.add(clean)
            unique_urls.append(clean)
    
    return unique_urls

def _should_skip_url(url: str) -> bool:
    """Check if a URL is a non-product page (search, category, etc.) that should be skipped."""
    for pattern in SKIP_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False

def run_mirror_loop():
    """Initializes a dedicated asyncio event loop for Telethon client with auto-restart capability."""
    global should_terminate
    backoff = 20  # Start with 20 seconds
    max_backoff = 600  # Cap at 10 minutes
    consecutive_auth_errors = 0
    max_auth_retries = 5  # Give up after 5 consecutive auth errors
    
    while not should_terminate:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(mirror_main())
            # If mirror_main completed normally (not from a crash), reset backoff
            backoff = 20
            consecutive_auth_errors = 0
        except Exception as loop_err:
            error_str = str(loop_err)
            logging.error(f"[Channel Mirror] Loop crashed: {error_str}")
            
            if _is_auth_error(error_str):
                consecutive_auth_errors += 1
                logging.warning(f"[Channel Mirror] Auth error #{consecutive_auth_errors}/{max_auth_retries}. Invalidating corrupted session...")
                _invalidate_file_session()
                
                if consecutive_auth_errors >= max_auth_retries:
                    logging.error(f"[Channel Mirror] {max_auth_retries} consecutive auth errors. Mirror listener stopped. "
                                  f"Please re-generate your Telegram session (delete channel_mirror.session and restart).")
                    break
            
        if should_terminate:
            break
        logging.warning(f"[Channel Mirror] Telethon client disconnected or loop finished. Re-initiating connection in {backoff} seconds...")
        time.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)  # Exponential backoff

async def mirror_main():
    global active_client
    # Load API credentials from environment
    api_id_str = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    
    if not api_id_str or not api_hash:
        logging.error("[Channel Mirror] TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables are required. Listener halted.")
        return
    
    try:
        api_id = int(api_id_str)
    except ValueError:
        logging.error(f"[Channel Mirror] Invalid API ID in configuration: {api_id_str}. Listener halted.")
        return

    # Path to store session file in base directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_path = os.path.join(base_dir, "channel_mirror.session")
    
    # Prefer StringSession (more resilient than file-based sessions)
    session_str = _load_string_session()
    
    logging.info("[Channel Mirror] Preparing Telethon Client setup...")
    # Authentication warning on startup
    logging.info("==========================================================================")
    logging.info("🌟 [Channel Mirror] REAL-TIME TELEGRAM MONITOR INITIATING 🌟")
    logging.info("👉 Note: If this is your first run, check your terminal/console! ")
    logging.info("   You will be prompted to enter your phone number and login code.")
    logging.info("==========================================================================")
    
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
        active_client = client
        
        # Now resolve and join target channels
        target_channels = ['Loot_shoppingdeals123', 'EPM_Deals', 'idoffers', 'indiafreestuffin', '+jY1FAgS1Wx80Mjk1', 'countingunique']
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
            
            # Extract URLs from text, entities, and buttons
            urls = _extract_urls_from_message(event)
            if not urls:
                logging.info("[Channel Mirror] Post contains no links. Ignored.")
                return
                
            for clean_url in urls:
                if _should_skip_url(clean_url):
                    logging.info(f"[Channel Mirror] Skipping non-product URL: {clean_url[:80]}")
                    continue
                logging.info(f"[Channel Mirror] Extracted link: {clean_url}")
                t = threading.Thread(target=process_deal_url_sem, args=(clean_url,), daemon=True)
                t.start()
                
        # Register handler dynamically
        client.add_event_handler(handler, events.NewMessage(chats=resolved_chats))
        logging.info("[Channel Mirror] Dynamic listener event handler registered. Monitoring active.")
        
        # Sweep last 10 messages from each channel to catch deals posted during downtime
        logging.info("[Channel Mirror] Sweeping last 10 messages from channels to capture downtime deals...")
        for entity in resolved_chats:
            try:
                chat_name = getattr(entity, 'username', None) or str(entity.id) if hasattr(entity, 'id') else "private_chat"
                async for message in client.iter_messages(entity, limit=10):
                    text = message.text or ""
                    urls = re.findall(r'(https?://[^\s>]+)', text)
                    if urls:
                        logging.info(f"[Channel Mirror] History sweep found links in competitor @{chat_name}")
                        for url in urls:
                            clean_url = url.rstrip('.,;()[]{}*#"\'')
                            logging.info(f"[Channel Mirror] Sweeping link: {clean_url}")
                            t = threading.Thread(target=process_deal_url_sem, args=(clean_url,), daemon=True)
                            t.start()
            except Exception as sweep_err:
                logging.warning(f"[Channel Mirror] Failed to sweep history for channel: {sweep_err}")
                
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"[Channel Mirror] Telethon client encountered fatal execution error: {e}")
    finally:
        logging.info("[Channel Mirror] Cleaning up Telethon client connection...")
        try:
            # We check if client exists and is connected
            if 'client' in locals() and client and client.is_connected():
                await client.disconnect()
                logging.info("[Channel Mirror] Telethon client disconnected cleanly.")
        except Exception as disconnect_err:
            logging.warning(f"[Channel Mirror] Error during client disconnect: {disconnect_err}")
            
        if active_client == client:
            active_client = None

def run_mirror_single_run():
    """Runs a one-time scan of the last 20 messages in competitor channels (suitable for CI/Actions)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(mirror_single_run_async())
    finally:
        loop.close()

async def mirror_single_run_async():
    api_id_str = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    
    if not api_id_str or not api_hash:
        logging.error("[Channel Mirror Single-Run] TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables are required.")
        return
    try:
        api_id = int(api_id_str)
    except ValueError:
        logging.error(f"[Channel Mirror Single-Run] Invalid API ID: {api_id_str}")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_path = os.path.join(base_dir, "channel_mirror.session")
    
    logging.info("[Channel Mirror Single-Run] Authenticating Telethon Client...")
    session_str = _load_string_session()
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
        
        target_channels = ['Loot_shoppingdeals123', 'EPM_Deals', 'idoffers', 'indiafreestuffin', '+jY1FAgS1Wx80Mjk1', 'countingunique']
        
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
                            except Exception: pass
                        else:
                            logging.warning(f"[Channel Mirror Single-Run] Error joining invite {invite_hash}: {invite_err}")
                else:
                    clean_username = chat_clean.lstrip("@")
                    entity = await client.get_input_entity(clean_username)
                    resolved_chats.append((entity, clean_username))
                    try:
                        await client(JoinChannelRequest(entity))
                    except Exception: pass
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
                            t = threading.Thread(target=process_deal_url_sem, args=(clean_url,))
                            t.start()
                            t.join()
                        except Exception as proc_err:
                            logging.error(f"[Channel Mirror Single-Run] Error processing URL {clean_url}: {proc_err}")
            except Exception as scan_err:
                logging.error(f"[Channel Mirror Single-Run] Error scanning channel {name}: {scan_err}")
                
        logging.info("[Channel Mirror Single-Run] One-time mirror scan finished.")
    except Exception as e:
        logging.error(f"[Channel Mirror Single-Run] Encountered fatal error: {e}")
    finally:
        try:
            if client.is_connected():
                await client.disconnect()
        except Exception:
            pass
