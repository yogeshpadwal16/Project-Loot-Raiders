import os
import json
import time
import logging
import threading
from deal_engine.deal_processor import process_deal_url
from config.settings import load_settings

def start_catalog_monitor():
    """Spawns the Catalog Priority Monitor in a separate background thread."""
    thread = threading.Thread(target=run_catalog_loop, daemon=True)
    thread.start()
    logging.info("[Catalog Monitor] Priority monitoring thread spawned.")

def run_catalog_loop():
    """Periodically scans cataloged products in the database/JSON configuration."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    catalog_file = os.path.join(base_dir, "config", "catalog_urls.json")
    os.makedirs(os.path.dirname(catalog_file), exist_ok=True)
    
    # Bootstrap default catalog with top products across all categories (Grocery, Home, Beauty, Tech)
    default_catalog = [
        # Groceries & Household Essentials
        "https://www.amazon.in/dp/B0757L8SBF",  # Tata Tea Gold
        "https://www.amazon.in/dp/B00V52G39Y",  # Surf Excel Easy Wash
        "https://www.amazon.in/dp/B01F29P522",  # Dettol Liquid Handwash Refill
        # Beauty & Personal Care
        "https://www.amazon.in/dp/B07KXP71C4",  # Nivea Body Lotion
        "https://www.amazon.in/dp/B08V8MLHR6",  # L'Oreal Paris Serum
        "https://www.amazon.in/dp/B07NSS91X1",  # Ponds Super Light Gel
        # Home & Kitchen
        "https://www.amazon.in/dp/B08XMB8JBM",  # Solimo Microfibre Comforter
        "https://www.amazon.in/dp/B09J4TKWNS",  # Pigeon Amaze Electric Kettle
        # Clothing & Accessories
        "https://www.amazon.in/dp/B0CB12W4XW",  # Red Tape Sneakers
        "https://www.amazon.in/dp/B0BL1G6RNP",  # Puma T-Shirt
        # Tech & Audio
        "https://www.amazon.in/dp/B097RV41Q2",  # boat Bassheads 100 Wired Earphones
        "https://www.amazon.in/dp/B084D77G16"   # SanDisk Ultra 64GB MicroSD Card
    ]
    
    if not os.path.exists(catalog_file):
        with open(catalog_file, "w", encoding="utf-8") as f:
            json.dump(default_catalog, f, indent=4)
        logging.info("[Catalog Monitor] Seeded default multi-category product catalog.")
        
    while True:
        try:
            # Reload catalog file dynamically
            with open(catalog_file, "r", encoding="utf-8") as f:
                urls = json.load(f)
                
            if not urls:
                logging.warning("[Catalog Monitor] Catalog URL list is empty. Add URLs to config/catalog_urls.json")
            else:
                logging.info(f"[Catalog Monitor] Beginning price-check cycle for {len(urls)} target items...")
                for url in urls:
                    try:
                        # Process target URL
                        process_deal_url(url)
                        # Polite spacing between requests to stay stealthy
                        time.sleep(15) 
                    except Exception as deal_err:
                        logging.error(f"[Catalog Monitor] Error processing target '{url}': {deal_err}")
                        
                logging.info("[Catalog Monitor] Ingestion cycle complete. Sleeping for 30 minutes.")
        except Exception as loop_err:
            logging.error(f"[Catalog Monitor] Execution loop error: {loop_err}")
            
        # Scan every 30 minutes
        time.sleep(1800)
