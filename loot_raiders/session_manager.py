import os
import json
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional
from hydrogram import Client
from hydrogram.errors import FloodWait

logger = logging.getLogger("loot_raiders.session_manager")

class SessionManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.clients: List[Client] = []
        self.client_metadata: Dict[int, Dict[str, Any]] = {} # keyed by index
        self.lock = asyncio.Lock()
        
    def load_config(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.config_path):
            logger.warning(f"Session config not found at {self.config_path}. Returning empty account list.")
            return []
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("accounts", [])
        except Exception as e:
            logger.error(f"Failed to load sessions config: {e}")
            return []

    async def start(self):
        """Initializes and starts all enabled userbot client sessions."""
        accounts = self.load_config()
        for idx, acc in enumerate(accounts):
            if not acc.get("enabled", False):
                logger.info(f"Session {acc.get('session_name')} is disabled. Skipping.")
                continue
                
            session_name = acc.get("session_name")
            api_id = acc.get("api_id")
            api_hash = acc.get("api_hash")
            
            # Setup SOCKS5 proxy if configured
            proxy_conf = acc.get("proxy")
            proxy = None
            if proxy_conf and proxy_conf.get("hostname"):
                proxy = {
                    "scheme": proxy_conf.get("scheme", "socks5"),
                    "hostname": proxy_conf.get("hostname"),
                    "port": int(proxy_conf.get("port", 1080)),
                    "username": proxy_conf.get("username"),
                    "password": proxy_conf.get("password")
                }
            
            logger.info(f"Initializing Hydrogram client: {session_name} (Proxy: {'Enabled' if proxy else 'None'})")
            
            client = Client(
                name=session_name,
                api_id=api_id,
                api_hash=api_hash,
                proxy=proxy,
                workdir=os.path.dirname(self.config_path)
            )
            
            try:
                await client.start()
                self.clients.append(client)
                self.client_metadata[len(self.clients) - 1] = {
                    "name": session_name,
                    "flood_cooldown_until": 0,
                    "last_used": 0
                }
                logger.info(f"Successfully started Hydrogram client: {session_name}")
            except Exception as e:
                logger.error(f"Failed to start Hydrogram client {session_name}: {e}")

        if not self.clients:
            logger.warning("No Hydrogram userbot sessions are currently active in the pool.")

    async def stop(self):
        """Gracefully stops all active userbot sessions."""
        logger.info("Stopping all Hydrogram userbot sessions...")
        for client in self.clients:
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"Error stopping client: {e}")
        self.clients.clear()
        self.client_metadata.clear()
        logger.info("All Hydrogram userbot sessions stopped.")

    async def get_active_client(self) -> Optional[Client]:
        """
        Retrieves the next available client from the pool.
        Implements load balancing & skips accounts on FloodWait cooldown.
        """
        async with self.lock:
            now = time.time()
            available = []
            
            for idx, client in enumerate(self.clients):
                meta = self.client_metadata[idx]
                if now >= meta["flood_cooldown_until"]:
                    available.append((idx, client, meta["last_used"]))
                    
            if not available:
                logger.warning("All clients in the pool are currently on FloodWait cooldown!")
                return None
                
            # Pick the least recently used client
            available.sort(key=lambda x: x[2])
            best_idx, best_client, _ = available[0]
            self.client_metadata[best_idx]["last_used"] = now
            return best_client

    async def handle_flood_wait(self, client: Client, wait_seconds: int):
        """Locks a client when a FloodWait exception is encountered."""
        async with self.lock:
            for idx, c in enumerate(self.clients):
                if c == client:
                    meta = self.client_metadata[idx]
                    meta["flood_cooldown_until"] = time.time() + wait_seconds + 5 # extra 5s buffer
                    logger.warning(f"Client {meta['name']} locked due to FloodWait for {wait_seconds} seconds.")
                    break
