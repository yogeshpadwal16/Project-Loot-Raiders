import os
import sys
import time
import re
import logging
import urllib.parse
import requests
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from config.settings import load_settings
from deal_engine.scorer import calculate_deal_score, should_publish_deal
from deal_engine.notifier import enqueue_alert

def process_deal_url(url: str, platform_hint: str = None) -> bool:
    """
    Expands, scrapes, scores, saves, and alerts a single product deal URL.
    Returns True if successfully processed, False otherwise.
    """
    logging.info(f"[Deal Processor] Initiating processing for URL: {url}")
    
    # 1. Expand shortened URLs / affiliate redirects dynamically
    expanded_url = url
    try:
        is_direct = ("amazon.in/dp/" in url.lower() or "amazon.in/gp/product/" in url.lower() or ("flipkart.com/" in url.lower() and "pid=" in url.lower()))
        if not is_direct:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
            # Use HEAD request for speed
            res = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
            if res.status_code >= 400 or res.url == url:
                # Fall back to GET with stream=True (only downloads headers, very fast)
                res = requests.get(url, headers=headers, allow_redirects=True, stream=True, timeout=10)
            expanded_url = res.url
            logging.info(f"[Deal Processor] URL expanded successfully: {url} -> {expanded_url}")
    except Exception as e:
        logging.warning(f"[Deal Processor] URL expansion failed: {e}")
        
    # 2. Extract Product ID and Platform
    platform = "generic"
    unique_id = str(int(time.time()))
    
    if "amazon.in" in expanded_url.lower():
        platform = "amazon"
        from utils.parser import extract_amazon_asin
        asin = extract_amazon_asin(expanded_url)
        if not asin:
            logging.warning(f"[Deal Processor] Failed to extract Amazon ASIN from: {expanded_url}")
            return False
        unique_id = asin
    elif "flipkart.com" in expanded_url.lower():
        platform = "flipkart"
        from utils.parser import extract_flipkart_pid
        pid = extract_flipkart_pid(expanded_url)
        if not pid:
            logging.warning(f"[Deal Processor] Failed to extract Flipkart PID from: {expanded_url}")
            return False
        unique_id = pid
    elif "myntra.com" in expanded_url.lower():
        platform = "myntra"
        # Myntra URLs usually have the ID in the path (e.g. /123456/buy)
        match = re.search(r'/(\d+)/buy', expanded_url)
        if match:
            unique_id = f"myntra_{match.group(1)}"
        else:
            unique_id = f"myntra_{str(hash(expanded_url))}"
    elif "meesho.com" in expanded_url.lower():
        platform = "meesho"
        # Meesho URLs usually end with /p/xxxxxx
        match = re.search(r'/p/([a-zA-Z0-9]+)', expanded_url)
        if match:
            unique_id = f"meesho_{match.group(1)}"
        else:
            unique_id = f"meesho_{str(hash(expanded_url))}"
    elif "ajio.com" in expanded_url.lower():
        platform = "ajio"
        unique_id = f"ajio_{str(hash(expanded_url))}"
    elif platform_hint:
        platform = platform_hint
        unique_id = f"{platform}_{str(hash(expanded_url))}"
        
    # 3. Check for duplicates / price-stability
    db = SessionLocal()
    try:
        latest = db.query(PriceHistory).filter_by(product_id=unique_id).order_by(PriceHistory.timestamp.desc()).first()
        if latest:
            # If we already have this product at the same price, skip scraping to save bandwidth
            time_diff = time.time() - latest.timestamp
            if time_diff < 1800: # 30 minutes threshold
                logging.info(f"[Deal Processor] Deal {unique_id} recently scanned {time_diff:.0f}s ago. Skipping.")
                return True
    except Exception as db_err:
        logging.error(f"[Deal Processor] Duplicate check error: {db_err}")
    finally:
        db.close()
        
    # 4. Scrape full details using selenium driver helper in loot_scraper
    from loot_scraper import scrape_product_details, verify_historical_low, save_deal_to_db
    
    try:
        scraped = scrape_product_details(expanded_url)
    except Exception as scrape_err:
        logging.error(f"[Deal Processor] Scraping failed for {expanded_url}: {scrape_err}")
        return False
        
    title = scraped.get("title", "Product Deal")
    price = scraped.get("price", 0)
    mrp = scraped.get("mrp", 0)
    img_url = scraped.get("image_url", "")
    rating = scraped.get("rating")
    reviews = scraped.get("reviews")
    has_bank_offer = scraped.get("has_bank_offer", False)
    
    if price == 0:
        logging.warning(f"[Deal Processor] Scraped price is 0. Skipping deal.")
        return False
        
    discount = 0.0
    if mrp > price:
        discount = ((mrp - price) / mrp) * 100.0
        
    # 4.5 Check if we already have this deal at the exact same price
    db = SessionLocal()
    try:
        latest = db.query(PriceHistory).filter_by(product_id=unique_id).order_by(PriceHistory.timestamp.desc()).first()
        if latest and latest.price == price:
            logging.info(f"[Deal Processor] Deal {unique_id} has unchanged price (₹{price}). Skipping duplicate competitor alert.")
            return True
    except Exception as db_err:
        logging.error(f"[Deal Processor] Price duplicate check error: {db_err}")
    finally:
        db.close()
        
    # 5. Format/Clean affiliate URL using custom routing rules
    settings = load_settings()
    final_url = expanded_url
    
    cuelinks_id = settings.get("cuelinks_pub_id", "").strip()
    earnkaro_id = settings.get("earnkaro_pub_id", "").strip()
    
    # Check if we should route this platform via third-party affiliate networks
    # Cuelinks/EarnKaro are great for general retailers (Ajio, Myntra, JioMart, Meesho, TataCliq, etc.)
    is_general_retailer = platform not in ["amazon", "flipkart"]
    
    if is_general_retailer and cuelinks_id:
        final_url = f"https://cuelinks.com/link?pub_id={cuelinks_id}&url={urllib.parse.quote(expanded_url)}"
    elif is_general_retailer and earnkaro_id:
        final_url = f"https://earnkaro.com/sharedeal?dl={urllib.parse.quote(expanded_url)}&pub_id={earnkaro_id}"
    else:
        # Direct affiliate channels fallback
        if platform == "amazon":
            final_url = f"https://www.amazon.in/dp/{unique_id}?tag={settings.get('amazon_tag', 'lootraiders-21')}"
        elif platform == "flipkart":
            final_url = f"https://www.flipkart.com/product/p/itm?pid={unique_id}&affid={settings.get('flipkart_affid', 'YOUR_FLIPKART_AFFILIATE_ID')}"
        elif platform == "myntra":
            # If Myntra is not routed via Cuelinks/EarnKaro, fall back to direct FK affiliate tag wrapper
            myntra_affid = settings.get("flipkart_affid", "YOUR_FLIPKART_AFFILIATE_ID")
            sep = "&" if "?" in expanded_url else "?"
            final_url = f"{expanded_url}{sep}affid={myntra_affid}"
        
    # 6. Apply filter thresholds (min_price, min_savings, blocklist)
    blocklist = settings.get("blocklist_keywords", [])
    title_lower = title.lower()
    for b_word in blocklist:
        if b_word.lower().strip() in title_lower:
            logging.info(f"[Deal Processor] Skipping blocklisted deal: {title[:35]}... (Matched: '{b_word}')")
            return False
            
    min_price = settings.get("min_deal_price", 149)
    min_savings = settings.get("min_deal_savings", 100)
    savings = mrp - price
    
    if price < min_price or savings < min_savings:
        logging.info(f"[Deal Processor] Skipping cheap deal: {title[:35]}... (Price: ₹{price}, Savings: ₹{savings})")
        return False
        
    # 7. Check Price Trend History
    is_verified_low = True
    try:
        from utils.playwright_adapter import get_playwright_driver
        temp_driver = get_playwright_driver(settings)
        try:
            is_verified_low = verify_historical_low(temp_driver, expanded_url, price, unique_id, discount)
        finally:
            temp_driver.quit()
    except Exception as verify_err:
        logging.warning(f"[Deal Processor] Price verification failed, defaulting to True: {verify_err}")
        is_verified_low = True
        
    # 8. Calculate score and save
    deal_score = calculate_deal_score(
        platform, price, mrp, discount, is_verified_low, False, 
        product_id=unique_id, title=title, rating=rating, reviews=reviews, 
        has_bank_offer=has_bank_offer
    )
    save_deal_to_db(platform, title, price, mrp, discount, img_url, final_url, is_verified_low, unique_id, deal_score)
    
    # 9. Dispatch alerts
    # Competitor mirror deals are broadcasted immediately with no score restrictions
    enqueue_alert(platform, title, price, mrp, discount, img_url, final_url, is_verified_low, deal_score, unique_id)
    logging.info(f"[Deal Processor] Competitor deal alert successfully dispatched for: {title[:35]}")
        
    return True
