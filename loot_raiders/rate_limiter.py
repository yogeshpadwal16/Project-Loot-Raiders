import logging
import asyncio
import time
from typing import Any, Callable, Coroutine, Tuple

logger = logging.getLogger("loot_raiders.rate_limiter")

class PrioritizedTask:
    def __init__(self, priority: int, func: Callable[[], Coroutine[Any, Any, Any]], description: str = ""):
        self.priority = priority
        self.func = func
        self.description = description
        self.created_at = time.time()
        
    def __lt__(self, other: 'PrioritizedTask') -> bool:
        # Lower number = higher priority. If priorities are equal, compare arrival time.
        if self.priority == other.priority:
            return self.created_at < other.created_at
        return self.priority < other.priority

class TeleRateLimiter:
    def __init__(self, min_interval: float = 2.5):
        self.queue = asyncio.PriorityQueue()
        self.min_interval = min_interval
        self.last_sent_time = 0.0
        self.lock = asyncio.Lock()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        
    async def enqueue(self, priority: int, func: Callable[[], Coroutine[Any, Any, Any]], description: str = ""):
        """Enqueues a Telegram task with a specific priority."""
        task = PrioritizedTask(priority, func, description)
        await self.queue.put(task)
        logger.debug(f"Enqueued task '{description}' with priority {priority}")

    def start(self):
        """Starts the background dispatching worker."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("Telegram Rate Limiter worker started.")

    async def stop(self):
        """Gracefully stops the worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Telegram Rate Limiter worker stopped.")

    async def _worker_loop(self):
        while self._running:
            try:
                task: PrioritizedTask = await self.queue.get()
                
                # Enforce the 2.5 seconds minimum interval between dispatches
                async with self.lock:
                    now = time.time()
                    elapsed = now - self.last_sent_time
                    if elapsed < self.min_interval:
                        sleep_time = self.min_interval - elapsed
                        logger.debug(f"Rate limit enforcement: sleeping {sleep_time:.2f}s before sending.")
                        await asyncio.sleep(sleep_time)
                        
                    # Execute task
                    try:
                        logger.info(f"Executing task: {task.description} (Priority: {task.priority})")
                        await task.func()
                        self.last_sent_time = time.time()
                    except Exception as e:
                        logger.error(f"Error executing rate-limited task '{task.description}': {e}", exc_info=True)
                    finally:
                        self.queue.task_done()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Exception in Rate Limiter worker loop: {e}", exc_info=True)
                await asyncio.sleep(1)
