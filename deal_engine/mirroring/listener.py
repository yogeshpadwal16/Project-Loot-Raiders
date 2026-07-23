import os
import asyncio
import logging
import time
from typing import List, Dict, Any, Union, Optional
from aiolimiter import AsyncLimiter

# Import Pyrogram
import pyrogram
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler

# Import Telethon
import telethon
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Import pipeline components
from deal_engine.mirroring.config import (
    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_STRING_SESSION,
    get_source_channels, RATE_LIMIT_REQUESTS, RATE_LIMIT_PERIOD
)
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.queue import RedisMessageQueue
from deal_engine.mirroring.normalizer import MessageNormalizer

class MultiClientMirrorListener:
    def __init__(self, queue: RedisMessageQueue):
        self.queue = queue
        self.pyro_client: Optional[Client] = None
        self.tele_client: Optional[TelegramClient] = None
        self.active_client_name: Optional[str] = None
        
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
                            logging.error("[Mirror Listener] Both primary and fallback clients failed to start. Re-trying in 30s...")
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
                logging.warning("[Mirror Listener] Active client (Telethon) disconnected. Triggering Pyrogram retry...")
                try: await self.tele_client.disconnect()
                except Exception: pass
                self.tele_client = None
                self.active_client_name = None

    async def _start_pyrogram(self) -> bool:
        """Initializes and runs the Pyrogram client."""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            session_path = os.path.join(base_dir, "pyrogram") # creates pyrogram.session
            
            # Use StringSession if available, else standard session file
            # Pyrogram StringSession format differs from Telethon, so we only use it if format is compatible
            # or fallback to session file.
            self.pyro_client = Client(
                name=session_path,
                api_id=int(TELEGRAM_API_ID),
                api_hash=TELEGRAM_API_HASH,
                workers=4
            )
            
            # Connect in non-interactive mode
            await self.pyro_client.connect()
            
            # Check authorization
            try:
                me = await self.pyro_client.get_me()
                is_authorized = me is not None
            except Exception as auth_err:
                logging.warning(f"[Mirror Listener] Pyrogram authorization check failed: {auth_err}")
                is_authorized = False

            if not is_authorized:
                logging.warning("[Mirror Listener] Pyrogram session is not authorized. Pyrogram start aborted.")
                await self.pyro_client.disconnect()
                return False
                
            # Set up message handlers for monitored channels
            channels = get_source_channels()
            resolved_chats = []
            
            for ch in channels:
                try:
                    chat_entity = await self.pyro_client.get_chat(ch)
                    resolved_chats.append(chat_entity.id)
                    logging.info(f"[Pyrogram] Resolved chat: {ch} (ID: {chat_entity.id})")
                except Exception as e:
                    logging.warning(f"[Pyrogram] Could not resolve channel {ch}: {e}")
                    
            if not resolved_chats:
                logging.error("[Pyrogram] No source channels resolved. Failing start.")
                await self.pyro_client.disconnect()
                return False
                
            # Message Handler Function
            async def pyro_handler(client, message):
                async with self.limiter:
                    # Stage 2: Message Reception
                    chat_name = message.chat.username or message.chat.title or str(message.chat.id)
                    logging.info(f"[STAGE 2: Message Reception] Pyrogram received message {message.id} from {chat_name}")
                    
                    try:
                        # Stage 5: Message Normalization
                        normalized = MessageNormalizer.from_pyrogram(message)
                        logging.info(f"[STAGE 5: Message Normalization] [CorrID: {normalized.correlation_id}] Normalization PASS. Raw links: {normalized.extracted_urls}")
                        
                        # Stage 3: Queue Insertion
                        logging.info(f"[STAGE 3: Queue Insertion] [CorrID: {normalized.correlation_id}] Attempting enqueue...")
                        success = self.queue.enqueue(normalized)
                        if success:
                            logging.info(f"[STAGE 3: Queue Insertion] [CorrID: {normalized.correlation_id}] Enqueue PASS.")
                        else:
                            logging.warning(f"[STAGE 3: Queue Insertion] [CorrID: {normalized.correlation_id}] Enqueue FAIL. Falling back to inline processing...")
                            self._process_inline(normalized)
                    except Exception as err:
                        logging.error(f"[Listener Exception] [Pyrogram pyro_handler] Error processing message {message.id}: {err}", exc_info=True)
                        raise
                        
            # Register event handler dynamically
            self.pyro_client.add_handler(
                MessageHandler(pyro_handler, filters.chat(resolved_chats))
            )
            logging.info("[Pyrogram] Message handler registered for active channels.")
            return True
        except Exception as e:
            logging.error(f"[Mirror Listener] Failed to start Pyrogram: {e}", exc_info=True)
            raise

    async def _start_telethon(self) -> bool:
        """Initializes and runs the Telethon client."""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            session_path = os.path.join(base_dir, "channel_mirror.session")
            
            session_str = TELEGRAM_STRING_SESSION
            
            if session_str:
                self.tele_client = TelegramClient(StringSession(session_str), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
            else:
                self.tele_client = TelegramClient(session_path, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
                
            await self.tele_client.connect()
            if not await self.tele_client.is_user_authorized():
                logging.error("[Telethon] Telethon session is not authorized. Fallback start failed.")
                await self.tele_client.disconnect()
                return False
                
            # Resolve channels
            channels = get_source_channels()
            resolved_chats = []
            
            for ch in channels:
                try:
                    entity = await self.tele_client.get_input_entity(ch)
                    resolved_chats.append(entity)
                    logging.info(f"[Telethon] Resolved chat: {ch}")
                except Exception as e:
                    logging.warning(f"[Telethon] Could not resolve channel {ch}: {e}")
                    
            if not resolved_chats:
                logging.error("[Telethon] No source channels resolved. Failing start.")
                await self.tele_client.disconnect()
                return False
                
            # Message Handler Function
            async def tele_handler(event):
                async with self.limiter:
                    # Stage 2: Message Reception
                    chat_name = getattr(event.chat, 'username', None) or str(event.chat_id)
                    logging.info(f"[STAGE 2: Message Reception] Telethon received message {event.message.id} from {chat_name}")
                    
                    try:
                        # Stage 5: Message Normalization
                        normalized = MessageNormalizer.from_telethon(event.message)
                        logging.info(f"[STAGE 5: Message Normalization] [CorrID: {normalized.correlation_id}] Normalization PASS. Raw links: {normalized.extracted_urls}")
                        
                        # Stage 3: Queue Insertion
                        logging.info(f"[STAGE 3: Queue Insertion] [CorrID: {normalized.correlation_id}] Attempting enqueue...")
                        success = self.queue.enqueue(normalized)
                        if success:
                            logging.info(f"[STAGE 3: Queue Insertion] [CorrID: {normalized.correlation_id}] Enqueue PASS.")
                        else:
                            logging.warning(f"[STAGE 3: Queue Insertion] [CorrID: {normalized.correlation_id}] Enqueue FAIL. Falling back to inline processing...")
                            self._process_inline(normalized)
                    except Exception as err:
                        logging.error(f"[Listener Exception] [Telethon tele_handler] Error processing message {event.message.id}: {err}", exc_info=True)
                        raise
                        
            self.tele_client.add_event_handler(tele_handler, events.NewMessage(chats=resolved_chats))
            logging.info("[Telethon] Message handler registered for active channels.")
            return True
        except Exception as e:
            logging.error(f"[Mirror Listener] Failed to start Telethon fallback: {e}", exc_info=True)
            raise

    def _process_inline(self, normalized: NormalizedMessage):
        """Processes a normalized message directly without pushing to Redis queue (fallback/single-run)."""
        logging.info(f"[STAGE 4: Queue Consumption] [CorrID: {normalized.correlation_id}] Bypassing Redis queue (Processing inline)")
        from deal_engine.mirroring.processor import DealMirrorProcessor
        processor = DealMirrorProcessor(self.queue)
        processor._execute_pipeline(normalized)

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
                                logging.info(f"[STAGE 2: Message Reception] Pyrogram swept message {message.id} from {ch}")
                                # Stage 5: Message Normalization
                                normalized = MessageNormalizer.from_pyrogram(message)
                                logging.info(f"[STAGE 5: Message Normalization] [CorrID: {normalized.correlation_id}] Normalization PASS.")
                                # Stage 3: Queue Insertion / Consumption (Processing Inline)
                                try:
                                    self._process_inline(normalized)
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
                                    logging.info(f"[STAGE 2: Message Reception] Telethon swept message {message.id} from {ch}")
                                    # Stage 5: Message Normalization
                                    normalized = MessageNormalizer.from_telethon(message)
                                    logging.info(f"[STAGE 5: Message Normalization] [CorrID: {normalized.correlation_id}] Normalization PASS.")
                                    # Stage 3: Queue Insertion / Consumption (Processing Inline)
                                    try:
                                        self._process_inline(normalized)
                                    except Exception as proc_err:
                                        logging.error(f"[Single-Run Processing Exception] [CorrID: {normalized.correlation_id}] Inline processing failed: {proc_err}", exc_info=True)
                        except Exception as ch_err:
                            logging.error(f"[Telethon Single-Run] Failed sweeping chat {ch}: {ch_err}", exc_info=True)
                    await self.tele_client.disconnect()
                except Exception as e:
                    logging.error(f"[Telethon Single-Run] Sweep failed: {e}", exc_info=True)
            else:
                logging.error("[Mirror Listener] Both Pyrogram and Telethon failed to initialize for history sweep.")
