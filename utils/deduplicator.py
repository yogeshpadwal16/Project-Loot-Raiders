# utils/deduplicator.py
import os
import re
import time
import logging
import threading
from typing import Tuple, Optional, Dict, Any
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from utils.semantic_dedup import find_semantic_duplicate, add_deal_vector

# Setup logging
logger = logging.getLogger("IntelligentDeduplicator")

# Thread-safe in-flight registry to prevent concurrency race conditions
IN_FLIGHT_LOCK = threading.Lock()
IN_FLIGHT_DEALS = {}  # fingerprint -> timestamp

SIMILARITY_THRESHOLD = 85.0  # token_sort_ratio threshold (0-100)
DEFAULT_TTL_SEC = 14400  # 4 hours

_ASYNC_REDIS_CLIENT: Optional[Any] = None
_IN_MEMORY_DEDUP_CACHE: Dict[str, float] = {}


async def _get_async_redis():
    """Lazy-initializes redis.asyncio Redis client connection pool."""
    global _ASYNC_REDIS_CLIENT
    if _ASYNC_REDIS_CLIENT is not None:
        return _ASYNC_REDIS_CLIENT

    redis_host = os.environ.get("REDIS_HOST", "127.0.0.1")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    redis_db = int(os.environ.get("REDIS_DB", 0))
    redis_pass = os.environ.get("REDIS_PASSWORD", None)

    try:
        import redis.asyncio as aioredis
        client = aioredis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_pass,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            decode_responses=True,
        )
        await client.ping()
        _ASYNC_REDIS_CLIENT = client
        logger.info(f"[Async Redis Deduplicator] Connected to Redis at {redis_host}:{redis_port}")
        return _ASYNC_REDIS_CLIENT
    except Exception as e:
        logger.warning(f"[Async Redis Deduplicator] Redis unavailable ({e}). Operating in-memory deduplication fallback.")
        _ASYNC_REDIS_CLIENT = None
        return None


async def is_duplicate_and_lock(canonical_key: Optional[str], ttl_seconds: int = DEFAULT_TTL_SEC) -> bool:
    """
    Non-blocking async atomic Redis lock check for canonical_key.
    Executes: redis.set(f"active_deal:{canonical_key}", "1", ex=ttl_seconds, nx=True)

    Returns:
      True  -> Duplicate found (lock key exists).
      False -> Lock acquired successfully (new unique deal!).
    """
    if not canonical_key:
        return False

    lock_key = f"active_deal:{canonical_key}"
    redis_client = await _get_async_redis()

    if redis_client:
        try:
            is_new = await redis_client.set(lock_key, "1", ex=ttl_seconds, nx=True)
            if is_new:
                logger.debug(f"[Async Redis Lock] Acquired lock for key='{lock_key}' (TTL={ttl_seconds}s)")
                return False  # Unique deal!
            else:
                logger.info(f"[Async Redis Lock] Duplicate deal suppressed for key='{lock_key}'")
                return True   # Duplicate!
        except Exception as e:
            logger.warning(f"[Async Redis Lock] Redis error ({e}). Using in-memory fallback.")

    # In-Memory Fallback Deduplication
    now = time.time()
    expired = [k for k, exp in _IN_MEMORY_DEDUP_CACHE.items() if now > exp]
    for k in expired:
        del _IN_MEMORY_DEDUP_CACHE[k]

    if lock_key in _IN_MEMORY_DEDUP_CACHE:
        if now < _IN_MEMORY_DEDUP_CACHE[lock_key]:
            logger.info(f"[In-Memory Lock] Duplicate deal suppressed for key='{lock_key}'")
            return True  # Duplicate!

    _IN_MEMORY_DEDUP_CACHE[lock_key] = now + ttl_seconds
    logger.debug(f"[In-Memory Lock] Acquired lock for key='{lock_key}' (TTL={ttl_seconds}s)")
    return False  # Unique deal!


async def release_deal_lock(canonical_key: Optional[str]) -> None:
    """Releases lock for canonical_key if deal processing failed and retry is required."""
    if not canonical_key:
        return
    lock_key = f"active_deal:{canonical_key}"
    redis_client = await _get_async_redis()
    if redis_client:
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass
    if lock_key in _IN_MEMORY_DEDUP_CACHE:
        del _IN_MEMORY_DEDUP_CACHE[lock_key]


def get_canonical_url(url: str) -> str:
    """Normalizes URL by stripping query parameters, anchors, and tracking codes."""
    if not url:
        return ""
    # Strip queries/anchors
    url = url.split("?")[0].split("#")[0].strip().rstrip("/")
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url

def extract_asin_or_pid(url: str, text: str = "") -> Tuple[Optional[str], Optional[str]]:
    """Extracts Amazon ASIN or Flipkart PID from URL paths or text content."""
    if not url:
        url = ""
    # Amazon ASIN
    if "amazon" in url.lower():
        match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
        if match:
            return "amazon", match.group(1)
    # Flipkart PID
    elif "flipkart" in url.lower():
        match = re.search(r'pid=([a-zA-Z0-9]{16})', url)
        if match:
            return "flipkart", match.group(1)
        match_p = re.search(r'/p/([a-zA-Z0-9]{16})', url)
        if match_p:
            return "flipkart", match_p.group(1)
            
    # Try from text search
    if "amazon.in" in text.lower() or "amzn.to" in text.lower():
        match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', text)
        if match:
            return "amazon", match.group(1)
            
    return None, None

def clean_title_for_fuzzy(text: str) -> str:
    """Preprocesses and sorts title tokens to guarantee order-independent text comparisons."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    stopwords = {
        "grab", "loot", "deal", "deals", "offers", "offer", "buy", "now", "free", "shipping",
        "verified", "hot", "price", "drop", "glitch", "error", "lowest", "rs", "inr", "off",
        "pack", "of", "for", "with", "and", "the", "in", "on", "at", "a", "an"
    }
    words = [w for w in text.split(" ") if w not in stopwords and w]
    words.sort()
    return " ".join(words)

def find_duplicate_deal(
    title: str,
    price: int,
    platform: str,
    url: str,
    text: str = "",
    time_window_hours: int = 24
) -> Tuple[bool, Optional[str]]:
    """
    Core thread-safe duplicate checking engine using multiple signals.
    """
    if not title:
        return False, None
        
    canon_url = get_canonical_url(url)
    plat, pid = extract_asin_or_pid(url, text)
    if not plat and platform:
        plat = platform.lower()
        
    fingerprints = []
    if plat and pid:
        fingerprints.append(f"ID:{plat.upper()}:{pid}")
    if canon_url:
        fingerprints.append(f"URL:{canon_url}")
        
    cleaned_title = clean_title_for_fuzzy(title)
    if cleaned_title:
        fingerprints.append(f"TITLE:{cleaned_title}_{price}")
        
    now = time.time()
    with IN_FLIGHT_LOCK:
        expired = [f for f, ts in IN_FLIGHT_DEALS.items() if now - ts > 300]
        for f in expired:
            del IN_FLIGHT_DEALS[f]
            
        for f in fingerprints:
            if f in IN_FLIGHT_DEALS:
                logger.info(f"Concurrency lock hit: fingerprint '{f}' is already processing in another thread.")
                return True, "in-flight"
                
        for f in fingerprints:
            IN_FLIGHT_DEALS[f] = now
            
    try:
        matched_id = find_semantic_duplicate(title=title, price=price, threshold=SIMILARITY_THRESHOLD / 100.0)
        if matched_id:
            logger.info(f"ChromaDB semantic duplicate match: '{title[:30]}' mapped to {matched_id}")
            return True, matched_id
    except Exception as sem_err:
        logger.error(f"ChromaDB semantic duplicate check failed: {sem_err}")

    db = SessionLocal()
    try:
        if plat and pid:
            prod = db.query(Product).filter_by(id=pid).first()
            if not prod:
                prod = db.query(Product).filter(Product.id.like(f"%{pid}%")).first()
            if prod:
                logger.info(f"DB duplicate match by ID: {prod.id} ('{title[:30]}')")
                return True, prod.id
                
        if canon_url:
            prod = db.query(Product).filter(Product.url.like(f"%{canon_url}%")).first()
            if prod:
                logger.info(f"DB duplicate match by canonical URL: {prod.id} ('{title[:30]}')")
                return True, prod.id
                
        cutoff = time.time() - (time_window_hours * 3600)
        recent_products = db.query(Product).join(PriceHistory).filter(PriceHistory.timestamp >= cutoff).all()
        
        try:
            from rapidfuzz import fuzz
            use_rapidfuzz = True
        except ImportError:
            import difflib
            use_rapidfuzz = False
            
        for p in recent_products:
            clean_cand = clean_title_for_fuzzy(p.title)
            if not clean_cand:
                continue
                
            if use_rapidfuzz:
                score = fuzz.token_sort_ratio(cleaned_title, clean_cand)
            else:
                score = difflib.SequenceMatcher(None, cleaned_title, clean_cand).ratio() * 100
                
            if score >= SIMILARITY_THRESHOLD:
                latest = db.query(PriceHistory).filter_by(product_id=p.id).order_by(PriceHistory.timestamp.desc()).first()
                if latest and latest.price == price:
                    logger.info(f"DB duplicate fuzzy match: '{p.title[:30]}' (Score: {score:.1f}%) at same price ₹{price}")
                    return True, p.id
    except Exception as e:
        logger.error(f"Error querying SQLite database in deduplicator: {e}")
    finally:
        db.close()
        
    return False, None

def release_in_flight_deal(title: str, platform: str, url: str):
    """Releases active processing locks if a deal is skipped by filters."""
    canon_url = get_canonical_url(url)
    plat, pid = extract_asin_or_pid(url)
    if not plat and platform:
        plat = platform.lower()
        
    fingerprints = []
    if plat and pid:
        fingerprints.append(f"ID:{plat.upper()}:{pid}")
    if canon_url:
        fingerprints.append(f"URL:{canon_url}")
        
    cleaned_title = clean_title_for_fuzzy(title)
    
    with IN_FLIGHT_LOCK:
        for f in fingerprints:
            if f in IN_FLIGHT_DEALS:
                del IN_FLIGHT_DEALS[f]
        keys_to_del = [k for k in IN_FLIGHT_DEALS.keys() if cleaned_title and k.startswith(f"TITLE:{cleaned_title}")]
        for k in keys_to_del:
            del IN_FLIGHT_DEALS[k]

# =====================================================================
# BACKWARDS COMPATIBILITY INTERFACE (FOR core/engine.py & operations.py)
# =====================================================================
MOCKED_VECTOR_DB = {}

def find_similar_product(title: str, distance_threshold: float = 0.15) -> Optional[str]:
    """Fallback compatibility method mapping directly to our fast fuzzy matcher."""
    try:
        matched_id = find_semantic_duplicate(title=title, price=0, threshold=1.0 - distance_threshold)
        if matched_id:
            logger.info(f"ChromaDB similar product match: {matched_id} ('{title[:30]}')")
            return matched_id
    except Exception as sem_err:
        logger.error(f"Persistent vector DB lookup failed: {sem_err}")

    cleaned_title = clean_title_for_fuzzy(title)
    if not cleaned_title:
        return None
        
    try:
        from rapidfuzz import fuzz
        use_rapidfuzz = True
    except ImportError:
        import difflib
        use_rapidfuzz = False
        
    for pid, ptitle in list(MOCKED_VECTOR_DB.items()):
        clean_cand = clean_title_for_fuzzy(ptitle)
        if not clean_cand:
            continue
        if use_rapidfuzz:
            score = fuzz.token_sort_ratio(cleaned_title, clean_cand)
        else:
            score = difflib.SequenceMatcher(None, cleaned_title, clean_cand).ratio() * 100
        if score >= 90.0:
            return pid
            
    db = SessionLocal()
    try:
        recent_products = db.query(Product).order_by(Product.created_at.desc()).limit(200).all()
        for p in recent_products:
            clean_cand = clean_title_for_fuzzy(p.title)
            if not clean_cand:
                continue
            if use_rapidfuzz:
                score = fuzz.token_sort_ratio(cleaned_title, clean_cand)
            else:
                score = difflib.SequenceMatcher(None, cleaned_title, clean_cand).ratio() * 100
            if score >= 90.0:
                return p.id
    except Exception as e:
        logger.error(f"Backcompat similar search error: {e}")
    finally:
        db.close()
    return None

def add_product_to_vector_db(product_id: str, title: str) -> bool:
    """Mock index a product in memory to prevent nested transaction write locks during active DB flushes."""
    MOCKED_VECTOR_DB[product_id] = title
    logger.info(f"Mock-indexed product '{product_id}' -> '{title[:30]}' in memory.")
    try:
        add_deal_vector(product_id=product_id, title=title, price=0)
    except Exception as index_err:
        logger.error(f"Failed to add product to persistent vector DB: {index_err}")
    return True

def is_genuine_loot_deal(product_id: str, title: str, price: int, mrp: int, discount: float, db) -> Tuple[bool, str]:
    """
    Evaluates whether a candidate deal discovered by the Loot Scraper is a genuine,
    value-adding loot deal, or if it is a spammy recurring listing that should be suppressed.
    """
    real_pid = product_id
    similar_id = find_similar_product(title)
    if similar_id:
        real_pid = similar_id

    history_entries = db.query(PriceHistory).filter_by(product_id=real_pid).order_by(PriceHistory.timestamp.desc()).all()
    
    if not history_entries:
        recent_prods = db.query(Product).order_by(Product.created_at.desc()).limit(300).all()
        cleaned_title = clean_title_for_fuzzy(title)
        
        try:
            from rapidfuzz import fuzz
            use_rapidfuzz = True
        except ImportError:
            import difflib
            use_rapidfuzz = False
            
        matched_pid = None
        for p in recent_prods:
            clean_cand = clean_title_for_fuzzy(p.title)
            if not clean_cand:
                continue
            if use_rapidfuzz:
                score = fuzz.token_sort_ratio(cleaned_title, clean_cand)
            else:
                score = difflib.SequenceMatcher(None, cleaned_title, clean_cand).ratio() * 100
            if score >= 90.0:
                matched_pid = p.id
                break
        
        if matched_pid:
            history_entries = db.query(PriceHistory).filter_by(product_id=matched_pid).order_by(PriceHistory.timestamp.desc()).all()
            real_pid = matched_pid

    now = time.time()
    history_entries = [h for h in history_entries if (now - h.timestamp) > 10.0]

    if not history_entries:
        return True, "new_product"

    latest_entry = history_entries[0]
    
    time_since_last_post = now - latest_entry.timestamp
    if time_since_last_post < 43200: # 12 hours
        price_drop_pct = ((latest_entry.price - price) / latest_entry.price) * 100.0 if latest_entry.price > 0 else 0.0
        if price_drop_pct < 15.0:
            return False, f"suppressed: posted recently ({time_since_last_post/3600:.2f}h ago) and price change too small ({price_drop_pct:.1f}%)"
            
    last_24h_posts = [h for h in history_entries if now - h.timestamp < 86400]
    if len(last_24h_posts) >= 3:
        return False, f"suppressed: daily post limit reached ({len(last_24h_posts)} posts in 24h)"

    last_7d_posts = [h for h in history_entries if now - h.timestamp < 7 * 86400]
    if len(last_7d_posts) >= 5:
        min_historical_price = min(h.price for h in history_entries)
        if price >= min_historical_price:
            return False, f"suppressed: recurring listing (posted {len(last_7d_posts)} times in 7d at or above historical low ₹{min_historical_price})"

    if price >= latest_entry.price:
        return False, f"suppressed: price is same or higher than last post (₹{price} >= ₹{latest_entry.price})"

    return True, "approved"
