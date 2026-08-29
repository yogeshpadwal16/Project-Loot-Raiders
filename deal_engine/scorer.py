import os
import re
import json
import logging
import requests
from config.settings import load_settings
from database.db_session import SessionLocal
from knowledge_base.models import ClickLog, Product, PriceHistory

from collections import OrderedDict

class _LRUCache:
    """Simple LRU cache with max size to prevent unbounded memory growth."""
    def __init__(self, maxsize=500):
        self._cache = OrderedDict()
        self._maxsize = maxsize
    def get(self, key):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None
    def set(self, key, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

_ai_score_cache = _LRUCache(maxsize=500)

def get_predictive_buying_advice(product_id: str, current_price: int) -> dict:
    """
    Predictive Price Intelligence Engine (PPIE).
    Calculates statistical price trends over tracked historical prices
    to generate actionable buying advice and confidence scores.
    """
    if not product_id:
        return {"action": "BUY_NOW", "badge": "🔥 STEAL DEAL", "confidence": 85, "reason": "High discount deal detected."}
        
    db = SessionLocal()
    try:
        hist = db.query(PriceHistory.price).filter_by(product_id=product_id).order_by(PriceHistory.timestamp.asc()).all()
        if not hist or len(hist) < 2:
            return {"action": "BUY_NOW", "badge": "⚡ HOT LOOT", "confidence": 80, "reason": "Fresh price drop."}
            
        prices = [h[0] for h in hist if h[0] > 0]
        if not prices:
            return {"action": "BUY_NOW", "badge": "⚡ HOT LOOT", "confidence": 80, "reason": "Fresh price drop."}
            
        min_p = min(prices)
        max_p = max(prices)
        avg_p = sum(prices) / len(prices)
        
        if current_price <= min_p:
            confidence = min(99, 90 + len(prices))
            return {
                "action": "BUY_NOW_LOWEST",
                "badge": "🏆 ALL-TIME RECORD LOW",
                "confidence": confidence,
                "reason": f"Lowest price recorded across {len(prices)} historical checks!"
            }
        elif current_price <= (avg_p * 0.8):
            drop_pct = int(((avg_p - current_price) / avg_p) * 100)
            return {
                "action": "BUY_NOW_STEAL",
                "badge": f"🚀 {drop_pct}% BELOW AVERAGE",
                "confidence": 92,
                "reason": f"Priced ₹{int(avg_p - current_price):,} below historical average (₹{int(avg_p):,})."
            }
        elif current_price >= max_p:
            return {
                "action": "WAIT_PRICE_HIGH",
                "badge": "⏰ PRICE NEAR PEAK",
                "confidence": 75,
                "reason": "Current price is near peak. Price drop expected soon."
            }
        else:
            return {
                "action": "BUY_NOW_GOOD",
                "badge": "🎯 GOOD VALUE",
                "confidence": 85,
                "reason": f"Priced lower than average (₹{int(avg_p):,})."
            }
    except Exception as e:
        logging.error(f"Error in predictive buying advice: {e}")
        return {"action": "BUY_NOW", "badge": "🔥 STEAL DEAL", "confidence": 80, "reason": "High-rated loot deal."}
    finally:
        db.close()

def get_gemini_ai_desirability_score(title: str, price: int, mrp: int, discount: float, platform: str) -> float:
    """
    Uses OmniRoute to rank deal desirability from 0-100.

    OmniRoute handles provider/model routing and fallback through the
    Loot-Raiders combo. The function name is retained for compatibility
    with existing callers.
    """
    settings = load_settings()

    base_url = settings.get(
        "omniroute_base_url",
        "http://localhost:20128/v1"
    ).rstrip("/")

    api_key = settings.get("omniroute_api_key", "")
    model = settings.get("omniroute_model", "Loot-Raiders")

    if not api_key:
        logging.warning(
            "OmniRoute API key is not configured; skipping AI desirability score."
        )
        return None

    prompt = f"""
You are the deal intelligence evaluator for an Indian ecommerce loot-deals service.

Judge whether this is genuinely an unusually good buying opportunity.

Product: {title}
Platform: {platform}
Selling price: INR {price}
Listed MRP: INR {mrp}
Advertised discount: {discount}%

IMPORTANT SCORING RULES:

1. Do NOT assume a large advertised discount means a great deal.
   Ecommerce MRPs are frequently inflated.

2. Judge the selling price against the likely real-world market value of
   this type of product.

3. Consider product desirability, brand reputation, category, selling
   price, realistic savings, and whether the price looks unusually low.

4. Generic accessories and low-value products such as USB cables,
   charging cables, cases, covers, screen protectors, holders, straps,
   pouches, keychains and similar items should normally score below 35,
   even when their advertised discount is very high.

5. A popular branded product at a genuinely exceptional price can score
   80-95.

6. Scores above 95 should be extremely rare and reserved for obvious
   pricing errors, glitches, or extraordinary historically-low prices.

7. An ordinary sale price should score around 40-60.

8. A weak, misleading, overpriced, or low-value deal should score 0-35.

Score from 0.0 to 100.0.

Respond with ONLY the numeric score.
Example: 72.5
"""

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 256,
        "stream": False
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        score_text = data["choices"][0]["message"]["content"].strip()

        match = re.search(r'\d+(?:\.\d+)?', score_text)
        if not match:
            logging.warning(
                f"OmniRoute returned an invalid desirability score: {score_text!r}"
            )
            return None

        score = float(match.group(0))
        return max(0.0, min(100.0, score))

    except requests.RequestException as e:
        logging.error(f"OmniRoute AI desirability request failed: {e}")
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as e:
        logging.error(f"Invalid OmniRoute AI desirability response: {e}")
    except Exception as e:
        logging.error(f"Unexpected OmniRoute AI desirability error: {e}")

    return None

def _matches_brand(brand: str, text_lower: str) -> bool:
    """Matches a brand or keyword against text ensuring whole-word boundary and optional plural matching."""
    if not text_lower or not brand:
        return False
    pattern = r'\b' + re.escape(brand) + r'(?:s|es)?\b'
    return bool(re.search(pattern, text_lower, re.IGNORECASE))

def get_heuristic_ai_ranking(
    title: str,
    platform: str,
    price: int,
    mrp: int,
    discount: float,
    is_verified_low: bool,
    product_id: str = None
) -> float:
    """
    Heuristic-based product desirability scorer (0-100).
    Evaluates product category, brand tier, and price-band desirability.
    Does NOT include deal-quality signals (discount, history, absolute savings)
    which are scored independently in calculate_deal_score().
    """
    if not title:
        return None
        
    cache_key = (product_id, title, price, platform)
    cached = _ai_score_cache.get(cache_key)
    if cached is not None:
        return cached
    
    title_lower = title.lower()
    score = 50.0  # Base score
    
    # 1. Low-value accessory check & penalty
    LOW_VALUE_CATEGORIES = {
        "cable": -20, "adapter": -15, "charger cable": -15, "otg": -15,
        "case": -15, "cover": -15, "back cover": -18, "tempered glass": -18,
        "screen protector": -18, "screen guard": -18, "protector": -15,
        "keychain": -25, "sticker": -25, "decal": -25,
        "holder": -15, "stand": -12, "mount": -10,
        "pouch": -15, "strap": -15, "band": -10,
        "pen": -12, "pencil": -12, "eraser": -18, "notebook": -10,
        "socks": -12, "handkerchief": -18, "napkin": -18,
    }
    
    is_accessory = False
    accessory_penalty = 0
    for keyword, penalty in LOW_VALUE_CATEGORIES.items():
        if _matches_brand(keyword, title_lower):
            is_accessory = True
            accessory_penalty = min(accessory_penalty, penalty)
            
    if is_accessory:
        score += accessory_penalty
    else:
        # Category desirability scoring for primary products
        HIGH_VALUE_CATEGORIES = {
            "laptop": 25, "macbook": 28, "smartphone": 22, "phone": 22, "iphone": 28,
            "tablet": 20, "ipad": 25, "monitor": 18, "television": 18, "tv": 18,
            "headphone": 15, "earphone": 12, "earbuds": 12, "airpods": 20,
            "watch": 15, "smartwatch": 15, "camera": 20, "lens": 15,
            "processor": 18, "gpu": 20, "graphics card": 22, "ssd": 14, "ram": 12,
            "washing machine": 16, "refrigerator": 16, "air conditioner": 18, "ac": 18,
            "microwave": 12, "vacuum": 14, "robot vacuum": 16,
            "speaker": 12, "soundbar": 14, "projector": 16,
            "console": 20, "playstation": 22, "xbox": 22, "nintendo": 20,
            "trimmer": 8, "shaver": 8, "grooming": 6,
            "shoe": 10, "sneaker": 12, "running shoe": 10, "footwear": 10, "slide": 8, "sandal": 8, "sportstyle": 10,
            "backpack": 6, "luggage": 8, "suitcase": 8, "wallet": 8, "leather wallet": 10, "handbag": 8,
            "perfume": 8, "fragrance": 8, "sunglasses": 8,
            "jacket": 8, "hoodie": 6, "jeans": 6, "shirt": 4, "t-shirt": 3,
            "kurta": 4, "saree": 5, "dress": 6,
        }
        category_bonus = 0
        for keyword, bonus in HIGH_VALUE_CATEGORIES.items():
            if _matches_brand(keyword, title_lower):
                category_bonus = max(category_bonus, bonus)
        score += category_bonus
    
    # 2. Brand tier scoring
    FLAGSHIP_BRANDS = [
        "apple", "samsung", "sony", "bose", "dyson", "lg", "dell", "hp",
        "lenovo", "asus", "acer", "msi", "nike", "adidas", "puma", "reebok",
        "new balance", "asics", "sennheiser", "marshall", "bosch", "whirlpool"
    ]
    MID_POPULAR_BRANDS = [
        "boat", "jbl", "oneplus", "nothing", "realme", "redmi", "xiaomi",
        "philips", "godrej", "havells", "levi", "us polo", "tommy hilfiger", "calvin klein"
    ]
    BUDGET_GENERIC_BRANDS = [
        "generic", "local", "unbranded", "no brand"
    ]
    
    brand_score = 0
    if not (is_accessory and any(_matches_brand(b, title_lower) for b in BUDGET_GENERIC_BRANDS)):
        for brand in FLAGSHIP_BRANDS:
            if _matches_brand(brand, title_lower):
                brand_score = 8
                break
        if brand_score == 0:
            for brand in MID_POPULAR_BRANDS:
                if _matches_brand(brand, title_lower):
                    brand_score = 4
                    break
    for brand in BUDGET_GENERIC_BRANDS:
        if _matches_brand(brand, title_lower):
            brand_score = -12
            break
    score += brand_score
    
    # 3. Price-band / mass-market desirability
    if 500 <= price <= 5000:
        score += 5   # Mass-market sweet spot
    elif 5000 < price <= 50000:
        score += 5   # Mid-to-high aspirational range
    elif price > 50000:
        score += 3   # Ultra premium
    elif price < 200:
        score -= 10  # Very cheap = likely low quality/junk
    
    # Clamp to 0-100
    score = max(0.0, min(100.0, score))
    
    reason = f"Heuristic: is_accessory={is_accessory}, brand_score={brand_score:+d}"
    logging.info(f"[AI Ranker] Heuristic Score -> {score:.0f}, {reason} for: {title[:40]}...")
    
    _ai_score_cache.set(cache_key, score)
    return score

# =====================================================================
# Phase 6D: Commercial Deal Intelligence Engine v2 (DIE v2) Constants
# =====================================================================
DEFAULT_CATEGORY_COMMISSION_RATES = {
    "fashion": 0.090,      # Apparel, Footwear, Fashion Accessories
    "beauty": 0.070,       # Cosmetics, Perfume, Personal Care
    "home": 0.060,         # Home Decor, Kitchen, Furniture
    "grocery": 0.050,      # Food, FMCG, Staples
    "electronics": 0.045,  # Audio, Headphones, Cameras, Components
    "appliances": 0.035,   # Large Appliances, ACs, Washing Machines
    "laptops": 0.030,      # Laptops, Desktops, Tablets
    "smartphones": 0.015,  # Mobile Phones
    "general": 0.040       # Default fallback rate
}

DIE_V2_WEIGHTS = {
    "discount": 0.25,
    "savings": 0.15,
    "history": 0.20,
    "ai_ranking": 0.20,
    "commercial_yield": 0.10,
    "urgency": 0.05,
    "trust": 0.05
}

def calculate_die_v2_breakdown(
    platform: str, 
    price: int, 
    mrp: int, 
    discount: float, 
    is_verified_low: bool,
    is_lightning: bool = False,
    product_id: str = None,
    title: str = None,
    rating: float = None,
    reviews: int = None,
    has_bank_offer: bool = False,
    qualified_clicks: int = None,
    category: str = None
) -> dict:
    """
    Computes a comprehensive component breakdown of the Commercial Deal Intelligence v2 score.
    Returns dictionary with component scores, modifiers, kappa_mrp attenuation, and final score.
    """
    # 0. Defensive input sanitization
    try:
        price = float(price or 0.0)
    except (ValueError, TypeError):
        price = 0.0

    try:
        mrp = float(mrp or price)
    except (ValueError, TypeError):
        mrp = price

    if mrp < price or mrp <= 0.0:
        mrp = max(price, 0.0)

    try:
        discount = float(discount or 0.0)
    except (ValueError, TypeError):
        discount = 0.0

    if mrp > 0.0 and price > 0.0 and discount <= 0.0 and mrp > price:
        discount = ((mrp - price) / mrp) * 100.0

    title_str = str(title or "")
    title_lower = title_str.lower()
    platform_str = str(platform or "generic").lower()

    # 1. Resolve Category & Commission
    if not category:
        from utils.rules_engine import infer_category
        category = infer_category(title=title_str)

    comm_rate = DEFAULT_CATEGORY_COMMISSION_RATES.get(category, 0.040)
    expected_commission = max(0.0, price * comm_rate)
    
    # 2. Brand & MRP Credibility (Kappa MRP Attenuation)
    FLAGSHIP_BRANDS = [
        "apple", "samsung", "sony", "dyson", "bose", "lg", "dell", "hp",
        "lenovo", "asus", "acer", "msi", "nike", "adidas", "puma", "reebok",
        "new balance", "asics", "sennheiser", "marshall", "bosch", "whirlpool"
    ]
    GENERIC_BRANDS = ["generic", "unbranded", "local", "no brand"]

    is_flagship = any(_matches_brand(b, title_lower) for b in FLAGSHIP_BRANDS)
    is_generic = any(_matches_brand(b, title_lower) for b in GENERIC_BRANDS)

    if is_verified_low or is_flagship:
        kappa_mrp = 1.0
        mrp_credibility = "HIGH"
    elif is_generic:
        if discount >= 80.0: kappa_mrp = 0.25
        elif discount >= 60.0: kappa_mrp = 0.50
        else: kappa_mrp = 0.75
        mrp_credibility = "LOW_GENERIC"
    else:
        if discount >= 85.0: kappa_mrp = 0.40
        elif discount >= 75.0: kappa_mrp = 0.70
        else: kappa_mrp = 1.0
        mrp_credibility = "STANDARD"

    eff_discount = max(0.0, discount * kappa_mrp)
    eff_savings = max(0.0, (mrp - price) * kappa_mrp)

    # 3. Component Scores (0 to 100 normalized)
    # A. Discount score (s_disc)
    if mrp >= 15000:
        if eff_discount < 15.0: s_disc = 0.0
        elif eff_discount >= 50.0: s_disc = 100.0
        else: s_disc = ((eff_discount - 15.0) / 35.0) * 100.0
    else:
        if eff_discount < 20.0: s_disc = 0.0
        elif eff_discount >= 80.0: s_disc = 100.0
        else: s_disc = ((eff_discount - 20.0) / 60.0) * 100.0

    # B. Absolute Savings score (s_save) - normalized to ₹8,000 cap
    s_save = min(100.0, (eff_savings / 8000.0) * 100.0)

    # C. Price History score (s_hist)
    s_hist = 100.0 if is_verified_low else 45.0

    # D. Heuristic Product / Brand Desirability score (s_ai)
    s_ai = get_heuristic_ai_ranking(
        title=title_str,
        platform=platform_str,
        price=int(price),
        mrp=int(mrp),
        discount=discount,
        is_verified_low=is_verified_low,
        product_id=product_id
    )
    if s_ai is None:
        s_ai = 50.0

    # E. Commercial Yield score (s_comm) - normalized to ₹500 expected commission
    s_comm = min(100.0, (expected_commission / 500.0) * 100.0)

    # F. Urgency (s_urg) & Trust (s_trust)
    s_urg = 100.0 if (is_lightning or "lightning" in platform_str) else 50.0
    s_trust = 90.0 if "amazon" in platform_str else (85.0 if "flipkart" in platform_str else 80.0)

    # 4. Weighted Base Sum
    base_score = (
        (s_disc * DIE_V2_WEIGHTS["discount"]) +
        (s_save * DIE_V2_WEIGHTS["savings"]) +
        (s_hist * DIE_V2_WEIGHTS["history"]) +
        (s_ai * DIE_V2_WEIGHTS["ai_ranking"]) +
        (s_comm * DIE_V2_WEIGHTS["commercial_yield"]) +
        (s_urg * DIE_V2_WEIGHTS["urgency"]) +
        (s_trust * DIE_V2_WEIGHTS["trust"])
    )

    # 5. Additive Feedback & Risk Modifiers
    # A. Popularity feedback (s_feedback)
    feedback_bonus = 0.0
    if qualified_clicks is not None:
        feedback_bonus = min(15.0, (max(0, qualified_clicks) // 10) * 2.5)
    elif product_id:
        db = SessionLocal()
        try:
            click_count = db.query(ClickLog).filter(
                ClickLog.product_id == product_id,
                ~ClickLog.user.like('%:bot%'),
                ~ClickLog.user.like('%:duplicate%')
            ).count()
            feedback_bonus = min(15.0, (click_count // 10) * 2.5)
        except Exception as db_err:
            logging.error(f"Failed to query click logs for score feedback: {db_err}")
        finally:
            db.close()

    # B. Rating & Reviews
    rating_mod = 0.0
    if rating is not None:
        if rating >= 4.5: rating_mod = 5.0
        elif rating >= 4.2: rating_mod = 3.0
        elif rating < 3.8: rating_mod = -10.0

    reviews_mod = 0.0
    if reviews is not None:
        if reviews >= 10000: reviews_mod = 4.0
        elif reviews >= 1000: reviews_mod = 2.0

    # C. Bank offer bonus
    bank_mod = 3.0 if has_bank_offer else 0.0

    # D. Price Glitch boost
    is_glitch = check_if_glitch(int(price), int(mrp), discount, product_id, title_str)
    glitch_mod = 15.0 if is_glitch else 0.0

    # E. Cancellation Risk penalty
    risk = calculate_cancellation_risk(platform_str, int(price), int(mrp), discount, title_str)
    risk_mod = -10.0 if risk >= 80.0 else (-5.0 if risk >= 50.0 else 0.0)

    # F. Optional OmniRoute Secondary Adjustment (bounded +/- 5)
    settings = load_settings()
    llm_adj = 0.0
    if settings.get("gemini_ai_scoring_enabled", False):
        llm_score = get_gemini_ai_desirability_score(title_str, int(price), int(mrp), discount, platform_str)
        if llm_score is not None:
            disagreement = llm_score - s_ai
            llm_adj = max(-5.0, min(5.0, disagreement * 0.10))

    final_score = base_score + feedback_bonus + rating_mod + reviews_mod + bank_mod + glitch_mod + risk_mod + llm_adj
    final_clamped = max(0.0, min(100.0, final_score))

    return {
        "score": round(final_clamped, 2),
        "base_score": round(base_score, 2),
        "s_disc": round(s_disc, 2),
        "s_save": round(s_save, 2),
        "s_hist": round(s_hist, 2),
        "s_ai": round(s_ai, 2),
        "s_comm": round(s_comm, 2),
        "s_urg": round(s_urg, 2),
        "s_trust": round(s_trust, 2),
        "kappa_mrp": kappa_mrp,
        "mrp_credibility": mrp_credibility,
        "category": category,
        "comm_rate": comm_rate,
        "expected_commission": round(expected_commission, 2),
        "feedback_bonus": round(feedback_bonus, 2),
        "rating_mod": rating_mod,
        "reviews_mod": reviews_mod,
        "bank_mod": bank_mod,
        "glitch_mod": glitch_mod,
        "risk_mod": risk_mod,
        "llm_adj": round(llm_adj, 2)
    }


def calculate_legacy_deal_score(
    platform: str,
    price: int,
    mrp: int,
    discount: float,
    is_verified_low: bool,
    is_lightning: bool = False,
    product_id: str = None,
    title: str = None
) -> float:
    """
    Legacy v1 Scorer fallback calculation for instant rollback capability.
    """
    if mrp >= 15000:
        if discount < 15.0: s_disc = 0.0
        elif discount >= 50.0: s_disc = 100.0
        else: s_disc = ((discount - 15.0) / 35.0) * 100.0
    else:
        if discount < 20.0: s_disc = 0.0
        elif discount >= 80.0: s_disc = 100.0
        else: s_disc = ((discount - 20.0) / 60.0) * 100.0

    savings = max(0, mrp - price)
    s_save = min(100.0, (savings / 10000.0) * 100.0)
    s_hist = 100.0 if is_verified_low else 40.0
    s_urg = 100.0 if (is_lightning or "lightning" in (platform or "").lower()) else 50.0
    s_trust = 80.0

    ai_score = get_heuristic_ai_ranking(
        title=title,
        platform=platform,
        price=price,
        mrp=mrp,
        discount=discount,
        is_verified_low=is_verified_low,
        product_id=product_id
    ) or 50.0

    is_glitch = check_if_glitch(price, mrp, discount, product_id, title)
    if not is_verified_low and not is_glitch:
        confidence_factor = max(0.40, min(1.0, ai_score / 60.0))
        s_disc = s_disc * confidence_factor

    weighted_sum = (s_disc * 0.35) + (s_save * 0.20) + (s_hist * 0.25) + (s_urg * 0.10) + (s_trust * 0.10) + (ai_score * 0.25)
    final_score = weighted_sum / 1.25
    if is_glitch:
        final_score += 15.0
    return max(0.0, min(100.0, final_score))


def calculate_deal_score(
    platform: str, 
    price: int, 
    mrp: int, 
    discount: float, 
    is_verified_low: bool,
    is_lightning: bool = False,
    product_id: str = None,
    title: str = None,
    rating: float = None,
    reviews: int = None,
    has_bank_offer: bool = False,
    qualified_clicks: int = None,
    category: str = None
) -> float:
    """
    Calculates the deal score (0.0 to 100.0) for a deal.
    Active Engine: Commercial Deal Intelligence Engine v2 (DIE v2) with instant rollback switch.
    """
    # 0. Check immediate rollback switch
    settings = load_settings()
    if not settings.get("enable_die_v2", True) or os.environ.get("ENABLE_DIE_V2", "true").lower() in ("false", "0", "no"):
        logging.info(f"[Scorer Rollback Fallback] DIE v2 disabled via configuration. Using legacy scorer for {product_id}.")
        return calculate_legacy_deal_score(
            platform=platform,
            price=price,
            mrp=mrp,
            discount=discount,
            is_verified_low=is_verified_low,
            is_lightning=is_lightning,
            product_id=product_id,
            title=title
        )

    breakdown = calculate_die_v2_breakdown(
        platform=platform,
        price=price,
        mrp=mrp,
        discount=discount,
        is_verified_low=is_verified_low,
        is_lightning=is_lightning,
        product_id=product_id,
        title=title,
        rating=rating,
        reviews=reviews,
        has_bank_offer=has_bank_offer,
        qualified_clicks=qualified_clicks,
        category=category
    )
    final_score = breakdown["score"]

    safe_price = breakdown.get("price", 0.0)
    safe_comm = breakdown.get("expected_commission", 0.0)
    logging.info(
        f"[DIE v2 Scorer] Deal ID: {product_id} | Cat: {breakdown['category']} | Comm: Rs.{safe_comm:.1f} | "
        f"Final Score: {final_score:.2f}"
    )
    return final_score


def check_if_glitch(price: int, mrp: int, discount: float, unique_id: str = None, title: str = None) -> bool:
    """
    Checks if a deal is an extreme price glitch/error based on high discount thresholds,
    sudden massive drops compared to tracked historical price averages, and
    category-aware heuristics (no external API required).
    """
    title_lower = title.lower() if title else ""
    LOW_VALUE_ACCESSORIES = [
        "cable", "adapter", "case", "cover", "tempered glass", "screen protector",
        "screen guard", "keychain", "sticker", "holder", "stand", "mount", "pouch", "strap"
    ]
    GENERIC_BUDGET_TERMS = [
        "generic", "unbranded", "local", "no brand"
    ]
    
    is_cheap_accessory = any(kw in title_lower for kw in LOW_VALUE_ACCESSORIES)
    is_generic = any(kw in title_lower for kw in GENERIC_BUDGET_TERMS)

    # Heuristic 1: Extreme discount (on non-generic, non-accessory items)
    if discount >= 85.0 and not is_cheap_accessory and not is_generic:
        return True
        
    # Heuristic 2: Large historical drop (confirmed by tracked prices)
    if unique_id:
        db = SessionLocal()
        try:
            hist = db.query(PriceHistory.price).filter_by(product_id=unique_id).all()
            if hist:
                prices = [h[0] for h in hist if h[0] > 0]
                if len(prices) >= 3:
                    avg_price = sum(prices) / len(prices)
                    if price <= (avg_price * 0.35): # 65% drop from average
                        return True
        except Exception as e:
            logging.error(f"Error checking glitch status against history: {e}")
        finally:
            db.close()
            
    # Heuristic 3: Category-aware glitch detection for high discounts (70-85%)
    # High-value electronics at extreme discounts are almost always price errors
    if discount >= 70.0 and title:
        HIGH_VALUE_ELECTRONICS = [
            "laptop", "smartphone", "phone", "iphone", "macbook", "ipad",
            "tablet", "monitor", "television", "tv", "processor", "gpu",
            "graphics card", "console", "playstation", "xbox", "camera",
            "air conditioner", "refrigerator", "washing machine",
        ]
        is_high_value = any(kw in title_lower for kw in HIGH_VALUE_ELECTRONICS)
        
        if is_high_value and price < 5000 and not is_generic:
            logging.info(f"[Glitch Detector] Category-heuristic glitch: {title[:40]}... at ₹{price} ({discount:.0f}% OFF)")
            return True
        elif is_high_value and price < 15000 and discount >= 75.0 and not is_generic:
            logging.info(f"[Glitch Detector] Probable glitch: {title[:40]}... at ₹{price} ({discount:.0f}% OFF)")
            return True
            
    return False

def should_publish_deal(platform: str, score: float) -> bool:
    settings = load_settings()
    rules = settings.get("scoring_rules", {})
    min_score = rules.get("min_publish_score", 45.0)
    return score >= min_score

def calculate_cancellation_risk(platform: str, price: int, mrp: int, discount: float, title: str) -> float:
    """
    Computes pricing error/glitch cancel probability based on item category and discount rate (Feature 5 on Admin).
    """
    if discount >= 85.0:
        # High value electronics have extremely high cancellation rates
        title_lower = title.lower() if title else ""
        if any(x in title_lower for x in ["laptop", "smartphone", "phone", "monitor", "tv", "processor", "gpu", "console", "camera"]):
            return 95.0
        return 80.0
    elif discount >= 70.0:
        return 45.0
    return 5.0
