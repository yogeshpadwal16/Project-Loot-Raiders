"""
deal_engine/price_war.py
Cross-Platform Flash Price War Detector.
Identifies active undercutting price battles between Amazon, Flipkart, Myntra, and Ajio.
"""

from typing import Dict, Any, Optional
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from utils.deduplicator import clean_title_for_fuzzy


def detect_flash_price_war(title: str, current_price: float, current_platform: str) -> Optional[Dict[str, Any]]:
    """
    Checks if a competing platform is locked in an active price war for this product.
    Returns details if an active price war is detected, else None.
    """
    if not title or current_price <= 0:
        return None

    cleaned_title = clean_title_for_fuzzy(title)
    if not cleaned_title:
        return None

    target_rival = "flipkart" if "amazon" in current_platform.lower() else "amazon"
    
    db = SessionLocal()
    try:
        # Query matching products on the rival platform
        rival_products = (
            db.query(Product)
            .filter(Product.platform.like(f"%{target_rival}%"))
            .order_by(Product.last_updated.desc())
            .limit(100)
            .all()
        )

        try:
            from rapidfuzz import fuzz
            scorer = fuzz.token_sort_ratio
        except ImportError:
            scorer = lambda a, b: 100 if a.lower() == b.lower() else 0

        best_match = None
        best_score = 0.0

        for rp in rival_products:
            score = scorer(cleaned_title, clean_title_for_fuzzy(rp.title or ""))
            if score > best_score and score >= 80.0:
                best_score = score
                best_match = rp

        if best_match:
            # Query latest price of matched rival product
            latest_rival_ph = (
                db.query(PriceHistory)
                .filter_by(product_id=best_match.id)
                .order_by(PriceHistory.timestamp.desc())
                .first()
            )
            if latest_rival_ph and latest_rival_ph.price > 0:
                rival_price = latest_rival_ph.price
                price_diff = abs(current_price - rival_price)
                
                # Check if prices are within 10% of each other (tight price competition)
                pct_diff = (price_diff / max(current_price, rival_price)) * 100.0
                if pct_diff <= 12.0 and price_diff > 0:
                    cheaper_platform = current_platform.capitalize() if current_price < rival_price else target_rival.capitalize()
                    savings = int(price_diff)
                    
                    return {
                        "is_price_war": True,
                        "headline": f"⚔️ ACTIVE PRICE WAR: {cheaper_platform} undercut by ₹{savings:,}!",
                        "current_platform": current_platform.capitalize(),
                        "current_price": int(current_price),
                        "rival_platform": target_rival.capitalize(),
                        "rival_price": int(rival_price),
                        "savings": savings,
                        "cheaper_platform": cheaper_platform
                    }
    except Exception:
        pass
    finally:
        db.close()

    return None
