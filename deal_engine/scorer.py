import os
import re
import json
import logging
import requests
from config.settings import load_settings
from database.db_session import SessionLocal
from knowledge_base.models import ClickLog, Product, PriceHistory

_ai_score_cache = {}

def get_gemini_ai_ranking(
    title: str,
    platform: str,
    price: int,
    mrp: int,
    discount: float,
    is_verified_low: bool,
    product_id: str = None
) -> float:
    """
    Calls the Gemini API to evaluate and rate the deal's quality/desirability.
    Uses an in-memory cache to avoid duplicate API calls.
    Returns a score from 0 to 100, or None if API call fails/is not configured.
    """
    if not title:
        return None
        
    cache_key = (product_id, price) if product_id else (title, price)
    if cache_key in _ai_score_cache:
        return _ai_score_cache[cache_key]
        
    settings = load_settings()
    api_key = os.environ.get("GEMINI_API_KEY") or settings.get("gemini_api_key")
    if not api_key or "YOUR_GEMINI" in api_key or api_key.strip() == "":
        return None
        
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
        
        prompt = (
            "You are an expert retail deal analyst. Evaluate this deal and return a desirability score between 0 and 100. "
            "Consider consumer demand, brand value, real price value, and filter out low-value spam (like cheap phone cases, cables, local stickers).\n\n"
            f"Product: {title}\n"
            f"Platform: {platform.upper()}\n"
            f"Loot Price: Rs. {price:,}\n"
            f"Original MRP: Rs. {mrp:,}\n"
            f"Discount: {discount:.0f}% OFF\n"
            f"Verified Low Price: {'Yes' if is_verified_low else 'No'}\n\n"
            "Return a JSON object matching this structure (no formatting or markdown wrappers, just raw JSON):\n"
            '{"score": <integer 0-100>, "reason": "<brief justification>"}'
        )
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        logging.info(f"[AI Ranker] Querying Gemini for: {title[:40]}... (Price: ₹{price})")
        
        res = requests.post(url, json=payload, timeout=25)
        if res.status_code == 200:
            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # Clean JSON wrappers if present
            if text.startswith("```"):
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
                text = text.strip()
                
            result = json.loads(text)
            ai_score = float(result.get("score", 50))
            reason = result.get("reason", "")
            
            logging.info(f"[AI Ranker] Gemini Response -> Score: {ai_score}, Reason: {reason}")
            
            _ai_score_cache[cache_key] = ai_score
            return ai_score
        else:
            logging.warning(f"[AI Ranker] Gemini API returned status {res.status_code}: {res.text}")
            
    except Exception as e:
        logging.error(f"[AI Ranker] Failed to fetch Gemini AI ranking: {e}")
        
    return None

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

    # Query Gemini AI Ranking score
    ai_score = get_gemini_ai_ranking(
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
    sudden massive drops compared to tracked historical price averages, and AI validation.
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
            
    # Heuristic 3: AI validation for high discounts (between 70% and 85%) (Feature 1)
    if discount >= 70.0 and title:
        settings = load_settings()
        api_key = os.environ.get("GEMINI_API_KEY") or settings.get("gemini_api_key")
        if api_key and "YOUR_GEMINI" not in api_key and api_key.strip() != "":
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
                prompt = (
                    "You are a price error auditor for e-commerce sites (Amazon, Flipkart). "
                    "Analyze if this discount looks like a merchant price error/glitch (e.g., brand-new laptop for Rs. 500, "
                    "high-end smartphone for Rs. 2,000, or a coupon stack glitch) versus a normal clearance discount. "
                    "Respond with a JSON object matching this structure (no markdown wrappers):\n"
                    '{"is_glitch": <true/false>, "reason": "<brief justification>"}\n\n'
                    f"Product: {title}\n"
                    f"Price: Rs. {price:,}\n"
                    f"MRP: Rs. {mrp:,}\n"
                    f"Discount: {discount:.0f}% OFF"
                )
                payload = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }]
                }
                res = requests.post(url, json=payload, timeout=25)
                if res.status_code == 200:
                    text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text.startswith("```"):
                        text = re.sub(r'^```(?:json)?\s*', '', text)
                        text = re.sub(r'\s*```$', '', text)
                        text = text.strip()
                    result = json.loads(text)
                    return bool(result.get("is_glitch", False))
            except Exception as e:
                logging.error(f"Failed to verify glitch via AI: {e}")
            
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
