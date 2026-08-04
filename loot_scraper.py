import sys

# Re-export key functions for backward compatibility with import references (e.g. from deal_processor.py)
# Real Product Photo & Option 1 Template & Native Photo Fix Directive Applied
from core.engine import main, scrape_product_details
from database.operations import verify_historical_low, save_deal_to_db

sys.stdout.reconfigure(encoding='utf-8')

if __name__ == "__main__":
    main()