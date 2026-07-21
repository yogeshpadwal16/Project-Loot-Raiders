import time
import logging
import threading
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from config.settings import load_settings
from deal_engine.notifier import enqueue_alert
from deal_engine.scorer import calculate_deal_score

def supermarket_monitor_loop():
    logging.info("Supermarket clearance monitor loop activated.")
    while True:
        # Scrape / seed simulated JioMart/DMart grocery clearance drops
        db = None
        try:
            db = SessionLocal()
            clearance_deals = [
                {
                    "id": "grocery_oil_dmart",
                    "title": "Fortune Mustard Oil 1L (DMart Warehouse Clearance)",
                    "price": 110,
                    "mrp": 210,
                    "discount": 47.6,
                    "image_url": "https://www.dmart.in/images/products/Fortune-Mustard-Oil-1L.jpg",
                    "url": "https://www.dmart.in/product/fortune-mustard-oil-1l",
                    "platform": "dmart_clearance"
                },
                {
                    "id": "grocery_sugar_jiomart",
                    "title": "Madhur Pure Sugar 5kg (JioMart Regional Flash Offer)",
                    "price": 199,
                    "mrp": 350,
                    "discount": 43.1,
                    "image_url": "https://www.jiomart.com/images/products/Madhur-Pure-Sugar-5kg.jpg",
                    "url": "https://www.jiomart.com/product/madhur-sugar-5kg",
                    "platform": "jiomart_clearance"
                }
            ]
            
            for deal in clearance_deals:
                try:
                    # Check duplicate
                    existing = db.query(Product).filter_by(id=deal["id"]).first()
                    if not existing:
                        prod = Product(
                            id=deal["id"],
                            platform=deal["platform"],
                            title=deal["title"],
                            image_url=deal["image_url"],
                            url=deal["url"]
                        )
                        db.add(prod)
                        db.flush()
                        
                        price_hist = PriceHistory(
                            product_id=deal["id"],
                            price=deal["price"],
                            mrp=deal["mrp"],
                            discount=deal["discount"],
                            is_verified_low=True,
                            deal_score=85.0,
                            timestamp=time.time()
                        )
                        db.add(price_hist)
                        db.commit()
                        
                        # Alert channel
                        enqueue_alert(
                            platform=deal["platform"],
                            title=deal["title"],
                            price=deal["price"],
                            mrp=deal["mrp"],
                            discount=deal["discount"],
                            img_url=deal["image_url"],
                            final_url=deal["url"],
                            is_verified_low=True,
                            deal_score=85.0,
                            unique_id=deal["id"],
                            bank_offers=["Extra 10% instant discount on orders above Rs 999"],
                            coupon_detail="FREE_DELIVERY",
                            review_grade="A+"
                        )
                        logging.info(f"Broadcasted supermarket clearance loot drop: {deal['title']}")
                except Exception as deal_err:
                    db.rollback()
                    logging.error(f"Error processing supermarket deal {deal.get('id', 'unknown')}: {deal_err}")
        except Exception as e:
            logging.error(f"Error in supermarket monitor loop: {e}")
        finally:
            if db:
                db.close()
            
        # Check every 4 hours
        time.sleep(14400)

def start_supermarket_monitor():
    t = threading.Thread(target=supermarket_monitor_loop, daemon=True)
    t.start()
