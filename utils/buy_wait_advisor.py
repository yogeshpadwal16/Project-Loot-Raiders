"""
utils/buy_wait_advisor.py
Keepa-Style 'Buy vs Wait' AI Advisor & Price History Trend Intelligence.
Analyzes price volatility to advise buyers on the optimal time to purchase.
"""

from typing import Dict, Any, List, Optional
from database.db_session import SessionLocal
from knowledge_base.models import PriceHistory
import time


def get_buy_vs_wait_recommendation(product_id: str, current_price: float) -> Dict[str, Any]:
    """
    Computes an instant Buy vs. Wait verdict based on price trends.
    """
    if not current_price or current_price <= 0:
        return {
            "verdict": "BUY_NOW",
            "verdict_badge": "🎯 VERDICT: BUY NOW",
            "reason": "Special price detected.",
            "lowest_all_time": int(current_price or 0),
            "highest_all_time": int(current_price or 0)
        }

    db = SessionLocal()
    try:
        history = (
            db.query(PriceHistory.price, PriceHistory.timestamp)
            .filter(PriceHistory.product_id == product_id)
            .order_by(PriceHistory.timestamp.asc())
            .all()
        )
        prices = [p[0] for p in history if p[0] and p[0] > 0]
    except Exception:
        prices = []
    finally:
        db.close()

    if not prices or len(prices) < 2:
        return {
            "verdict": "BUY_NOW",
            "verdict_badge": "🎯 VERDICT: BUY NOW",
            "reason": "Freshly discovered deal at low price.",
            "lowest_all_time": int(current_price),
            "highest_all_time": int(current_price)
        }

    lowest_price = min(prices)
    highest_price = max(prices)
    avg_price = sum(prices) / len(prices)

    # 1. All-time low
    if current_price <= lowest_price:
        return {
            "verdict": "BUY_NOW",
            "verdict_badge": "🎯 VERDICT: BUY NOW (All-Time Lowest Price!)",
            "reason": f"Lowest price recorded across all historical scans (Prev Low: ₹{lowest_price:,}).",
            "lowest_all_time": int(lowest_price),
            "highest_all_time": int(highest_price),
            "avg_price": int(avg_price)
        }

    # 2. Great deal (within 5% of lowest price or >25% below average)
    if current_price <= (lowest_price * 1.05) or current_price <= (avg_price * 0.75):
        return {
            "verdict": "GREAT_PRICE",
            "verdict_badge": "🔥 VERDICT: GREAT PRICE (Near All-Time Low)",
            "reason": f"Within 5% of historical lowest price of ₹{lowest_price:,}.",
            "lowest_all_time": int(lowest_price),
            "highest_all_time": int(highest_price),
            "avg_price": int(avg_price)
        }

    # 3. Wait for sale (substantially higher than lowest price and drops frequently)
    if current_price > (lowest_price * 1.25):
        diff = int(current_price - lowest_price)
        return {
            "verdict": "WAIT_FOR_SALE",
            "verdict_badge": "⏳ VERDICT: WAIT (Price Drops Periodically)",
            "reason": f"Historical low is ₹{lowest_price:,} (Save ₹{diff:,} by waiting for upcoming sale).",
            "lowest_all_time": int(lowest_price),
            "highest_all_time": int(highest_price),
            "avg_price": int(avg_price)
        }

    return {
        "verdict": "FAIR_PRICE",
        "verdict_badge": "⚖️ VERDICT: FAIR PRICE",
        "reason": f"Trading within regular historical range (₹{lowest_price:,} - ₹{highest_price:,}).",
        "lowest_all_time": int(lowest_price),
        "highest_all_time": int(highest_price),
        "avg_price": int(avg_price)
    }
