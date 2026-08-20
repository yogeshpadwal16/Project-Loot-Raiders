"""
utils/rules_engine.py
India Free Stuff Mathematical Scoring & Deal Eligibility Engine.

Evaluates deal discount percentages, category-specific minimum thresholds,
loot/price glitch detection, seller trust ratings, and shipping traps.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("LootRulesEngine")


def infer_category(title: str = "", text: str = "") -> str:
    """Infers product category from title/text keywords."""
    combined = f"{title} {text}".lower()
    if any(k in combined for k in ["phone", "mobile", "iphone", "galaxy", "redmi", "realme", "oneplus", "smartphone", "vivo", "oppo", "poco"]):
        return "smartphones"
    if any(k in combined for k in ["laptop", "tv", "audio", "headphone", "earphone", "airpods", "watch", "electronics", "camera", "monitor"]):
        return "electronics"
    if any(k in combined for k in ["shirt", "tshirt", "jeans", "shoes", "fashion", "dress", "saree", "kurta", "wear"]):
        return "fashion"
    if any(k in combined for k in ["grocery", "food", "oil", "biscuit", "soap", "shampoo", "fmcg"]):
        return "grocery"
    return "general"


def evaluate_deal_eligibility(
    mrp: Optional[float],
    current_price: Optional[float],
    category: str = "general",
    seller_rating: float = 4.0,
    shipping_charge: float = 0.0,
    coupon_discount: float = 0.0,
    historical_avg_price: Optional[float] = None,
    title: str = ""
) -> Dict[str, Any]:
    """
    Applies the India Free Stuff mathematical scoring model to evaluate deal eligibility.

    Returns:
      Dict with keys: approved (bool), tier (str), is_loot (bool), discount_pct (float), effective_price (float), reason (str)
    """
    if current_price is None or current_price <= 0:
        logger.info("[Rules Engine] Unverified deal approved (price unlisted / title fallback mode)")
        return {
            "approved": True,
            "tier": "UNVERIFIED",
            "is_loot": False,
            "discount_pct": 0.0,
            "effective_price": 0.0,
            "reason": "Unverified price - unlisted fallback mode"
        }

    effective_price = max(0.0, current_price - coupon_discount)

    # If MRP is missing or <= effective_price, approve as Standard deal based on price alone
    if mrp is None or mrp <= effective_price:
        return {
            "approved": True,
            "tier": "STANDARD",
            "is_loot": False,
            "discount_pct": 0.0,
            "effective_price": effective_price,
            "reason": "Standard deal - MRP unlisted"
        }

    raw_discount = round(((mrp - effective_price) / mrp) * 100, 2)

    # Filter out fake / scam sellers
    if seller_rating < 3.5:
        logger.info(f"[Rules Engine] Rejected deal: Seller rating {seller_rating} < 3.5")
        return {"approved": False, "reason": f"Low seller rating ({seller_rating} < 3.5)"}

    # Filter out shipping traps (e.g. ₹20 item + ₹120 delivery)
    if effective_price > 0 and (shipping_charge / effective_price) > 0.40 and shipping_charge > 50:
        logger.info(f"[Rules Engine] Rejected deal: Shipping trap (₹{shipping_charge} on ₹{effective_price} item)")
        return {"approved": False, "reason": "High shipping charge offsets discount"}

    if category == "general" and title:
        category = infer_category(title)

    cat_lower = category.lower().strip()

    # 1. Loot / Price Glitch Rule
    if (cat_lower in ["electronics", "smartphones", "laptops", "mobile"] and raw_discount >= 50.0) or \
       (effective_price <= 99.0 and raw_discount >= 50.0) or \
       (raw_discount >= 75.0):
        logger.info(f"[Rules Engine] LOOT DEAL DETECTED! Category={cat_lower}, Discount={raw_discount}%, Price=Rs.{effective_price}")
        return {
            "approved": True,
            "tier": "LOOT_DEAL",
            "is_loot": True,
            "discount_pct": raw_discount,
            "effective_price": effective_price,
            "reason": f"Loot deal detected ({raw_discount}% OFF)"
        }

    # 2. Category Minimum Thresholds
    thresholds = {
        "smartphones": 10.0,
        "mobile": 10.0,
        "electronics": 15.0,
        "laptops": 15.0,
        "grocery": 20.0,
        "fmcg": 20.0,
        "fashion": 40.0,
        "clothing": 40.0,
        "general": 10.0
    }
    min_required = thresholds.get(cat_lower, 10.0)

    if raw_discount >= min_required:
        tier = "SUPERDEAL" if raw_discount >= 50.0 else "STANDARD"
        logger.info(f"[Rules Engine] Approved deal ({tier}): Discount={raw_discount}% >= Required={min_required}%")
        return {
            "approved": True,
            "tier": tier,
            "is_loot": False,
            "discount_pct": raw_discount,
            "effective_price": effective_price,
            "reason": f"Approved {tier} ({raw_discount}% OFF)"
        }

    logger.info(f"[Rules Engine] Rejected deal: Discount {raw_discount}% below minimum {min_required}% for category '{cat_lower}'")
    return {"approved": False, "reason": f"Discount {raw_discount}% below minimum {min_required}%"}
