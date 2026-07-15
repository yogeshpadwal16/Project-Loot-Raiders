import os
import sys
import json
import time

# Add root folder to system path to import local modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from database.db_session import SessionLocal, init_db
from knowledge_base.models import Product, PriceHistory, ClickLog, SelectorMatrix

def migrate():
    print("Initialising database tables...")
    init_db()
    db = SessionLocal()
    
    # 1. Migrate Selectors Matrix Configuration
    selectors_file = os.path.join(BASE_DIR, "selectors.json")
    if os.path.exists(selectors_file):
        try:
            print("Migrating selectors configurations...")
            with open(selectors_file, 'r', encoding='utf-8') as f:
                sel_data = json.load(f)
            for plat_key, config in sel_data.items():
                # Avoid duplicates
                existing = db.query(SelectorMatrix).filter_by(platform=plat_key).first()
                if not existing:
                    matrix = SelectorMatrix(
                        platform=plat_key,
                        url=config.get("url", ""),
                        card_selector=config.get("card_selector", ""),
                        title_selector=config.get("title_selector", ""),
                        link_selector=config.get("link_selector", ""),
                        image_selector=config.get("image_selector", "")
                    )
                    db.add(matrix)
            db.commit()
            print("Selectors migrated successfully.")
        except Exception as e:
            print(f"Error migrating selectors: {e}")
            db.rollback()

    # 2. Migrate Product & Price History Records
    deals_file = os.path.join(BASE_DIR, "dashboard", "deals_history.json")
    if os.path.exists(deals_file):
        try:
            print("Migrating products and pricing records...")
            with open(deals_file, 'r', encoding='utf-8') as f:
                deals_data = json.load(f)
            for deal in deals_data:
                deal_id = deal.get("id")
                if not deal_id:
                    continue
                
                # Insert or get product
                product = db.query(Product).filter_by(id=deal_id).first()
                if not product:
                    product = Product(
                        id=deal_id,
                        platform=deal.get("platform", ""),
                        title=deal.get("title", ""),
                        image_url=deal.get("image_url", ""),
                        url=deal.get("url", "")
                    )
                    db.add(product)
                    db.flush() # Flush to link price history
                
                # Check price history duplicate
                price_exists = db.query(PriceHistory).filter_by(
                    product_id=deal_id, 
                    price=deal.get("price"),
                    timestamp=deal.get("timestamp")
                ).first()
                
                if not price_exists:
                    price_hist = PriceHistory(
                        product_id=deal_id,
                        price=deal.get("price", 0),
                        mrp=deal.get("mrp", 0),
                        discount=deal.get("discount", 0.0),
                        is_verified_low=deal.get("is_verified_low", False),
                        timestamp=deal.get("timestamp", time.time())
                    )
                    db.add(price_hist)
            db.commit()
            print("Products and pricing history records migrated.")
        except Exception as e:
            print(f"Error migrating deals: {e}")
            db.rollback()

    # 3. Migrate Click Logs Activity
    clicks_file = os.path.join(BASE_DIR, "clicks_activity.json")
    if os.path.exists(clicks_file):
        try:
            print("Migrating clicks activities logs...")
            with open(clicks_file, 'r', encoding='utf-8') as f:
                clicks_data = json.load(f)
            for click in clicks_data:
                click_log = ClickLog(
                    product_id=click.get("deal_id", ""),
                    title=click.get("title", "Unknown Product"),
                    ip=click.get("ip", ""),
                    user=click.get("user", "Anonymous"),
                    user_agent=click.get("user_agent", ""),
                    timestamp=click.get("timestamp", time.time())
                )
                db.add(click_log)
            db.commit()
            print("Click activity logs migrated.")
        except Exception as e:
            print(f"Error migrating click activity: {e}")
            db.rollback()

    db.close()
    print("Migration finished!")

if __name__ == "__main__":
    migrate()
