# utils/cache.py
import logging
import time
import json
from typing import Any
import redis
from config.settings import load_settings

logger = logging.getLogger("CacheManager")

_redis_client = None
_local_memory_cache = {}  # In-memory fallback dictionary
_local_memory_locks = {}

def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
        
    settings = load_settings()
    # Read redis configurations from settings (default to Dragonfly host localhost:6379)
    host = settings.get("redis_host", "localhost")
    port = int(settings.get("redis_port", 6379))
    password = settings.get("redis_password", "")
    
    try:
        logger.info(f"Connecting to Dragonfly cache server at {host}:{port}...")
        _redis_client = redis.Redis(
            host=host,
            port=port,
            password=password if password else None,
            socket_timeout=2.0,
            decode_responses=True
        )
        # Test connection
        _redis_client.ping()
        logger.info("Connected to Dragonfly cache successfully.")
        return _redis_client
    except Exception as e:
        logger.warning(f"Dragonfly connection failed: {e}. Falling back to in-memory cache.")
        _redis_client = False  # Set to False to signify connection failed
    return None

def cache_set(key: str, value: Any, expire_seconds: int = None):
    """
    Stores key-value pair in Dragonfly (or falls back to in-memory dict).
    """
    client = get_redis_client()
    if client:
        try:
            val_str = json.dumps(value)
            if expire_seconds:
                client.setex(key, expire_seconds, val_str)
            else:
                client.set(key, val_str)
            return True
        except Exception as e:
            logger.debug(f"Redis write failed: {e}")
            
    # Fallback to local memory
    expiry = time.time() + expire_seconds if expire_seconds else None
    _local_memory_cache[key] = (value, expiry)
    return True

def cache_get(key: str) -> Any:
    """
    Retrieves key value from Dragonfly (or in-memory fallback).
    Returns None if key doesn't exist or is expired.
    """
    client = get_redis_client()
    if client:
        try:
            val_str = client.get(key)
            if val_str:
                return json.loads(val_str)
            return None
        except Exception as e:
            logger.debug(f"Redis read failed: {e}")
            
    # Fallback to local memory
    if key in _local_memory_cache:
        val, expiry = _local_memory_cache[key]
        if expiry and time.time() > expiry:
            del _local_memory_cache[key] # Expired
            return None
        return val
    return None

def cache_delete(key: str):
    """
    Removes key from cache.
    """
    client = get_redis_client()
    if client:
        try:
            client.delete(key)
            return True
        except Exception as e:
            logger.debug(f"Redis delete failed: {e}")
            
    if key in _local_memory_cache:
        del _local_memory_cache[key]
    return True

def acquire_lock(lock_name: str, expire_seconds: int = 15) -> bool:
    """
    Acquires a mutual-exclusion lock (NX key set) to serialize crawler runs.
    """
    client = get_redis_client()
    if client:
        try:
            # Set key if not exists (NX) with expiry
            status = client.set(f"lock:{lock_name}", "locked", ex=expire_seconds, nx=True)
            return bool(status)
        except Exception as e:
            logger.debug(f"Redis lock failed: {e}")
            
    # Fallback to local memory lock
    now = time.time()
    if lock_name in _local_memory_locks:
        expiry = _local_memory_locks[lock_name]
        if now < expiry:
            return False # Locked
            
    _local_memory_locks[lock_name] = now + expire_seconds
    return True

def release_lock(lock_name: str):
    """
    Releases a lock manually.
    """
    client = get_redis_client()
    if client:
        try:
            client.delete(f"lock:{lock_name}")
            return True
        except Exception as e:
            logger.debug(f"Redis unlock failed: {e}")
            
    if lock_name in _local_memory_locks:
        del _local_memory_locks[lock_name]
    return True
