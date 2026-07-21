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
import threading

processing_lock = threading.Lock()
processing_products = set()

def extract_store_url_from_competitor_landing_page(landing_url: str) -> str:
    """
    Scans a competitor landing page/blog post to locate direct outbound store product links.
    Filters out generic site links and ranks them to pick the actual product deal URL.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
        res = requests.get(landing_url, headers=headers, timeout=10)
        if res.status_code == 200:
            html = res.text
            hrefs = re.findall(r'href=["\'](https?://[^\s"\']+)["\']', html)
            store_domains = ["amazon.in", "flipkart.com", "myntra.com", "ajio.com", "meesho.com", "tatacliq.com", "jiomart.com"]
            
            candidates = []
            for href in hrefs:
                href_lower = href.lower()
                if any(domain in href_lower for domain in store_domains):
                    # Filter out social and sharing links
                    if any(bad in href_lower for bad in ["facebook.com", "twitter.com", "whatsapp.com", "telegram.me", "t.me", "pinterest.com"]):
                        continue
                    
                    # Exclude generic help, cart, rewards, and homepages
                    if any(x in href_lower for x in ["/h/rewards", "/gp/help", "/gp/cart", "/gp/css/order-history", "/gp/prime", "/gp/navigation", "amazon.in/gp/goldbox", "amazon.in/gp/today", "amazon.in/s?"]):
                        continue
                        
                    # Check if link points directly to a product
                    has_product_id = any(p in href_lower for p in ["/dp/", "/gp/product/", "/p/", "pid=", "/pdp/", "/p/"])
                    score = 10 if has_product_id else 1
                    
                    # If it has a redirect parameters wrapper (e.g. ?rto=... or ?url=...), parse and extract nested link
                    nested_url = None
                    parsed = urllib.parse.urlparse(href)
                    queries = urllib.parse.parse_qs(parsed.query)
                    for k, vals in queries.items():
                        for val in vals:
                            if val.startswith("http") and any(d in val.lower() for d in store_domains):
                                nested_url = val
                                break
                                
                    target_url = nested_url or href
                    # Double check direct indicators on nested url
                    if nested_url:
                        has_product_id_nested = any(p in nested_url.lower() for p in ["/dp/", "/gp/product/", "/p/", "pid=", "/pdp/", "/p/"])
                        score += 8 if has_product_id_nested else 3
                        
                    # Add target retailer keyword matching bonus (+15 points)
                    for domain in store_domains:
                        domain_name = domain.split('.')[0]
                        if domain_name in landing_url.lower():
                            if domain_name in target_url.lower():
                                score += 15
                                break
                                
                    candidates.append({
                        "url": target_url,
                        "score": score
                    })
                    
            if candidates:
                candidates.sort(key=lambda x: x["score"], reverse=True)
                logging.info(f"[Deal Processor] Extracted store link candidates: {[c['url'] for c in candidates[:3]]}")
                return candidates[0]["url"]
    except Exception as e:
        logging.warning(f"[Deal Processor] Outbound link extraction failed for {landing_url}: {e}")
    return None

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
        
    # Check if expanded URL points to a competitor blog/landing page and extract store link from it
    store_domains = ["amazon.in", "flipkart.com", "myntra.com", "ajio.com", "meesho.com", "tatacliq.com", "jiomart.com"]
    is_competitor_landing = not any(d in expanded_url.lower() for d in store_domains)
    if is_competitor_landing:
        logging.info(f"[Deal Processor] Non-store URL detected. Scanning landing page for outbound deal links: {expanded_url}")
        extracted_store_url = extract_store_url_from_competitor_landing_page(expanded_url)
        if extracted_store_url:
            logging.info(f"[Deal Processor] Extracted direct store link from landing page: {extracted_store_url}")
            expanded_url = extracted_store_url
            # Expand again in case the extracted store link itself is a shortened/redirect link
            try:
                if not any(expanded_url.lower().startswith(x) for x in ["http://www.amazon.in/dp/", "https://www.amazon.in/dp/", "http://amazon.in/dp/", "https://amazon.in/dp/"]):
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
                    res = requests.head(expanded_url, headers=headers, allow_redirects=True, timeout=10)
                    if res.status_code >= 400 or res.url == expanded_url:
                        res = requests.get(expanded_url, headers=headers, allow_redirects=True, stream=True, timeout=10)
                    expanded_url = res.url
                    logging.info(f"[Deal Processor] Extracted store URL expanded successfully to: {expanded_url}")
            except Exception as expand_err:
                logging.warning(f"[Deal Processor] Extracted store URL expansion failed: {expand_err}")
        
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
        
    global processing_products
    with processing_lock:
        if unique_id in processing_products:
            logging.info(f"[Deal Processor] Product {unique_id} is already being processed. Skipping concurrent duplicate.")
            return True
        processing_products.add(unique_id)
        
    try:
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
            
        # 4. Scrape full details using selenium driver helper directly from core/database modules
        from core.engine import scrape_product_details
        from database.operations import verify_historical_low, save_deal_to_db
        
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
            
        # 5. Format/Clean affiliate URL using custom routing rules (Feature 11: Yield Maximizer & Feature 12: Auto-Cart)
        from utils.affiliate import get_best_affiliate_url, generate_auto_cart_url
        settings = load_settings()
        final_url = get_best_affiliate_url(expanded_url, platform, settings)
        auto_cart_url = generate_auto_cart_url(expanded_url, platform, settings)
            
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
        bank_offers = scraped.get("bank_offers", [])
        coupon_detail = scraped.get("coupon_detail", "")
        review_grade = scraped.get("review_grade", "N/A")
        
        enqueue_alert(
            platform=platform,
            title=title,
            price=price,
            mrp=mrp,
            discount=discount,
            img_url=img_url,
            final_url=final_url,
            is_verified_low=is_verified_low,
            deal_score=deal_score,
            unique_id=unique_id,
            bank_offers=bank_offers,
            coupon_detail=coupon_detail,
            review_grade=review_grade,
            auto_cart_url=auto_cart_url
        )
        logging.info(f"[Deal Processor] Competitor deal alert successfully dispatched for: {title[:35]}")
            
        return True
    finally:
        with processing_lock:
            if unique_id in processing_products:
                processing_products.remove(unique_id)
