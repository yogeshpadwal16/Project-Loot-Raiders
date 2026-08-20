import os
import asyncio
import logging
import time
from typing import List, Dict, Any, Union, Optional
from aiolimiter import AsyncLimiter
from concurrent.futures import ThreadPoolExecutor

# Limit to maximum 3 parallel inline browsers to save VPS CPU
inline_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="inline_scraper")

# Import Pyrogram
import pyrogram
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler

# Import Telethon
import telethon
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Import pipeline components
from deal_engine.mirroring.mirror_config import (
    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_STRING_SESSION,
    get_source_channels, RATE_LIMIT_REQUESTS, RATE_LIMIT_PERIOD,
    load_mirror_settings
)
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.redis_queue import RedisMessageQueue
from deal_engine.mirroring.normalizer import MessageNormalizer

class MultiClientMirrorListener:
    def __init__(self, queue: RedisMessageQueue):
        self.queue = queue
        self.pyro_client: Optional[Client] = None
        self.tele_client: Optional[TelegramClient] = None
        self.active_client_name: Optional[str] = None
        self.web_scraper_task: Optional[asyncio.Task] = None
        
        # Throttler to prevent API rate limits / FloodWait (Feature 28)
        self.limiter = AsyncLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_PERIOD)
        self.should_run = True
        self.supervisor_task = None

    async def start_listening(self):
        """Starts the main listener loop with Pyrogram (Primary) and Telethon (Fallback)."""
        self.should_run = True
        self.supervisor_task = asyncio.create_task(self._supervisor_loop())
        logging.info("[Mirror Listener] Multi-client supervisor background task initiated.")

    async def stop_listening(self):
        """Cleanly stops all clients and terminates the supervisor task."""
        self.should_run = False
        if self.supervisor_task:
            self.supervisor_task.cancel()
        if self.web_scraper_task:
            self.web_scraper_task.cancel()
        
        logging.info("[Mirror Listener] Stopping Telegram clients...")
        if self.pyro_client:
            try:
                await self.pyro_client.stop()
            except Exception: pass
        if self.tele_client:
            try:
                await self.tele_client.disconnect()
            except Exception: pass
            
        self.active_client_name = None
        logging.info("[Mirror Listener] Multi-client listener stopped cleanly.")

    async def _supervisor_loop(self):
        """Monitors client health and performs automatic failover if the primary client crashes."""
        while self.should_run:
            try:
                if self.active_client_name is None:
                    # Check if Web Scraper mode is explicitly forced (Feature for 0% ban risk)
                    force_scraper = os.environ.get("FORCE_WEB_SCRAPER", "false").lower() == "true"
                    if not force_scraper:
                        try:
                            settings = load_mirror_settings()
                            if settings.get("force_web_scraper", False):
                                force_scraper = True
                        except Exception:
                            pass

                    if force_scraper:
                        logging.info("[Mirror Listener] FORCE_WEB_SCRAPER option enabled. Skipping Userbots and launching Web Scraper...")
                        success = await self._start_web_scraper()
                        if success:
                            self.active_client_name = "web_scraper"
                            logging.info("[Mirror Listener] Public Web Scraper is now active as primary.")
                        else:
                            logging.error("[Mirror Listener] Public Web Scraper failed to start. Re-trying in 30s...")
                            await asyncio.sleep(30)
                            continue
                    else:
                        # 1. Attempt to start Primary Client (Pyrogram)
                        logging.info("[Mirror Listener] Attempting to start Primary client (Pyrogram)...")
                        success = await self._start_pyrogram()
                        
                        if success:
                            self.active_client_name = "pyrogram"
                            logging.info("[Mirror Listener] Primary client (Pyrogram) is now active.")
                        else:
                            # 2. Fall back to Telethon if Pyrogram fails to initialize/authenticate
                            logging.warning("[Mirror Listener] Pyrogram initialization failed. Falling back to Telethon...")
                            success = await self._start_telethon()
                            if success:
                                self.active_client_name = "telethon"
                                logging.info("[Mirror Listener] Fallback client (Telethon) is now active.")
                            else:
                                # 3. Fall back to public session-less web scraper
                                logging.warning("[Mirror Listener] Both primary and fallback clients failed to start. Falling back to public session-less Web Scraper...")
                                success = await self._start_web_scraper()
                                if success:
                                    self.active_client_name = "web_scraper"
                                    logging.info("[Mirror Listener] Public Web Scraper fallback is now active.")
                                else:
                                    logging.error("[Mirror Listener] All client layers (Pyrogram, Telethon, Web Scraper) failed to start. Re-trying in 30s...")
                                    await asyncio.sleep(30)
                                    continue
                
                # Health Check Checkpoint
                await asyncio.sleep(15)
                await self._check_client_health()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[Mirror Listener] Supervisor loop encountered error: {e}")
                await asyncio.sleep(10)

    async def _check_client_health(self):
        """Performs health check on the active client and restarts/fails-over if dead."""
        if self.active_client_name == "pyrogram" and self.pyro_client:
            if not self.pyro_client.is_connected:
                logging.warning("[Mirror Listener] Active client (Pyrogram) disconnected. Triggering failover to Telethon...")
                try: await self.pyro_client.stop() 
                except Exception: pass
                self.pyro_client = None
                self.active_client_name = None
        elif self.active_client_name == "telethon" and self.tele_client:
            if not self.tele_client.is_connected():
                logging.warning("[Mirror Listener] Active client (Telethon) disconnected. Triggering public Web Scraper fallback...")
                try: await self.tele_client.disconnect()
                except Exception: pass
                self.tele_client = None
                self.active_client_name = None
        elif self.active_client_name == "web_scraper":
            if not self.web_scraper_task or self.web_scraper_task.done():
                logging.warning("[Mirror Listener] Active public Web Scraper task died. Triggering restart...")
                self.web_scraper_task = None
                self.active_client_name = None

    async def _start_pyrogram(self) -> bool:
        """Initializes and runs the Pyrogram client."""
        client = None
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            session_path = os.path.join(base_dir, "pyrogram") # creates pyrogram.session
            
            # Use StringSession if available, else standard session file
            # Pyrogram StringSession format differs from Telethon, so we only use it if format is compatible
            # or fallback to session file.
            client = Client(
                name=session_path,
                api_id=int(TELEGRAM_API_ID),
                api_hash=TELEGRAM_API_HASH,
                workers=4
            )
            self.pyro_client = client
            
            # Connect in non-interactive mode
            await client.connect()
            
            # Check authorization
            try:
                me = await client.get_me()
                is_authorized = me is not None and not me.is_bot
                if me and me.is_bot:
                    logging.warning("[Mirror Listener] Connected as Bot (@" + getattr(me, 'username', 'unknown') + ") instead of User. Pyrogram listener needs a User session to read competitor channels. Aborting Pyrogram to trigger Telethon fallback...")
            except Exception as auth_err:
                logging.warning(f"[Mirror Listener] Pyrogram authorization check failed: {auth_err}")
                is_authorized = False

            if not is_authorized:
                logging.warning("[Mirror Listener] Pyrogram session is not authorized or is a bot. Pyrogram start aborted.")
                await client.disconnect()
                self.pyro_client = None
                return False
                
            # Set up message handlers for monitored channels
            channels = get_source_channels()
            resolved_chats = []
            
            for ch in channels:
                try:
                    chat_entity = await client.get_chat(ch)
                    resolved_chats.append(chat_entity.id)
                    logging.info(f"[Pyrogram] Resolved chat: {ch} (ID: {chat_entity.id})")
                except Exception as e:
                    logging.warning(f"[Pyrogram] Could not resolve channel {ch}: {e}")
                    
            if not resolved_chats:
                logging.error("[Pyrogram] No source channels resolved. Failing start.")
                await client.disconnect()
                self.pyro_client = None
                return False
                
            # Message Handler Function
            async def pyro_handler(c, message):
                async with self.limiter:
                    # Stage 2: Message Reception
                    chat_name = message.chat.username or message.chat.title or str(message.chat.id)
                    logging.info(f"[INGEST] Pyrogram received message {message.id} from {chat_name}")
                    
                    try:
                        # Stage 5: Message Normalization
                        normalized = MessageNormalizer.from_pyrogram(message)
                        logging.info(f"[PARSE] [CorrID: {normalized.correlation_id}] Normalization PASS. Raw links: {normalized.extracted_urls}")
                        
                        # Stage 3: Queue Insertion
                        logging.info(f"[QUEUE] [CorrID: {normalized.correlation_id}] Attempting enqueue...")
                        success = await asyncio.to_thread(self.queue.enqueue, normalized)
                        if success:
                            logging.info(f"[QUEUE] [CorrID: {normalized.correlation_id}] Enqueue PASS.")
                        else:
                            logging.warning(f"[QUEUE] [CorrID: {normalized.correlation_id}] Enqueue FAIL. Falling back to inline processing...")
                            asyncio.create_task(asyncio.to_thread(self._process_inline, normalized))
                    except Exception as err:
                        logging.error(f"[Listener Exception] [Pyrogram pyro_handler] Error processing message {message.id}: {err}", exc_info=True)
                        raise
                        
            # Register event handler dynamically
            client.add_handler(
                MessageHandler(pyro_handler, filters.chat(resolved_chats))
            )
            logging.info("[Pyrogram] Message handler registered for active channels.")
            return True
        except Exception as e:
            logging.error(f"[Mirror Listener] Failed to start Pyrogram: {e}", exc_info=True)
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            self.pyro_client = None
            return False

    async def _start_telethon(self) -> bool:
        """Initializes and runs the Telethon client."""
        client = None
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            session_path = os.path.join(base_dir, "channel_mirror.session")
            
            session_str = TELEGRAM_STRING_SESSION
            
            if session_str:
                client = TelegramClient(StringSession(session_str), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
            else:
                client = TelegramClient(session_path, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
                
            self.tele_client = client
            await client.connect()
            if not await client.is_user_authorized():
                logging.error("[Telethon] Telethon session is not authorized. Fallback start failed.")
                await client.disconnect()
                self.tele_client = None
                return False
                
            # Resolve channels
            channels = get_source_channels()
            resolved_chats = []
            
            for ch in channels:
                try:
                    entity = await client.get_input_entity(ch)
                    resolved_chats.append(entity)
                    logging.info(f"[Telethon] Resolved chat: {ch}")
                except Exception as e:
                    logging.warning(f"[Telethon] Could not resolve channel {ch}: {e}")
                    
            if not resolved_chats:
                logging.error("[Telethon] No source channels resolved. Failing start.")
                await client.disconnect()
                self.tele_client = None
                return False
                
            # Message Handler Function
            async def tele_handler(event):
                async with self.limiter:
                    # Stage 2: Message Reception
                    chat_name = getattr(event.chat, 'username', None) or str(event.chat_id)
                    logging.info(f"[INGEST] Telethon received message {event.message.id} from {chat_name}")
                    
                    try:
                        # Stage 5: Message Normalization
                        normalized = MessageNormalizer.from_telethon(event.message)
                        logging.info(f"[PARSE] [CorrID: {normalized.correlation_id}] Normalization PASS. Raw links: {normalized.extracted_urls}")
                        
                        # Stage 3: Queue Insertion
                        logging.info(f"[QUEUE] [CorrID: {normalized.correlation_id}] Attempting enqueue...")
                        success = await asyncio.to_thread(self.queue.enqueue, normalized)
                        if success:
                            logging.info(f"[QUEUE] [CorrID: {normalized.correlation_id}] Enqueue PASS.")
                        else:
                            logging.warning(f"[QUEUE] [CorrID: {normalized.correlation_id}] Enqueue FAIL. Falling back to inline processing...")
                            asyncio.create_task(asyncio.to_thread(self._process_inline, normalized))
                    except Exception as err:
                        logging.error(f"[Listener Exception] [Telethon tele_handler] Error processing message {event.message.id}: {err}", exc_info=True)
                        raise
                        
            client.add_event_handler(tele_handler, events.NewMessage(chats=resolved_chats))
            logging.info("[Telethon] Message handler registered for active channels.")
            return True
        except Exception as e:
            logging.error(f"[Mirror Listener] Failed to start Telethon fallback: {e}", exc_info=True)
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            self.tele_client = None
            return False

    def _process_inline(self, normalized: NormalizedMessage):
        """Processes a normalized message directly without pushing to Redis queue (fallback/single-run)."""
        logging.info(f"[QUEUE] [CorrID: {normalized.correlation_id}] Bypassing Redis queue (Processing inline)")
        from deal_engine.mirroring.processor import DealMirrorProcessor
        processor = DealMirrorProcessor(self.queue)
        inline_executor.submit(processor._execute_pipeline, normalized)

    async def run_single_run_scan(self, limit: int = 20):
        """Performs a one-time sweep of recent messages (CI/GitHub Actions support)."""
        logging.info("[Mirror Listener] Executing single-run competitor history sweep...")
        
        # We try to use Pyrogram first, fallback to Telethon
        client_started = await self._start_pyrogram()
        if client_started and self.pyro_client:
            try:
                channels = get_source_channels()
                for ch in channels:
                    try:
                        logging.info(f"[Pyrogram Single-Run] Sweeping last {limit} messages from: {ch}")
                        async for message in self.pyro_client.get_chat_history(ch, limit=limit):
                            async with self.limiter:
                                # Stage 2: Message Reception
                                logging.info(f"[INGEST] Pyrogram swept message {message.id} from {ch}")
                                # Stage 5: Message Normalization
                                normalized = MessageNormalizer.from_pyrogram(message)
                                logging.info(f"[PARSE] [CorrID: {normalized.correlation_id}] Normalization PASS.")
                                # Stage 3: Queue Insertion / Consumption (Processing Inline)
                                try:
                                    await asyncio.to_thread(self._process_inline, normalized)
                                except Exception as proc_err:
                                    logging.error(f"[Single-Run Processing Exception] [CorrID: {normalized.correlation_id}] Inline processing failed: {proc_err}", exc_info=True)
                    except Exception as ch_err:
                        logging.error(f"[Pyrogram Single-Run] Failed sweeping chat {ch}: {ch_err}", exc_info=True)
                await self.pyro_client.disconnect()
            except Exception as e:
                logging.error(f"[Pyrogram Single-Run] Sweep failed: {e}", exc_info=True)
        else:
            logging.warning("[Mirror Listener] Pyrogram unavailable. Falling back to Telethon for single-run sweep...")
            client_started = await self._start_telethon()
            if client_started and self.tele_client:
                try:
                    channels = get_source_channels()
                    for ch in channels:
                        try:
                            logging.info(f"[Telethon Single-Run] Sweeping last {limit} messages from: {ch}")
                            entity = await self.tele_client.get_input_entity(ch)
                            async for message in self.tele_client.iter_messages(entity, limit=limit):
                                async with self.limiter:
                                    # Stage 2: Message Reception
                                    logging.info(f"[INGEST] Telethon swept message {message.id} from {ch}")
                                    # Stage 5: Message Normalization
                                    normalized = MessageNormalizer.from_telethon(message)
                                    logging.info(f"[PARSE] [CorrID: {normalized.correlation_id}] Normalization PASS.")
                                    # Stage 3: Queue Insertion / Consumption (Processing Inline)
                                    try:
                                        await asyncio.to_thread(self._process_inline, normalized)
                                    except Exception as proc_err:
                                        logging.error(f"[Single-Run Processing Exception] [CorrID: {normalized.correlation_id}] Inline processing failed: {proc_err}", exc_info=True)
                        except Exception as ch_err:
                            logging.error(f"[Telethon Single-Run] Failed sweeping chat {ch}: {ch_err}", exc_info=True)
                    await self.tele_client.disconnect()
                except Exception as e:
                    logging.error(f"[Telethon Single-Run] Sweep failed: {e}", exc_info=True)
            else:
                logging.warning("[Mirror Listener] Both Pyrogram and Telethon failed. Falling back to public session-less web scraper for single-run sweep...")
                try:
                    import httpx
                    import re
                    from bs4 import BeautifulSoup
                    from deal_engine.mirroring.schemas import ButtonSchema
                    from deal_engine.mirroring.normalizer import extract_urls_from_text, extract_coupons_from_text, extract_seller_info
                    
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    }
                    
                    channels = get_source_channels()
                    public_channels = [ch for ch in channels if not (ch.startswith("+") or "joinchat" in ch)]
                    
                    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=30) as client:
                        for ch in public_channels:
                            url = f"https://t.me/s/{ch}"
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                soup = BeautifulSoup(resp.text, "html.parser")
                                messages = soup.find_all("div", class_="tgme_widget_message")
                                logging.info(f"[Web Scraper Single-Run] Sweeping last {limit} messages from: {ch} (Found {len(messages)} elements)")
                                
                                for msg in messages[-limit:]:
                                    post_ref = msg.get("data-post", "")
                                    if not post_ref or "/" not in post_ref:
                                        continue
                                    try:
                                        msg_id = int(post_ref.split("/")[-1])
                                    except ValueError:
                                        continue
                                        
                                    # Stage 2: Message Reception
                                    logging.info(f"[INGEST] Web Scraper swept message {msg_id} from {ch}")
                                    
                                    # Extract content
                                    text_elem = msg.find("div", class_="tgme_widget_message_text")
                                    full_text = text_elem.get_text(separator="\n").strip() if text_elem else ""
                                    
                                    # Extract URLs
                                    extracted_urls = extract_urls_from_text(full_text)
                                    if text_elem:
                                        for a in text_elem.find_all("a"):
                                            href = a.get("href")
                                            if href and href.startswith("http") and href not in extracted_urls:
                                                extracted_urls.append(href)
                                                
                                    buttons = []
                                    btn_container = msg.find("div", class_="tgme_widget_message_inline_keyboard")
                                    if btn_container:
                                        for btn in btn_container.find_all("a", class_="tgme_widget_message_inline_button"):
                                            btn_text = btn.get_text(strip=True)
                                            btn_href = btn.get("href")
                                            buttons.append(ButtonSchema(text=btn_text, url=btn_href))
                                            if btn_href and btn_href.startswith("http") and btn_href not in extracted_urls:
                                                extracted_urls.append(btn_href)
                                                
                                    photo_wrap = msg.find("a", class_="tgme_widget_message_photo_wrap")
                                    photo_url = None
                                    media_type = "none"
                                    if photo_wrap:
                                        style = photo_wrap.get("style", "")
                                        match = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", style)
                                        if match:
                                            photo_url = match.group(1)
                                            media_type = "photo"
                                            
                                    coupons = extract_coupons_from_text(full_text)
                                    seller = extract_seller_info(full_text)
                                    
                                    normalized = NormalizedMessage(
                                        channel_id=ch,
                                        channel_name=ch,
                                        message_id=msg_id,
                                        is_edited=False,
                                        raw_text=full_text,
                                        caption="",
                                        media_type=media_type,
                                        media_file_id=photo_url,
                                        extracted_urls=extracted_urls,
                                        buttons=buttons,
                                        seller=seller,
                                        coupon_codes=coupons,
                                        metadata={
                                            "client": "web_scraper",
                                            "photo_url": photo_url
                                        }
                                    )
                                    logging.info(f"[PARSE] [CorrID: {normalized.correlation_id}] Normalization PASS.")
                                    try:
                                        await asyncio.to_thread(self._process_inline, normalized)
                                    except Exception as proc_err:
                                        logging.error(f"[Single-Run Web Scraper] [CorrID: {normalized.correlation_id}] Inline processing failed: {proc_err}")
                except Exception as run_err:
                    logging.error(f"[Web Scraper Single-Run] Sweep failed: {run_err}", exc_info=True)

    async def _start_web_scraper(self) -> bool:
        """Initializes and runs the public web scraper polling fallback task."""
        self.active_client_name = "web_scraper"
        self.web_scraper_task = asyncio.create_task(self._web_scraper_loop())
        logging.info("[Mirror Listener] Public Web Scraper fallback task started.")
        return True

    async def _web_scraper_loop(self):
        import httpx
        from bs4 import BeautifulSoup
        import re
        from deal_engine.mirroring.schemas import ButtonSchema
        
        logging.info("[Mirror Listener] Starting public web scraper polling loop...")
        
        # Track last processed message IDs to avoid duplicates
        last_seen_msg_ids = {}
        
        # Initialize headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        
        channels = get_source_channels()
        # Filter public channels
        public_channels = [ch for ch in channels if not (ch.startswith("+") or "joinchat" in ch)]
        
        # Perform initial sweep to establish baseline last_seen IDs
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=30) as client:
            for ch in public_channels:
                try:
                    url = f"https://t.me/s/{ch}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        messages = soup.find_all("div", class_="tgme_widget_message")
                        max_id = 0
                        for msg in messages:
                            post_ref = msg.get("data-post", "")
                            if post_ref and "/" in post_ref:
                                try:
                                    msg_id = int(post_ref.split("/")[-1])
                                    if msg_id > max_id:
                                        max_id = msg_id
                                except ValueError:
                                    pass
                        if max_id > 0:
                            # Start baseline 50 messages back so we pull all recent deals on startup
                            baseline_val = max(0, max_id - 50)
                            last_seen_msg_ids[ch] = baseline_val
                            logging.info(f"[Web Scraper] Initialized baseline for {ch} at message ID {baseline_val} (Current max: {max_id})")
                except Exception as init_err:
                    logging.warning(f"[Web Scraper] Failed to initialize baseline for {ch}: {init_err}")
        
        # Main polling loop
        while self.should_run and self.active_client_name == "web_scraper":
            try:
                logging.info("[Web Scraper] Polling competitor channels...")
                async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=30) as client:
                    for ch_idx, ch in enumerate(public_channels):
                        try:
                            # Stagger requests to avoid connection pressure
                            if ch_idx > 0:
                                await asyncio.sleep(2)
                            url = f"https://t.me/s/{ch}"
                            # Retry up to 3 times with backoff on connection errors
                            resp = None
                            for attempt in range(3):
                                try:
                                    resp = await client.get(url)
                                    break
                                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as retry_err:
                                    if attempt < 2:
                                        wait_secs = 3 * (attempt + 1)
                                        logging.warning(f"[Web Scraper] Retry {attempt+1}/3 for {ch} after {retry_err.__class__.__name__}. Waiting {wait_secs}s...")
                                        await asyncio.sleep(wait_secs)
                                    else:
                                        logging.error(f"[Web Scraper] All 3 retries failed for {ch}: {retry_err}")
                            if resp is None:
                                continue
                            if resp.status_code != 200:
                                logging.warning(f"[Web Scraper] Failed to fetch {ch}, status: {resp.status_code}")
                                continue
                                
                            soup = BeautifulSoup(resp.text, "html.parser")
                            messages = soup.find_all("div", class_="tgme_widget_message")
                            
                            new_messages = []
                            baseline_id = last_seen_msg_ids.get(ch, 0)
                            
                            for msg in messages:
                                post_ref = msg.get("data-post", "")
                                if not post_ref or "/" not in post_ref:
                                    continue
                                try:
                                    msg_id = int(post_ref.split("/")[-1])
                                except ValueError:
                                    continue
                                    
                                if msg_id > baseline_id:
                                    new_messages.append((msg_id, msg))
                                    
                            # Process new messages in chronological order (smallest ID first)
                            new_messages.sort(key=lambda x: x[0])
                            
                            for msg_id, msg in new_messages:
                                try:
                                    # Stage 2: Message Reception
                                    logging.info(f"[INGEST] Web Scraper received message {msg_id} from {ch}")
                                    
                                    # Extract content
                                    text_elem = msg.find("div", class_="tgme_widget_message_text")
                                    full_text = text_elem.get_text(separator="\n").strip() if text_elem else ""
                                    
                                    # Extract raw links from text
                                    from deal_engine.mirroring.normalizer import extract_urls_from_text, extract_coupons_from_text, extract_seller_info
                                    extracted_urls = extract_urls_from_text(full_text)
                                    
                                    # Extract additional links from hyperlinked anchors
                                    if text_elem:
                                        for a in text_elem.find_all("a"):
                                            href = a.get("href")
                                            if href and href.startswith("http") and href not in extracted_urls:
                                                extracted_urls.append(href)
                                                
                                    # Extract inline keyboard buttons
                                    buttons = []
                                    btn_container = msg.find("div", class_="tgme_widget_message_inline_keyboard")
                                    if btn_container:
                                        for btn in btn_container.find_all("a", class_="tgme_widget_message_inline_button"):
                                            btn_text = btn.get_text(strip=True)
                                            btn_href = btn.get("href")
                                            buttons.append(ButtonSchema(text=btn_text, url=btn_href))
                                            if btn_href and btn_href.startswith("http") and btn_href not in extracted_urls:
                                                extracted_urls.append(btn_href)
                                                
                                    # Extract photo URL if present
                                    photo_wrap = msg.find("a", class_="tgme_widget_message_photo_wrap")
                                    photo_url = None
                                    media_type = "none"
                                    if photo_wrap:
                                        style = photo_wrap.get("style", "")
                                        match = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", style)
                                        if match:
                                            photo_url = match.group(1)
                                            media_type = "photo"
                                            
                                    coupons = extract_coupons_from_text(full_text)
                                    seller = extract_seller_info(full_text)
                                    
                                    # Stage 5: Message Normalization
                                    normalized = NormalizedMessage(
                                        channel_id=ch,
                                        channel_name=ch,
                                        message_id=msg_id,
                                        is_edited=False,
                                        raw_text=full_text,
                                        caption="",
                                        media_type=media_type,
                                        media_file_id=photo_url,
                                        extracted_urls=extracted_urls,
                                        buttons=buttons,
                                        seller=seller,
                                        coupon_codes=coupons,
                                        metadata={
                                            "client": "web_scraper",
                                            "photo_url": photo_url
                                        }
                                    )
                                    logging.info(f"[PARSE] [CorrID: {normalized.correlation_id}] Normalization PASS. Raw links: {normalized.extracted_urls}")
                                    
                                    # Stage 3: Queue Insertion
                                    logging.info(f"[QUEUE] [CorrID: {normalized.correlation_id}] Attempting enqueue...")
                                    success = await asyncio.to_thread(self.queue.enqueue, normalized)
                                    if success:
                                        logging.info(f"[QUEUE] [CorrID: {normalized.correlation_id}] Enqueue PASS.")
                                    else:
                                        logging.warning(f"[QUEUE] [CorrID: {normalized.correlation_id}] Enqueue FAIL. Falling back to inline processing...")
                                        asyncio.create_task(asyncio.to_thread(self._process_inline, normalized))
                                        
                                    last_seen_msg_ids[ch] = msg_id
                                except Exception as msg_err:
                                    logging.error(f"[INGEST] Error processing message {msg_id} from {ch}: {msg_err}", exc_info=True)
                                    
                        except Exception as ch_err:
                            logging.error(f"[Web Scraper] Error scraping channel {ch}: {ch_err}", exc_info=True)
                            
                # Sleep for 120 seconds (2 minutes) before next poll loop
                await asyncio.sleep(120)
            except Exception as e:
                logging.error(f"[Web Scraper] Polling loop exception: {e}", exc_info=True)
                await asyncio.sleep(30)

