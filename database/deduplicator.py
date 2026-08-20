import asyncio
from typing import Optional
from utils.deduplicator import is_duplicate_and_lock as _async_is_duplicate_and_lock
from utils.deduplicator import release_deal_lock as _async_release_lock

def is_duplicate_and_lock(canonical_key: Optional[str], ttl_seconds: int = 14400) -> bool:
    """Synchronous proxy to async atomic Redis lock check."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        try:
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(_async_is_duplicate_and_lock(canonical_key, ttl_seconds))
        except Exception:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(_async_is_duplicate_and_lock(canonical_key, ttl_seconds)))
                return future.result()
    else:
        return loop.run_until_complete(_async_is_duplicate_and_lock(canonical_key, ttl_seconds))

def release_lock(canonical_key: Optional[str]) -> bool:
    """Synchronous proxy to async Redis lock release."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        try:
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(_async_release_lock(canonical_key))
        except Exception:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(_async_release_lock(canonical_key)))
                return future.result()
    else:
        return loop.run_until_complete(_async_release_lock(canonical_key))

async def is_duplicate_and_lock_async(canonical_key: Optional[str], ttl_seconds: int = 14400) -> bool:
    return await _async_is_duplicate_and_lock(canonical_key, ttl_seconds)

async def release_lock_async(canonical_key: Optional[str]) -> bool:
    return await _async_release_lock(canonical_key)
