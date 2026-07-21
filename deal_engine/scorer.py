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
    Heuristic-based deal desirability scorer. Analyzes product category,
    brand tier, price point, and discount to generate a score 0-100.
    Replaces Gemini API — instant, free, always works.
    """
    if not title:
        return None
        
    cache_key = (product_id, price) if product_id else (title, price)
    cached = _ai_score_cache.get(cache_key)
    if cached is not None:
        return cached
    
    title_lower = title.lower()
    score = 50.0  # Base score
    
    # 1. Category desirability scoring
    HIGH_VALUE_CATEGORIES = {
        "laptop": 25, "smartphone": 22, "phone": 22, "iphone": 28, "macbook": 28,
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
    
    LOW_VALUE_CATEGORIES = {
        "cable": -15, "adapter": -12, "charger cable": -10, "otg": -15,
        "case": -12, "cover": -12, "back cover": -15, "tempered glass": -15,
        "screen protector": -15, "screen guard": -15, "protector": -12,
        "keychain": -20, "sticker": -20, "decal": -20,
        "holder": -12, "stand": -10, "mount": -8,
        "pouch": -12, "strap": -12, "band": -8,
        "pen": -10, "pencil": -10, "eraser": -15, "notebook": -8,
        "socks": -10, "handkerchief": -15, "napkin": -15,
    }
    
    category_bonus = 0
    for keyword, bonus in HIGH_VALUE_CATEGORIES.items():
        if keyword in title_lower:
            category_bonus = max(category_bonus, bonus)
    for keyword, penalty in LOW_VALUE_CATEGORIES.items():
        if keyword in title_lower:
            category_bonus = min(category_bonus, penalty)
    score += category_bonus
    
    # 2. Brand tier scoring
    PREMIUM_BRANDS = [
        "apple", "samsung", "sony", "bose", "dyson", "lg", "oneplus",
        "dell", "hp", "lenovo", "asus", "acer", "msi", "nothing",
        "nike", "adidas", "puma", "reebok", "new balance", "asics",
        "boat", "jbl", "sennheiser", "marshall",
        "philips", "bosch", "whirlpool", "godrej", "havells",
        "levi", "us polo", "tommy hilfiger", "calvin klein",
    ]
    BUDGET_BRANDS = [
        "generic", "local", "unbranded", "no brand",
    ]
    
    for brand in PREMIUM_BRANDS:
        if brand in title_lower:
            score += 8
            break
    for brand in BUDGET_BRANDS:
        if brand in title_lower:
            score -= 10
            break
    
    # 3. Price sweet-spot scoring (most desirable: ₹500–₹5000)
    if 500 <= price <= 5000:
        score += 10  # Mass-market sweet spot
    elif 5000 < price <= 15000:
        score += 5   # Mid-range
    elif price > 15000:
        score += 3   # Aspirational but fewer buyers
    elif price < 200:
        score -= 10  # Too cheap = likely junk
    
    # 4. Discount magnitude bonus (on top of category)
    if discount >= 80:
        score += 15
    elif discount >= 70:
        score += 10
    elif discount >= 60:
        score += 5
    elif discount >= 50:
        score += 3
    
    # 5. Verified historical low bonus
    if is_verified_low:
        score += 10
    
    # 6. Absolute savings impact
    savings = max(0, mrp - price)
    if savings >= 5000:
        score += 8
    elif savings >= 2000:
        score += 5
    elif savings >= 1000:
        score += 3
    
    # Clamp to 0-100
    score = max(0.0, min(100.0, score))
    
    reason = f"Heuristic: cat={category_bonus:+d}, price_range={'sweet' if 500<=price<=5000 else 'other'}, disc={discount:.0f}%"
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
    Gemini AI desirability rankings, and real-time click feedback loops.
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
    # Scale discount from 30% (score 0) to 80% (score 100)
    if discount < 30.0:
        s_disc = 0.0
    elif discount >= 80.0:
        s_disc = 100.0
    else:
        s_disc = ((discount - 30.0) / (80.0 - 30.0)) * 100.0
        
    # 2. Absolute Savings Score (s_save)
    # Scale absolute savings from ₹0 (score 0) to ₹3000 (score 100)
    savings = max(0, mrp - price)
    if savings >= 3000:
        s_save = 100.0
    else:
        s_save = (savings / 3000.0) * 100.0
        
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

    # Query heuristic AI ranking score (no external API)
    ai_score = get_heuristic_ai_ranking(
        title=title,
        platform=platform,
        price=price,
        mrp=mrp,
        discount=discount,
        is_verified_low=is_verified_low,
        product_id=product_id
    )

    # Dynamic Weight Normalization based on whether AI score is available
    if ai_score is not None:
        active_weights = dict(weights)
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
    
    # Check if this is a price glitch / extreme price error
    is_glitch = check_if_glitch(price, mrp, discount, product_id, title)
    if is_glitch:
        final_score += 15.0
        logging.info(f"[AI Scorer] Price glitch detected for product {product_id}! Score boosted.")
    
    # 7. Shield Against Fake Quoted Discounts / Fake MRPs
    # If the price drop is not historically verified and it's not a glitch, cap the score below the publish threshold
    if not is_verified_low and not is_glitch:
        min_publish = rules.get("min_publish_score", 45.0)
        final_score = min(min_publish - 2.0, final_score)
        
    final_score = max(0.0, min(100.0, final_score))
    
    logging.info(f"Deal Scoring -> [ID: {product_id}] Discount: {discount:.1f}%, VerifiedLow: {is_verified_low}, AI Score: {ai_score}, Glitch: {is_glitch}, Clicks Bonus: +{feedback_bonus:.1f} -> Final Score: {final_score:.1f}")
    return final_score

def check_if_glitch(price: int, mrp: int, discount: float, unique_id: str = None, title: str = None) -> bool:
    """
    Checks if a deal is an extreme price glitch/error based on high discount thresholds,
    sudden massive drops compared to tracked historical price averages, and
    category-aware heuristics (no external API required).
    """
    # Heuristic 1: Extreme discount
    if discount >= 85.0:
        return True
        
    # Heuristic 2: Large historical drop
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
        title_lower = title.lower()
        HIGH_VALUE_ELECTRONICS = [
            "laptop", "smartphone", "phone", "iphone", "macbook", "ipad",
            "tablet", "monitor", "television", "tv", "processor", "gpu",
            "graphics card", "console", "playstation", "xbox", "camera",
            "air conditioner", "refrigerator", "washing machine",
        ]
        is_high_value = any(kw in title_lower for kw in HIGH_VALUE_ELECTRONICS)
        
        if is_high_value and price < 5000:
            # A high-value item under ₹5000 with 70%+ discount is almost certainly a glitch
            logging.info(f"[Glitch Detector] Category-heuristic glitch: {title[:40]}... at ₹{price} ({discount:.0f}% OFF)")
            return True
        elif is_high_value and price < 15000 and discount >= 75.0:
            # High-value item at extreme discount range — likely glitch
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
