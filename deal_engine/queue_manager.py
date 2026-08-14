"""
Phase 5: Async Queueing & Decoupling Module.
Decouples raw deal ingestion from processing/publishing via concurrent asyncio background workers.
Implements complete Pipeline Workflow:
Ingest -> Unshorten -> Canonical ID -> Redis Lock Check -> Live Scrape -> Monetize -> Publish.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from utils.normalizer import resolve_final_url, get_canonical_product_id
from database.deduplicator import is_duplicate_and_lock, release_lock
from utils.converter import monetize_url
from scrapers.anti_bot_scraper import scrape_product_live_async

logger = logging.getLogger("LootQueueManager")

# In-memory asyncio queue for decoupled deal processing
_DEAL_INGESTION_QUEUE: Optional[asyncio.Queue] = None
_WORKER_TASKS = []
_MAX_CONCURRENCY = 4


async def process_deal_job(job_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Complete Enterprise Pipeline Worker Task:
      Step 1: Ingest Raw Link
      Step 2: Unshorten URL (resolve_final_url)
      Step 3: Extract Canonical Product ID (get_canonical_product_id)
      Step 4: Atomic Redis Lock Check (is_duplicate_and_lock)
      Step 5: Pre-publish Live Scraping Check (scrape_product_live_async)
      Step 6: Monetize Link (monetize_url)
      Step 7: Return final deal payload ready for publishing
    """
    raw_url = job_payload.get("raw_url") or job_payload.get("url") or ""
    if not raw_url:
        return {"status": "skipped", "reason": "empty_url"}

    # Step 1 & 2: Unshorten URL
    final_url = await resolve_final_url(raw_url, timeout_seconds=5)
    if not final_url:
        final_url = raw_url

    # Step 3: Extract Canonical ID
    canonical_id, platform = get_canonical_product_id(final_url)

    # Step 4: Atomic Redis Lock Check
    if is_duplicate_and_lock(canonical_id, ttl_seconds=14400):
        logger.info(f"[Queue Worker] Duplicate deal suppressed for canonical_id='{canonical_id}'")
        return {"status": "duplicate_suppressed", "canonical_id": canonical_id}

    # Step 5: Pre-publish Live Scraping Check
    scraped_data = await scrape_product_live_async(final_url, timeout=10.0)

    # Step 6: Multi-Tier Monetization
    monetized_url, platform_name, auto_cart_url = monetize_url(final_url, platform_hint=platform)

    # Merge job payload with scraped telemetry
    title = scraped_data.get("title") or job_payload.get("title") or "Loot Deal Item"
    price = scraped_data.get("price") or job_payload.get("price") or 0.0
    mrp = scraped_data.get("mrp") or job_payload.get("mrp") or (price * 1.3)
    discount = ((mrp - price) / mrp * 100.0) if mrp > price > 0 else 0.0

    processed_payload = {
        "status": "success",
        "canonical_id": canonical_id,
        "platform": platform_name,
        "title": title,
        "price": price,
        "mrp": mrp,
        "discount": discount,
        "image_url": scraped_data.get("image_url") or job_payload.get("image_url") or "",
        "monetized_url": monetized_url,
        "auto_cart_url": auto_cart_url,
        "in_stock": scraped_data.get("in_stock", True),
        "timestamp": time.time(),
    }

    logger.info(f"[Queue Worker] Processed deal successfully: '{title[:45]}...' ({platform_name.upper()} | Rs.{price})")
    return processed_payload


async def _worker_loop(worker_id: int):
    """Background worker loop consuming deal jobs from queue."""
    logger.info(f"[Queue Worker-{worker_id}] Started consuming ingestion queue...")
    while True:
        try:
            job_payload = await _DEAL_INGESTION_QUEUE.get()
            try:
                await process_deal_job(job_payload)
            except Exception as err:
                logger.error(f"[Queue Worker-{worker_id}] Job processing error: {err}")
            finally:
                _DEAL_INGESTION_QUEUE.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Queue Worker-{worker_id}] Unexpected loop exception: {e}")
            await asyncio.sleep(1.0)


def start_queue_workers(concurrency: int = _MAX_CONCURRENCY):
    """Initiates async queue and worker tasks."""
    global _DEAL_INGESTION_QUEUE, _WORKER_TASKS
    if _DEAL_INGESTION_QUEUE is None:
        _DEAL_INGESTION_QUEUE = asyncio.Queue()

    loop = asyncio.get_event_loop()
    for i in range(concurrency):
        task = loop.create_task(_worker_loop(i + 1))
        _WORKER_TASKS.append(task)
    logger.info(f"[Queue Manager] Spawned {concurrency} async background worker threads.")


def enqueue_raw_deal(raw_url: str, title: str = "", price: float = 0.0, **kwargs) -> bool:
    """Enqueues a raw deal link into the async processing pipeline."""
    global _DEAL_INGESTION_QUEUE
    if _DEAL_INGESTION_QUEUE is None:
        _DEAL_INGESTION_QUEUE = asyncio.Queue()

    payload = {"raw_url": raw_url, "title": title, "price": price, **kwargs}
    try:
        _DEAL_INGESTION_QUEUE.put_nowait(payload)
        logger.debug(f"[Queue Manager] Enqueued raw deal link: {raw_url[:50]}")
        return True
    except Exception as e:
        logger.error(f"[Queue Manager] Failed to enqueue raw deal link: {e}")
        return False
