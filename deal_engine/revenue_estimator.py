"""
deal_engine/revenue_estimator.py
Automated Profit & Affiliate Commission Revenue Estimator.
Analyzes daily link clicks, applies category commission slabs, and generates daily earnings summaries.
"""

import time
from typing import Dict, Any, List
from database.db_session import SessionLocal
from knowledge_base.models import ClickLog, PriceHistory, Product


# Standard Indian Affiliate Commission Rates by Category (Amazon Associates / EarnKaro / Cuelinks)
COMMISSION_RATES = {
    "fashion": 0.08,        # 8% (Apparel, Shoes, Watches, Bags)
    "beauty": 0.07,         # 7% (Cosmetics, Grooming, Skincare)
    "home": 0.06,           # 6% (Home & Kitchen, Furniture)
    "electronics": 0.04,    # 4% (Audio, Headphones, Accessories)
    "grocery": 0.05,        # 5% (Food, Pantry, FMCG)
    "appliances": 0.035,    # 3.5% (TV, Washing Machines, AC)
    "smartphones": 0.012,   # 1.2% (Mobiles, Tablets)
    "general": 0.04         # 4% default fallback
}

# Industry average conversion rate for high-intent discount shoppers (3.5%)
CONVERSION_RATE_ESTIMATE = 0.035


def estimate_daily_affiliate_revenue(lookback_hours: int = 24) -> Dict[str, Any]:
    """
    Computes estimated daily clicks, conversions, and commission revenue.
    """
    cutoff_time = time.time() - (lookback_hours * 3600)
    db = SessionLocal()
    
    total_clicks = 0
    estimated_orders = 0
    estimated_revenue = 0.0
    top_clicked_deals = []

    try:
        # 1. Total clicks in the last 24h
        clicks = db.query(ClickLog).filter(ClickLog.timestamp >= cutoff_time).all()
        total_clicks = len(clicks)

        # 2. Query products with high click activity
        from sqlalchemy import func
        click_summary = (
            db.query(ClickLog.product_id, func.count(ClickLog.id).label("click_count"))
            .filter(ClickLog.timestamp >= cutoff_time)
            .group_by(ClickLog.product_id)
            .order_by(func.count(ClickLog.id).desc())
            .limit(5)
            .all()
        )

        for prod_id, count in click_summary:
            prod = db.query(Product).filter_by(id=prod_id).first()
            ph = db.query(PriceHistory).filter_by(product_id=prod_id).order_by(PriceHistory.timestamp.desc()).first()
            if prod and ph:
                price = ph.price or 1000
                category = (prod.category or "general").lower()
                rate = COMMISSION_RATES.get(category, COMMISSION_RATES["general"])
                
                # Estimated earnings = clicks * conv_rate * price * commission_rate
                item_conv = max(1, int(count * CONVERSION_RATE_ESTIMATE))
                item_est_comm = item_conv * price * rate
                estimated_revenue += item_est_comm
                estimated_orders += item_conv

                top_clicked_deals.append({
                    "title": prod.title[:45] + "...",
                    "clicks": count,
                    "price": int(price),
                    "est_commission": int(item_est_comm)
                })

    except Exception:
        pass
    finally:
        db.close()

    # Fallback estimate if click tracking is fresh
    if total_clicks > 0 and estimated_revenue == 0.0:
        estimated_orders = max(1, int(total_clicks * CONVERSION_RATE_ESTIMATE))
        estimated_revenue = estimated_orders * 1500 * 0.04 # Avg order ₹1,500 at 4%

    return {
        "lookback_hours": lookback_hours,
        "total_clicks": total_clicks,
        "estimated_orders": estimated_orders,
        "estimated_revenue_inr": round(estimated_revenue, 2),
        "top_clicked_deals": top_clicked_deals,
        "summary_text": f"📊 Daily Earnings Report: {total_clicks} Clicks | ~{estimated_orders} Orders | Est. Earnings: ₹{int(estimated_revenue):,}"
    }
