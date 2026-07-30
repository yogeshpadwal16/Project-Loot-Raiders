import logging
from database import SessionLocal, PriceHistory

logger = logging.getLogger("loot_raiders.redrop")


def check_for_redrop(product_id: str, current_price: int) -> tuple[bool, str | None]:
    """
    Checks if a product has drop-up-drop price behavior.
    
    If the product previously dropped to price X, then rose back up, and has now
    dropped back down below that peak to a low price, it returns (True, "Price Dropped Again!").
    """
    db = SessionLocal()
    try:
        # Load all history entries for this product (ascending by timestamp)
        history = db.query(PriceHistory).filter_by(product_id=product_id).order_by(PriceHistory.timestamp.asc()).all()
        
        if len(history) < 3:
            return False, None
            
        prices = [h.price for h in history]
        
        # We look for a pattern where prices went: Low -> High -> Low (current_price)
        # We check if there's a peak price in the history that is higher than current_price
        # and there is an earlier price that was lower than that peak
        peak_index = -1
        peak_price = 0
        
        for i in range(1, len(prices) - 1):
            if prices[i] > prices[i-1] and prices[i] > current_price:
                if prices[i] > peak_price:
                    peak_price = prices[i]
                    peak_index = i
                    
        if peak_index != -1:
            # We found a temporary rise. Now check if the current price is a drop below that peak
            # representing a double drop alert!
            logger.info(f"[Redrop] Double drop detected for product {product_id}! Peak was {peak_price}, current is {current_price}.")
            return True, "⚡ <b>LOOT ALERT: Price Dropped Again!</b> ⚡"

    except Exception as e:
        logger.error(f"[Redrop] Failed to check for double drop: {e}")
    finally:
        db.close()

    return False, None
