"""
utils/coupon_hunter.py
Auto-Coupon & Hidden Promo Code Intelligence Engine.
Extracts collectable coupon checkboxes, promo codes, and calculates stacked net prices.
"""

import re
from typing import Dict, Any, Tuple, Optional


def extract_coupon_discount(coupon_text: str, current_price: float) -> Tuple[float, str]:
    """
    Extracts coupon discount value (flat or percentage) and description from raw scraped coupon text.
    Returns (coupon_discount_value, coupon_description).
    """
    if not coupon_text or current_price <= 0:
        return 0.0, ""

    text = coupon_text.lower()
    
    # 1. Percentage Coupon (e.g., "Apply 10% coupon", "Save 15% with coupon")
    pct_match = re.search(r'(\d+)%\s*(?:coupon|off)', text)
    if pct_match:
        pct = float(pct_match.group(1))
        discount_val = round((current_price * pct) / 100.0, 2)
        return discount_val, f"{int(pct)}% Coupon Checkbox (-₹{int(discount_val):,})"

    # 2. Flat Rupee Coupon (e.g., "Apply ₹500 coupon", "₹100 coupon applied", "Flat 250 off")
    flat_match = re.search(r'(?:₹|rs\.?|flat)\s*([0-9,]+)\s*(?:coupon|off)', text)
    if flat_match:
        flat_val = float(flat_match.group(1).replace(",", ""))
        if flat_val < current_price:
            return flat_val, f"Flat ₹{int(flat_val):,} Coupon Checkbox"

    return 0.0, ""


def calculate_stacked_deal_pricing(
    base_price: float,
    advertised_mrp: float,
    coupon_text: Optional[str] = None,
    bank_offer_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculates final bottom-line price by stacking Base Price + Coupon Checkbox + Bank Discount.
    """
    if not base_price or base_price <= 0:
        return {
            "base_price": 0,
            "net_final_price": 0,
            "total_savings": 0,
            "coupon_discount": 0,
            "bank_discount": 0,
            "breakdown_text": "Price unavailable"
        }

    coupon_discount = 0.0
    coupon_desc = ""
    if coupon_text:
        coupon_discount, coupon_desc = extract_coupon_discount(coupon_text, base_price)

    # Bank discount parsing
    bank_discount = 0.0
    bank_desc = ""
    if bank_offer_text:
        from utils.bank_offers import extract_discount_from_offer_text
        bank_discount, bank_desc = extract_discount_from_offer_text(bank_offer_text, base_price - coupon_discount)

    net_final_price = max(1.0, base_price - coupon_discount - bank_discount)
    mrp_ref = advertised_mrp if (advertised_mrp and advertised_mrp > base_price) else base_price
    total_savings = mrp_ref - net_final_price

    breakdown_parts = [f"💰 Deal Price: ₹{int(base_price):,}"]
    if coupon_discount > 0:
        breakdown_parts.append(f"🎟️ Coupon: -₹{int(coupon_discount):,}")
    if bank_discount > 0:
        breakdown_parts.append(f"💳 Card Offer: -₹{int(bank_discount):,}")
    breakdown_parts.append(f"👉 Effective Bottom Line: ₹{int(net_final_price):,}!")

    return {
        "base_price": int(base_price),
        "mrp": int(mrp_ref),
        "coupon_discount": int(coupon_discount),
        "coupon_desc": coupon_desc,
        "bank_discount": int(bank_discount),
        "bank_desc": bank_desc,
        "net_final_price": int(net_final_price),
        "total_savings": int(total_savings),
        "breakdown_text": " | ".join(breakdown_parts)
    }
