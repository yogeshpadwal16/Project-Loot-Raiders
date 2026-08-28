"""
Phase 2: Atomic Redis Deduplication Module.
Provides thread-safe & worker-safe atomic deduplication using Redis SET key val EX ttl NX.
Includes graceful in-memory fallback if Redis connection is unavailable.
"""

import os
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("LootDeduplicator")

# Global Redis client placeholder & in-memory fallback cache
_REDIS_CLIENT: Optional[Any] = None
_REDIS_LAST_FAILED_AT: float = 0.0
_REDIS_RETRY_INTERVAL: float = 60.0  # seconds
_IN_MEMORY_DEDUP_CACHE: Dict[str, float] = {}
DEFAULT_TTL_SEC = 14400  # 4 hours


def _get_redis_client() -> Optional[Any]:
    """Lazy-initializes Dragonfly / Redis client connection with circuit breaker cooldown."""
    global _REDIS_CLIENT, _REDIS_LAST_FAILED_AT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    now = time.time()
    if now - _REDIS_LAST_FAILED_AT < _REDIS_RETRY_INTERVAL:
        return None

    redis_host = os.environ.get("REDIS_HOST", "127.0.0.1")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    redis_db = int(os.environ.get("REDIS_DB", 0))
    redis_pass = os.environ.get("REDIS_PASSWORD", None)

    try:
        import redis
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_pass,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
            decode_responses=True,
        )
        # Test connection ping
        client.ping()
        _REDIS_CLIENT = client
        logger.info(f"[Redis Deduplicator] Successfully connected to Redis at {redis_host}:{redis_port}")
        return _REDIS_CLIENT
    except Exception as e:
        _REDIS_LAST_FAILED_AT = now
        _REDIS_CLIENT = None
        logger.warning(f"[Redis Deduplicator] Redis unavailable ({e}). Operating in-memory deduplication fallback (cooldown 60s).")
        return None


def is_duplicate_and_lock(canonical_key: str, ttl_seconds: int = DEFAULT_TTL_SEC) -> bool:
    """
    Executes an atomic lock check on canonical_key.
    Returns:
      True  -> Duplicate detected (lock exists).
      False -> Unique deal! Lock acquired successfully.
    """
    if not canonical_key:
        return False

    lock_key = f"loot:dedup:{canonical_key}"
    redis_client = _get_redis_client()

    if redis_client:
        try:
            # Redis Atomic Operation: SET key val EX ttl NX
            # Returns True if key was set (was new), None/False if key already existed
            is_new = redis_client.set(lock_key, "1", ex=ttl_seconds, nx=True)
            if is_new:
                logger.debug(f"[Redis Lock] Acquired atomic lock for key='{canonical_key}' (TTL={ttl_seconds}s)")
                return False  # Not a duplicate!
            else:
                logger.info(f"[Redis Lock] Duplicate suppressed for key='{canonical_key}'")
                return True   # Duplicate!
        except Exception as e:
            logger.warning(f"[Redis Lock] Redis SET NX error ({e}). Falling back to in-memory check.")

    # In-Memory Fallback Deduplication
    now = time.time()
    # Cleanup expired in-memory keys
    expired_keys = [k for k, exp in _IN_MEMORY_DEDUP_CACHE.items() if now > exp]
    for k in expired_keys:
        del _IN_MEMORY_DEDUP_CACHE[k]

    if lock_key in _IN_MEMORY_DEDUP_CACHE:
        if now < _IN_MEMORY_DEDUP_CACHE[lock_key]:
            logger.info(f"[In-Memory Lock] Duplicate suppressed for key='{canonical_key}'")
            return True  # Duplicate!

    # Acquire lock in memory
    _IN_MEMORY_DEDUP_CACHE[lock_key] = now + ttl_seconds
    logger.debug(f"[In-Memory Lock] Acquired lock for key='{canonical_key}' (TTL={ttl_seconds}s)")
    return False  # Not a duplicate!


def release_lock(canonical_key: str) -> None:
    """Releases lock for canonical_key if processing failed and retry is required."""
    lock_key = f"loot:dedup:{canonical_key}"
    redis_client = _get_redis_client()
    if redis_client:
        try:
            redis_client.delete(lock_key)
        except Exception:
            pass
    if lock_key in _IN_MEMORY_DEDUP_CACHE:
        del _IN_MEMORY_DEDUP_CACHE[lock_key]
