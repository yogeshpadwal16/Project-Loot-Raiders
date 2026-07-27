# utils/deduplicator.py
import os
import re
import time
import logging
import threading
from typing import Tuple, Optional
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory

# Setup logging
logger = logging.getLogger("IntelligentDeduplicator")

# Thread-safe in-flight registry to prevent concurrency race conditions
IN_FLIGHT_LOCK = threading.Lock()
IN_FLIGHT_DEALS = {}  # fingerprint -> timestamp

SIMILARITY_THRESHOLD = 85.0  # token_sort_ratio threshold (0-100)

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
    # Remove non-alphanumeric characters except spaces
    text = re.sub(r'[^\w\s]', '', text)
    # Strip double spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Filter stopwords and common deal words that distort fuzzy match ratios
    stopwords = {
        "grab", "loot", "deal", "deals", "offers", "offer", "buy", "now", "free", "shipping",
        "verified", "hot", "price", "drop", "glitch", "error", "lowest", "rs", "inr", "off",
        "pack", "of", "for", "with", "and", "the", "in", "on", "at", "a", "an"
    }
    words = [w for w in text.split(" ") if w not in stopwords and w]
    words.sort()  # Alphabetical sorting ensures order independence
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
    Core thread-safe duplicate checking engine using multiple signals:
    - In-flight registry collision (prevents race condition between parallel threads).
    - Database check by unique ASIN/PID.
    - Database check by canonical product URL.
    - Fuzzy title similarity comparison against recently logged price entries.
    """
    if not title:
        return False, None
        
    canon_url = get_canonical_url(url)
    plat, pid = extract_asin_or_pid(url, text)
    if not plat and platform:
        plat = platform.lower()
        
    # Generate signals for in-flight check
    fingerprints = []
    if plat and pid:
        fingerprints.append(f"ID:{plat.upper()}:{pid}")
    if canon_url:
        fingerprints.append(f"URL:{canon_url}")
        
    cleaned_title = clean_title_for_fuzzy(title)
    if cleaned_title:
        # Title + Price combo prevents identical deal reposts at same price
        fingerprints.append(f"TITLE:{cleaned_title}_{price}")
        
    # 1. Validate against In-Flight Deals (Concurrency Lock)
    now = time.time()
    with IN_FLIGHT_LOCK:
        # Clean in-flight deals older than 5 minutes
        expired = [f for f, ts in IN_FLIGHT_DEALS.items() if now - ts > 300]
        for f in expired:
            del IN_FLIGHT_DEALS[f]
            
        for f in fingerprints:
            if f in IN_FLIGHT_DEALS:
                logger.info(f"Concurrency lock hit: fingerprint '{f}' is already processing in another thread.")
                return True, "in-flight"
                
        # Lock these signals for 5 minutes
        for f in fingerprints:
            IN_FLIGHT_DEALS[f] = now
            
    # 2. Query SQLite Database
    db = SessionLocal()
    try:
        # Check by Unique ID (ASIN / PID)
        if plat and pid:
            prod = db.query(Product).filter_by(id=pid).first()
            if not prod:
                prod = db.query(Product).filter(Product.id.like(f"%{pid}%")).first()
            if prod:
                logger.info(f"DB duplicate match by ID: {prod.id} ('{title[:30]}')")
                return True, prod.id
                
        # Check by Canonical URL
        if canon_url:
            prod = db.query(Product).filter(Product.url.like(f"%{canon_url}%")).first()
            if prod:
                logger.info(f"DB duplicate match by canonical URL: {prod.id} ('{title[:30]}')")
                return True, prod.id
                
        # Check by Fuzzy Title + Identical Price
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
                # Fetch latest price history to see if price is identical
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
        # Clean title matches
        keys_to_del = [k for k in IN_FLIGHT_DEALS.keys() if cleaned_title and k.startswith(f"TITLE:{cleaned_title}")]
        for k in keys_to_del:
            del IN_FLIGHT_DEALS[k]

# =====================================================================
# BACKWARDS COMPATIBILITY INTERFACE (FOR core/engine.py & operations.py)
# =====================================================================
MOCKED_VECTOR_DB = {}

def find_similar_product(title: str, distance_threshold: float = 0.15) -> Optional[str]:
    """Fallback compatibility method mapping directly to our fast fuzzy matcher."""
    cleaned_title = clean_title_for_fuzzy(title)
    if not cleaned_title:
        return None
        
    try:
        from rapidfuzz import fuzz
        use_rapidfuzz = True
    except ImportError:
        import difflib
        use_rapidfuzz = False
        
    # 1. Search in-memory mocked vector DB first (for unit test compatibility)
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
            
    # 2. Fall back to querying recent SQLite products
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
    return True
