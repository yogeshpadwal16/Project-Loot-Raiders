import sys

# Re-export key functions for backward compatibility with import references (e.g. from deal_processor.py)
from core.engine import main, scrape_product_details
from database.operations import verify_historical_low, save_deal_to_db

sys.stdout.reconfigure(encoding='utf-8')

if __name__ == "__main__":
    main()