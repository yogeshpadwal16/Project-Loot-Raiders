import logging
from config.settings import load_settings

def calculate_deal_score(
    platform: str, 
    price: int, 
    mrp: int, 
    discount: float, 
    is_verified_low: bool,
    is_lightning: bool = False
) -> float:
    """
    Calculates a normalized score (0 to 100) for a deal based on settings.json weights.
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
    
    # Final Weighted Aggregation
    final_score = (
        (s_disc * weights.get("discount", 0.35)) +
        (s_save * weights.get("savings", 0.20)) +
        (s_hist * weights.get("history", 0.25)) +
        (s_urg * weights.get("urgency", 0.10)) +
        (s_trust * weights.get("trust", 0.10))
    )
    
    final_score = max(0.0, min(100.0, final_score))
    logging.info(f"Deal Scoring -> [Platform: {platform}] Price: ₹{price}, Discount: {discount:.1f}%, VerifiedLow: {is_verified_low} -> Final Score: {final_score:.1f}")
    return final_score

def should_publish_deal(platform: str, score: float) -> bool:
    settings = load_settings()
    rules = settings.get("scoring_rules", {})
    min_score = rules.get("min_publish_score", 70.0)
    return score >= min_score
