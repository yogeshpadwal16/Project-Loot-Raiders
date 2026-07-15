import logging
from config.settings import load_settings
from database.db_session import SessionLocal
from knowledge_base.models import ClickLog

def calculate_deal_score(
    platform: str, 
    price: int, 
    mrp: int, 
    discount: float, 
    is_verified_low: bool,
    is_lightning: bool = False,
    product_id: str = None
) -> float:
    """
    Calculates a normalized score (0 to 100) for a deal based on settings.json weights
    and real-time click feedback loops.
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
    # Scale discount from 45% (score 0) to 85% (score 100)
    if discount < 45.0:
        s_disc = 0.0
    elif discount >= 85.0:
        s_disc = 100.0
    else:
        s_disc = ((discount - 45.0) / (85.0 - 45.0)) * 100.0
        
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
    
    # Final Weighted Aggregation
    final_score = (
        (s_disc * weights.get("discount", 0.35)) +
        (s_save * weights.get("savings", 0.20)) +
        (s_hist * weights.get("history", 0.25)) +
        (s_urg * weights.get("urgency", 0.10)) +
        (s_trust * weights.get("trust", 0.10))
    )
    
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
    
    # 7. Shield Against Fake Quoted Discounts / Fake MRPs
    # If the price drop is not historically verified, cap the score below the publish threshold
    if not is_verified_low:
        min_publish = rules.get("min_publish_score", 70.0)
        final_score = min(min_publish - 2.0, final_score)
        
    final_score = max(0.0, min(100.0, final_score))
    
    logging.info(f"Deal Scoring -> [ID: {product_id}] Discount: {discount:.1f}%, VerifiedLow: {is_verified_low}, Clicks Bonus: +{feedback_bonus:.1f} -> Final Score: {final_score:.1f}")
    return final_score

def should_publish_deal(platform: str, score: float) -> bool:
    settings = load_settings()
    rules = settings.get("scoring_rules", {})
    min_score = rules.get("min_publish_score", 70.0)
    return score >= min_score
