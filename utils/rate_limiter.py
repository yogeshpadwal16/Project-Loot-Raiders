"""
utils/rate_limiter.py
Non-blocking asynchronous leaky-bucket rate limiter with automatic Telegram FloodWaitError recovery.
Enforces broadcast pacing and prevents rate-limit penalties across Telethon/Pyrogram clients.
"""

import asyncio
import time
import logging
from typing import Any, Optional

logger = logging.getLogger("LootRateLimiter")


class TelegramRateLimiter:
    """Leaky-bucket rate limiter enforcing spacing between Telegram messages."""
    def __init__(self, delay_seconds: float = 1.5):
        self.delay_seconds = delay_seconds
        self._last_send_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquires a rate limit token, sleeping if necessary to enforce delay_seconds."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_send_time
            if elapsed < self.delay_seconds:
                wait_time = self.delay_seconds - elapsed
                await asyncio.sleep(wait_time)
            self._last_send_time = time.time()


# Global rate limiter instance
_GLOBAL_RATE_LIMITER = TelegramRateLimiter(delay_seconds=1.5)


async def safe_send_message(client: Any, channel_id: str, message: str, **kwargs) -> Optional[Any]:
    """
    Safely sends a message via Telegram client enforcing pacing intervals.
    Catches FloodWaitError / RPCError, sleeps e.seconds + 1, and retries automatically.
    """
    if not client or not channel_id or not message:
        return None

    await _GLOBAL_RATE_LIMITER.acquire()

    max_retries = kwargs.pop("max_retries", 3)

    for attempt in range(max_retries):
        try:
            # Telethon client method
            if hasattr(client, "send_message"):
                res = await client.send_message(channel_id, message, **kwargs)
                logger.info(f"[Safe Send] Message dispatched to {channel_id} (Attempt {attempt+1})")
                return res
            # Bot method fallback
            elif hasattr(client, "send_message_async"):
                res = await client.send_message_async(channel_id, message, **kwargs)
                return res
            else:
                logger.warning("[Safe Send] Provided client object does not support send_message.")
                return None

        except Exception as e:
            error_type = type(e).__name__
            # Check for Telethon/Pyrogram FloodWaitError
            if "FloodWait" in error_type or hasattr(e, "seconds"):
                wait_sec = getattr(e, "seconds", 10) + 1
                logger.warning(f"[Safe Send] FloodWaitError hit on {channel_id}. Sleeping for {wait_sec}s before retry...")
                await asyncio.sleep(wait_sec)
                continue
            else:
                logger.error(f"[Safe Send] Failed sending message to {channel_id} (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
                else:
                    return None

    return None
