"""
utils/price_truth.py
Fake Discount & Inflated MRP Hunter Engine.
Audits advertised discounts against 90-day price history database to detect inflated list prices.
"""

from typing import Dict, Any, List, Optional
from database.db_session import SessionLocal
from knowledge_base.models import PriceHistory
import time


def analyze_price_truth(product_id: str, current_price: float, advertised_mrp: float) -> Dict[str, Any]:
    """
    Evaluates whether a deal has genuine savings vs. an artificially inflated MRP.
    Returns structured truth metrics and display badges.
    """
    if not current_price or current_price <= 0:
        return {
            "status": "UNKNOWN",
            "badge_text": "Price Unavailable",
            "real_discount_pct": 0.0,
            "is_inflated_mrp": False,
            "avg_price_90d": 0,
            "real_savings": 0
        }

    db = SessionLocal()
    try:
        cutoff_90d = time.time() - (90 * 86400)
        history = (
            db.query(PriceHistory.price)
            .filter(PriceHistory.product_id == product_id, PriceHistory.timestamp >= cutoff_90d)
            .all()
        )
        prices = [p[0] for p in history if p[0] and p[0] > 0]
    except Exception:
        prices = []
    finally:
        db.close()

    # If no 90-day historical data, evaluate based on basic price vs MRP ratio
    if not prices or len(prices) < 2:
        advertised_disc = round(((advertised_mrp - current_price) / advertised_mrp) * 100, 1) if (advertised_mrp and advertised_mrp > current_price) else 0.0
        return {
            "status": "VERIFIED" if advertised_disc >= 20 else "REGULAR",
            "badge_text": f"🔥 {advertised_disc:.0f}% Off MRP" if advertised_disc > 0 else "Standard Price",
            "real_discount_pct": advertised_disc,
            "is_inflated_mrp": False,
            "avg_price_90d": int(current_price),
            "real_savings": int(advertised_mrp - current_price) if advertised_mrp > current_price else 0
        }

    avg_price_90d = sum(prices) / len(prices)
    lowest_90d = min(prices)
    highest_90d = max(prices)

    # Real discount vs average selling price
    real_savings = avg_price_90d - current_price
    real_discount_pct = round((real_savings / avg_price_90d) * 100, 1) if avg_price_90d > 0 else 0.0

    # Inflated MRP Check: Did the seller advertise an MRP substantially higher than highest recorded selling price?
    is_inflated = bool(advertised_mrp and advertised_mrp > (highest_90d * 1.35))

    if real_discount_pct >= 20 or current_price <= lowest_90d:
        status = "GENUINE_LOOT"
        badge_text = f"✅ TRUE DEAL: Save ₹{int(real_savings):,} vs 90-day avg (₹{int(avg_price_90d):,})"
    elif is_inflated:
        status = "INFLATED_MRP"
        badge_text = f"⚠️ INFLATED MRP: Real savings are {max(0, real_discount_pct):.0f}% vs historical avg"
    elif real_discount_pct > 5:
        status = "MODERATE_DISCOUNT"
        badge_text = f"📉 {real_discount_pct:.0f}% below 90-day average"
    else:
        status = "REGULAR_PRICE"
        badge_text = "ℹ️ Regular ongoing price"

    return {
        "status": status,
        "badge_text": badge_text,
        "real_discount_pct": max(0.0, real_discount_pct),
        "is_inflated_mrp": is_inflated,
        "avg_price_90d": int(avg_price_90d),
        "lowest_90d": int(lowest_90d),
        "highest_90d": int(highest_90d),
        "real_savings": max(0, int(real_savings))
    }
