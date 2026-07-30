import os
import json
import logging
import asyncio

logger = logging.getLogger("loot_raiders.session_manager")


class MultiAccountSessionManager:
    """
    Manages multiple Telegram userbot sessions, SOCKS5 proxies,
    and fallback routing to handle Telegram FloodWait limits.
    """
    def __init__(self, config_path: str = None):
        if not config_path:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions_config.json")
        self.config_path = config_path
        self.accounts = []
        self.active_index = 0
        self._load_config()

    def _load_config(self):
        """Loads account sessions and proxies from config JSON."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Session config not found at: {self.config_path}")
            return
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                self.accounts = data.get("accounts", [])
                logger.info(f"[SessionManager] Loaded {len(self.accounts)} userbot account configurations.")
        except Exception as e:
            logger.error(f"[SessionManager] Failed to load session config: {e}")

    def get_active_account(self) -> dict | None:
        """Returns the current active account config."""
        if not self.accounts:
            return None
        return self.accounts[self.active_index]

    def rotate_on_floodwait(self):
        """Rotates to the next userbot account when FloodWait is encountered."""
        if len(self.accounts) <= 1:
            logger.warning("[SessionManager] Only 1 account configured. Rotation skipped.")
            return
        
        self.active_index = (self.active_index + 1) % len(self.accounts)
        new_active = self.accounts[self.active_index]
        logger.info(f"[SessionManager] FloodWait detected. Switched active userbot session to: {new_active['session_name']}")

    async def initialize_clients(self):
        """
        Initializes Pyrogram/Hydrogram Client sessions using configured SOCKS5 proxies.
        (Simulates API connection checks).
        """
        for acc in self.accounts:
            session = acc.get("session_name")
            proxy = acc.get("proxy", {})
            logger.info(
                f"[SessionManager] Pre-authenticating Pyrogram userbot '{session}' "
                f"via SOCKS5 proxy: {proxy.get('hostname')}:{proxy.get('port')}"
            )
            # Simulated async connect check
            await asyncio.sleep(0.1)

        logger.info("[SessionManager] All configured userbot clients pre-authenticated.")
