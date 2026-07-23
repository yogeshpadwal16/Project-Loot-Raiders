import re
import logging
import time
from typing import Optional, Tuple
from rapidfuzz import fuzz
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from deal_engine.mirroring.config import SIMILARITY_THRESHOLD

def clean_text_for_comparison(text: str) -> str:
    """Removes emojis, extra whitespace, special characters, and converts to lowercase."""
    if not text:
        return ""
    # 1. Convert to lowercase
    text = text.lower()
    
    # 2. Remove emojis (any non-ASCII characters / special emojis range)
    # We remove emojis and non-alphanumeric except spaces
    text = re.sub(r'[^\w\s]', '', text)
    
    # 3. Strip extra spaces and newlines
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 4. Remove common deal verbs/keywords that inflate similarity score
    stopwords = [
        "grab", "loot", "deal", "deals", "offers", "offer", "buy", "now", "free", "shipping",
        "verified", "hot", "price", "drop", "glitch", "error", "lowest", "rs", "inr", "off"
    ]
    words = [w for w in text.split(" ") if w not in stopwords]
    return " ".join(words)

class IntelligentDeduplicator:
    @staticmethod
    def find_duplicate(title: str, current_price: int, time_window_hours: int = 24) -> Tuple[bool, Optional[str]]:
        """
        Uses RapidFuzz to find a highly similar product deals published recently.
        Returns (is_duplicate, matched_product_id).
        """
        if not title:
            return False, None
            
        clean_target = clean_text_for_comparison(title)
        if len(clean_target) < 6:
            return False, None
            
        db = SessionLocal()
        try:
            # Query recent products published in the time window
            cutoff = time.time() - (time_window_hours * 3600)
            
            # Fetch products with their latest price history timestamp
            recent_products = db.query(Product).join(PriceHistory).filter(PriceHistory.timestamp >= cutoff).all()
            
            highest_score = 0.0
            matched_id = None
            
            for p in recent_products:
                clean_candidate = clean_text_for_comparison(p.title)
                if not clean_candidate:
                    continue
                
                # We use token_sort_ratio to be order-independent (e.g. "iPhone 15 Black" vs "Black iPhone 15")
                score = fuzz.token_sort_ratio(clean_target, clean_candidate)
                
                if score > highest_score:
                    highest_score = score
                    matched_id = p.id
                    
            if highest_score >= SIMILARITY_THRESHOLD:
                # Double check price similarity or if it's the exact same deal
                # If similarity is extremely high (>95%), treat as duplicate regardless of price
                # If similarity is high (>85%) but price is significantly different, it might be a different variant
                logging.info(f"[Deduplicator] Semantic match found (Score: {highest_score:.1f}%): Target: '{title[:30]}' matched candidate ID: {matched_id}")
                return True, matched_id
                
        except Exception as e:
            logging.error(f"[Deduplicator] Duplicate detection failed: {e}")
        finally:
            db.close()
            
        return False, None
