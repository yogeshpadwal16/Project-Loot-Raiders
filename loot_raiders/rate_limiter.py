import asyncio
import logging
import time

logger = logging.getLogger("loot_raiders.rate_limiter")


class PriorityRateLimiter:
    """
    Priority Queue combined with rate limit pacing to respect Telegram FloodWait thresholds.
    Ensures high-value price errors (Priority 1) are posted instantly,
    while generic feed updates (Priority 3) are queued and paced at 2.5s gaps.
    """
    def __init__(self, min_gap_seconds: float = 2.5):
        self.queue = asyncio.PriorityQueue()
        self.min_gap_seconds = min_gap_seconds
        self.last_sent_time = 0.0
        self.lock = asyncio.Lock()

    async def add_task(self, priority: int, task_callable, *args, **kwargs):
        """
        Enqueues a posting task.
        Priority values: 1 (High/Glitch), 2 (Medium/verified drop), 3 (Low/General)
        """
        entry_time = time.time()
        # priority, entry_time, callback, args, kwargs
        await self.queue.put((priority, entry_time, task_callable, args, kwargs))
        logger.info(f"[Limiter] Task enqueued at priority {priority}.")

    async def run_limiter_worker(self):
        """Continuously pulls tasks from queue and executes them with paced rate limits."""
        while True:
            # wait for task
            priority, _, task_callable, args, kwargs = await self.queue.get()
            try:
                async with self.lock:
                    now = time.time()
                    elapsed = now - self.last_sent_time
                    
                    # Pace posting frequency
                    if elapsed < self.min_gap_seconds:
                        delay = self.min_gap_seconds - elapsed
                        logger.info(f"[Limiter] Pacing output: sleeping for {delay:.2f}s (Telegram FloodWait guard)")
                        await asyncio.sleep(delay)
                    
                    # Execute task
                    await task_callable(*args, **kwargs)
                    self.last_sent_time = time.time()
            except Exception as e:
                logger.error(f"[Limiter] Task execution failed: {e}")
            finally:
                self.queue.task_done()
