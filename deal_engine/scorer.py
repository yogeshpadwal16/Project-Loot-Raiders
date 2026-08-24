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
        if keyword in title_lower:
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
            "shoe": 10, "sneaker": 12, "running shoe": 10,
            "backpack": 6, "luggage": 8, "suitcase": 8,
            "perfume": 8, "fragrance": 8,
            "jacket": 8, "hoodie": 6, "jeans": 6, "shirt": 4, "t-shirt": 3,
            "kurta": 4, "saree": 5, "dress": 6,
        }
        category_bonus = 0
        for keyword, bonus in HIGH_VALUE_CATEGORIES.items():
            if keyword in title_lower:
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
    if not (is_accessory and any(b in title_lower for b in BUDGET_GENERIC_BRANDS)):
        for brand in FLAGSHIP_BRANDS:
            if brand in title_lower:
                brand_score = 8
                break
        if brand_score == 0:
            for brand in MID_POPULAR_BRANDS:
                if brand in title_lower:
                    brand_score = 4
                    break
    for brand in BUDGET_GENERIC_BRANDS:
        if brand in title_lower:
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
    has_bank_offer: bool = False
) -> float:
    """
    Calculates a normalized score (0 to 100) for a deal based on settings.json weights,
    heuristic product desirability, OmniRoute secondary input, and click feedback loops.
    """
    settings = load_settings()
    rules = settings.get("scoring_rules", {})
    weights = rules.get("weights", {
        "discount": 0.35,
        "savings": 0.20,
        "history": 0.25,
        "urgency": 0.10,
        "trust": 0.10
    })
    
    # 1. Discount Score (s_disc)
    # Adaptive scaling: High-MRP items (electronics/appliances >= 15k) scale from 15% discount
    if mrp >= 15000:
        if discount < 15.0:
            s_disc = 0.0
        elif discount >= 50.0:
            s_disc = 100.0
        else:
            s_disc = ((discount - 15.0) / (50.0 - 15.0)) * 100.0
    else:
        if discount < 20.0:
            s_disc = 0.0
        elif discount >= 80.0:
            s_disc = 100.0
        else:
            s_disc = ((discount - 20.0) / (80.0 - 20.0)) * 100.0
        
    # 2. Absolute Savings Score (s_save)
    # Scale absolute savings up to ₹10,000 (score 100)
    savings = max(0, mrp - price)
    s_save = min(100.0, (savings / 10000.0) * 100.0)
        
    # 3. History Score (s_hist)
    # Verified low price gets 100, otherwise 40
    s_hist = 100.0 if is_verified_low else 40.0
    
    # 4. Urgency Score (s_urg)
    # Lightning/Flash deals get 100, standard items get 50
    s_urg = 100.0 if (is_lightning or "lightning" in platform.lower()) else 50.0
    
    # 5. Trust Score (s_trust)
    # Look up retailer/stream configuration trust score
    trust_scores = rules.get("retailer_trust_scores", {})
    s_trust = float(trust_scores.get(platform, 80.0))
    
    # Resolve product title from DB if not provided directly but product_id is present
    if not title and product_id:
        db = SessionLocal()
        try:
            prod = db.query(Product).filter_by(id=product_id).first()
            if prod:
                title = prod.title
        except Exception as db_err:
            logging.error(f"Failed to fetch product title from DB for scoring: {db_err}")
        finally:
            db.close()

    # Always calculate the deterministic heuristic AI ranking.
    # This remains the primary product-desirability signal.
    heuristic_ai_score = get_heuristic_ai_ranking(
        title=title,
        platform=platform,
        price=price,
        mrp=mrp,
        discount=discount,
        is_verified_low=is_verified_low,
        product_id=product_id
    )

    # OmniRoute is an optional secondary opinion.
    # It must never become a hard dependency or replace deterministic scoring.
    llm_ai_score = None
    if settings.get("gemini_ai_scoring_enabled", False):
        llm_ai_score = get_gemini_ai_desirability_score(
            title, price, mrp, discount, platform
        )

    # Check if this is a price glitch / extreme price error
    is_glitch = check_if_glitch(price, mrp, discount, product_id, title)

    # Use heuristic score in the weighted scoring model.
    ai_score = heuristic_ai_score

    # Confidence-adjusted discount signal for unverified, non-glitch deals
    if not is_verified_low and not is_glitch:
        confidence_factor = max(0.40, min(1.0, (ai_score or 50.0) / 60.0))
        s_disc = s_disc * confidence_factor

    active_weights = dict(weights)

    if ai_score is not None:
        if "ai_ranking" not in active_weights:
            active_weights["ai_ranking"] = 0.25

        total_weight = sum(active_weights.values())

        weighted_sum = (
            (s_disc * active_weights.get("discount", 0.0)) +
            (s_save * active_weights.get("savings", 0.0)) +
            (s_hist * active_weights.get("history", 0.0)) +
            (s_urg * active_weights.get("urgency", 0.0)) +
            (s_trust * active_weights.get("trust", 0.0)) +
            (ai_score * active_weights.get("ai_ranking", 0.0))
        )

        final_score = weighted_sum / total_weight

    else:
        total_weight = sum(weights.values())

        weighted_sum = (
            (s_disc * weights.get("discount", 0.0)) +
            (s_save * weights.get("savings", 0.0)) +
            (s_hist * weights.get("history", 0.0)) +
            (s_urg * weights.get("urgency", 0.0)) +
            (s_trust * weights.get("trust", 0.0))
        )

        final_score = weighted_sum / total_weight

    # OmniRoute may adjust the deterministic result only slightly.
    # Maximum influence: +/- 5 points.
    ai_adjustment = 0.0

    if llm_ai_score is not None and heuristic_ai_score is not None:
        disagreement = llm_ai_score - heuristic_ai_score

        # Scale disagreement down heavily and clamp it.
        ai_adjustment = max(-5.0, min(5.0, disagreement * 0.10))

        final_score += ai_adjustment
    # 6. Real-time Feedback Popularity Bonus (s_feedback)
    # Add +2 points for every 10 clicks, capped at +15 points max boost
    feedback_bonus = 0.0
    if product_id:
        db = SessionLocal()
        try:
            click_count = db.query(ClickLog).filter_by(product_id=product_id).count()
            feedback_bonus = min(15.0, (click_count // 10) * 2.0)
        except Exception as db_err:
            logging.error(f"Failed to query click logs for score feedback: {db_err}")
        finally:
            db.close()
            
    final_score += feedback_bonus
    
    # 6.5 Deal Intelligence Engine (DIE) Adjustments
    die_adjustment = 0.0
    if rating is not None:
        if rating >= 4.5:
            die_adjustment += 10.0
        elif rating >= 4.2:
            die_adjustment += 5.0
        elif rating < 3.8:
            die_adjustment -= 15.0
            
    if reviews is not None:
        if reviews >= 10000:
            die_adjustment += 5.0
        elif reviews >= 1000:
            die_adjustment += 3.0
            
    if has_bank_offer:
        die_adjustment += 5.0
        
    final_score += die_adjustment
    
    if is_glitch:
        final_score += 15.0
        logging.info(f"[AI Scorer] Price glitch detected for product {product_id}! Score boosted.")
    
    final_score = max(0.0, min(100.0, final_score))
    
    logging.info(f"Deal Scoring -> [ID: {product_id}] Discount: {discount:.1f}%, VerifiedLow: {is_verified_low}, AI Score: {ai_score}, Glitch: {is_glitch}, Clicks Bonus: +{feedback_bonus:.1f} -> Final Score: {final_score:.1f}")
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
