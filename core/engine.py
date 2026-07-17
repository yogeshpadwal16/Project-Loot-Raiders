import os
import re
import sys
import time
import json
import logging
from concurrent.futures import ThreadPoolExecutor

# Core database and configuration imports
from database.db_session import SessionLocal, init_db
from knowledge_base.models import Product, PriceHistory, ClickLog, SelectorMatrix
from config.settings import load_settings
from deal_engine.scorer import calculate_deal_score, should_publish_deal
from deal_engine.notifier import start_notifier, enqueue_alert
from deal_engine.bot_listener import start_telegram_bot_listener
from utils.playwright_adapter import get_playwright_driver

# Retailer Scraper Plugins
from plugins.amazon import AmazonRetailerPlugin
from plugins.flipkart import FlipkartRetailerPlugin
from plugins.generic import GenericRetailerPlugin

# Operations & Utilities
from database.operations import initialize_database_selectors, save_deal_to_db, verify_historical_low
from utils.zombie import run_zombie_cleanup
from web.server import start_api_server

RETAILER_PLUGINS = {
    "amazon": AmazonRetailerPlugin(),
    "flipkart": FlipkartRetailerPlugin(),
    "myntra": GenericRetailerPlugin("myntra"),
    "ajio": GenericRetailerPlugin("ajio"),
    "meesho": GenericRetailerPlugin("meesho"),
    "tatacliq": GenericRetailerPlugin("tatacliq"),
    "jiomart": GenericRetailerPlugin("jiomart")
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
LOG_FILE = os.path.join(BASE_DIR, "execution.log")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
for h in logger.handlers[:]:
    logger.removeHandler(h)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==========================================
# SYSTEM STATE FOR WEB DASHBOARD CONTROL
# ==========================================
scraper_state = {
    "is_running": True,          # Background scanning enabled
    "scans_completed": 0,        # Count of completed scan loops
    "last_scan_time": 0,         # Epoch timestamp of last completed loop
    "uptime_start": time.time(), # Start timestamp
    "scan_trigger": False,       # External trigger for manual scan
    "crawler_health": {}         # Platform monitoring logs
}

def init_driver():
    settings = load_settings()
    return get_playwright_driver(settings)

# ==========================================
# CORE SCANNERS MAIN LOOP
# ==========================================
def scrape_platform(platform: str, config: dict, history: set):
    if not scraper_state["is_running"] and not scraper_state["scan_trigger"]:
        return
        
    logging.info(f"Scanning target feed stream: {platform.upper()} (Multi-threaded)")
    driver = None
    
    # Initialize health state for this crawler
    if platform not in scraper_state["crawler_health"]:
        scraper_state["crawler_health"][platform] = {
            "status": "Starting",
            "consecutive_failures": 0,
            "success_count": 0,
            "fail_count": 0,
            "last_success": 0,
            "last_failure": 0,
            "last_error": ""
        }
    health = scraper_state["crawler_health"][platform]
    
    # 1. Resolve matched plugin for platform
    plugin = None
    for key, instance in RETAILER_PLUGINS.items():
        if key in platform.lower():
            plugin = instance
            break
            
    if not plugin:
        logging.warning(f"No suitable retailer plugin registered for platform: {platform}")
        health["status"] = "Offline"
        health["last_error"] = "Plugin not found"
        return
        
    settings = load_settings()
    
    try:
        driver = init_driver()
        driver.set_page_load_timeout(30)
        
        # 2. Delegate extraction to plugin
        start_time = time.time()
        extracted_deals = plugin.extract_deals(driver, config, settings)
        elapsed = time.time() - start_time
        logging.info(f"Plugin [{plugin.retailer_id}] extracted {len(extracted_deals)} deal candidates in {elapsed:.2f}s for platform: {platform}")
        
        # Update health based on extraction results
        if len(extracted_deals) > 0:
            health["status"] = "Healthy"
            health["consecutive_failures"] = 0
            health["success_count"] += 1
            health["last_success"] = time.time()
        else:
            health["consecutive_failures"] += 1
            health["fail_count"] += 1
            health["last_failure"] = time.time()
            health["last_error"] = "0 deals extracted (possible selector drift or no deals available)"
            if health["consecutive_failures"] >= 3:
                health["status"] = "Degraded"
                
        # 3. Process extracted deal candidates
        for deal in extracted_deals:
            if not scraper_state["is_running"] and not scraper_state["scan_trigger"]:
                logging.info(f"Scraper execution halted by user request on stream {platform}.")
                break
                
            unique_id = deal["id"]
            price = deal["price"]
            mrp = deal["mrp"]
            discount = deal["discount"]
            title = deal["title"]
            img_url = deal["image_url"]
            from utils.affiliate import get_best_affiliate_url
            final_url = get_best_affiliate_url(deal["url"], platform, settings)
            is_lightning = deal["is_lightning"]
            rating = deal.get("rating")
            reviews = deal.get("reviews")
            has_bank_offer = deal.get("has_bank_offer", False)
            
            # Fetch latest price from DB to see if it's a duplicate or if the price changed
            price_changed = True
            is_price_drop = False
            db = SessionLocal()
            try:
                latest = db.query(PriceHistory).filter_by(product_id=unique_id).order_by(PriceHistory.timestamp.desc()).first()
                if latest:
                    if latest.price == price:
                        price_changed = False
                        is_price_drop = False
                    else:
                        price_changed = True
                        is_price_drop = price < latest.price
                else:
                    # New product is treated as a price drop
                    price_changed = True
                    is_price_drop = True
            except Exception as db_err:
                logging.error(f"Error querying latest price for duplicate check: {db_err}")
            finally:
                db.close()
                
            if not price_changed:
                continue
                
            # Filter out low-value cheap products or minor savings spams
            settings = load_settings()
            
            # Title keyword blocklist check
            blocklist = settings.get("blocklist_keywords", [])
            title_lower = title.lower()
            blocked_match = None
            for b_word in blocklist:
                if b_word.lower().strip() in title_lower:
                    blocked_match = b_word
                    break
            if blocked_match:
                logging.info(f"Skipping blocklisted accessory deal: {title[:35]}... (Matched: '{blocked_match}')")
                continue
                
            min_price = settings.get("min_deal_price", 299)
            min_savings = settings.get("min_deal_savings", 250)
            savings = mrp - price
            
            if price < min_price or savings < min_savings:
                logging.info(f"Skipping basic/cheap deal: {title[:35]}... (Price: ₹{price}, Savings: ₹{savings})")
                continue
                
            # Extract base URL to check price tracker history
            clean_url = final_url.split("?")[0].split("&")[0]
            is_verified_low = verify_historical_low(driver, clean_url, price, unique_id, discount)
            
            # Calculate final AI Deal score
            deal_score = calculate_deal_score(
                platform, price, mrp, discount, is_verified_low, is_lightning, 
                product_id=unique_id, title=title, rating=rating, reviews=reviews, 
                has_bank_offer=has_bank_offer
            )
            
            # Persist inside Knowledge Base database
            save_deal_to_db(platform, title, price, mrp, discount, img_url, final_url, is_verified_low, unique_id, deal_score)
            history.add(unique_id)
            
            # Dispatch notifications if score is above the configured threshold and it's a price drop (or new product)
            if should_publish_deal(platform, deal_score) and is_price_drop:
                bank_offers = []
                coupon_detail = ""
                review_grade = "N/A"
                
                try:
                    enriched = scrape_product_details(final_url)
                    if enriched:
                        img_url = enriched.get("image_url") or img_url
                        bank_offers = enriched.get("bank_offers", [])
                        coupon_detail = enriched.get("coupon_detail", "")
                        review_grade = enriched.get("review_grade", "N/A")
                except Exception as enrich_err:
                    logging.warning(f"Failed to enrich scraped deal {unique_id} before dispatch: {enrich_err}")
                    
                auto_cart_url = None
                try:
                    from utils.affiliate import generate_auto_cart_url
                    settings = load_settings()
                    auto_cart_url = generate_auto_cart_url(final_url, platform, settings)
                except:
                    pass
                    
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
                time.sleep(0.5)
            else:
                if not is_price_drop:
                    logging.info(f"Skipping deal broadcast: {title[:35]}... (Price increased from last scan)")
                else:
                    logging.info(f"Skipping deal broadcast: {title[:35]}... (Score: {deal_score:.1f} below threshold)")
                
    except Exception as out_err:
        logging.error(f"Scraper interface failure on stream {platform}: {out_err}")
        if platform in scraper_state["crawler_health"]:
            health = scraper_state["crawler_health"][platform]
            health["consecutive_failures"] += 1
            health["fail_count"] += 1
            health["last_failure"] = time.time()
            health["last_error"] = str(out_err)
            health["status"] = "Offline"
    finally:
        if driver:
            try: driver.quit()
            except: pass

def sync_database_to_json():
    db = SessionLocal()
    try:
        products = db.query(Product).all()
        deals = []
        for p in products:
            latest_price = db.query(PriceHistory).filter_by(product_id=p.id).order_by(PriceHistory.timestamp.desc()).first()
            if not latest_price:
                continue
            
            click_count = db.query(ClickLog).filter_by(product_id=p.id).count()
            
            # Fetch recent price history points for client-side Chart rendering
            history_query = db.query(PriceHistory).filter_by(product_id=p.id).order_by(PriceHistory.timestamp.desc()).limit(15).all()
            history_query.reverse()
            price_history = [{"price": h.price, "timestamp": h.timestamp} for h in history_query]
            
            deals.append({
                "id": p.id,
                "platform": p.platform,
                "title": p.title,
                "price": latest_price.price,
                "mrp": latest_price.mrp,
                "discount": latest_price.discount,
                "image_url": p.image_url,
                "url": p.url,
                "is_verified_low": latest_price.is_verified_low,
                "deal_score": latest_price.deal_score,
                "timestamp": latest_price.timestamp,
                "clicks": click_count,
                "price_history": price_history
            })
        deals.sort(key=lambda x: x["timestamp"], reverse=True)
        deals = deals[:300]
        
        deals_file = os.path.join(DASHBOARD_DIR, "deals_history.json")
        with open(deals_file, 'w', encoding='utf-8') as f:
            json.dump(deals, f, indent=2)
            
        omega = {p.id: time.time() for p in products}
        history_file = os.path.join(BASE_DIR, "omega_history.json")
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(omega, f, indent=2)
            
        logging.info("SQLite database synchronized to static JSON files successfully.")
    except Exception as e:
        logging.error(f"Failed to sync database to JSON exports: {e}")
    finally:
        db.close()

def scrape_product_details(url: str) -> dict:
    from selenium.webdriver.common.by import By
    import time
    import re
    import json
    
    driver = init_driver()
    try:
        driver.get(url)
        time.sleep(5)  # Wait for dynamic JS content to fully load
        
        title = ""
        price = 0
        mrp = 0
        image_url = ""
        platform = "generic"
        
        url_lower = url.lower()
        if "amazon" in url_lower:
            platform = "amazon"
        elif "flipkart" in url_lower:
            platform = "flipkart"
        elif "myntra" in url_lower:
            platform = "myntra"
        elif "ajio" in url_lower:
            platform = "ajio"
        elif "meesho" in url_lower:
            platform = "meesho"
        elif "tatacliq" in url_lower:
            platform = "tatacliq"
        elif "jiomart" in url_lower:
            platform = "jiomart"
            
        def clean_number(txt):
            try:
                txt = txt.replace(',', '').split('.')[0]
                nums = re.findall(r'\d+', txt)
                if nums:
                    return int(nums[0])
            except:
                pass
            return 0

        # 1. Try JSON-LD Structured Data (Most robust across layouts)
        try:
            ld_scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
            for script in ld_scripts:
                try:
                    js_text = script.get_attribute("textContent").strip()
                    data = json.loads(js_text)
                    
                    if isinstance(data, list):
                        items = data
                    else:
                        items = [data]
                        
                    for item in items:
                        # Sometimes structured data is nested in graph
                        graph = item.get("@graph", [])
                        if graph and isinstance(graph, list):
                            for g_item in graph:
                                items.append(g_item)
                                
                        if item.get("@type") == "Product" or "Product" in str(item.get("@type")):
                            if not title:
                                title = item.get("name")
                            if not image_url:
                                img = item.get("image")
                                if isinstance(img, list) and img:
                                    image_url = img[0]
                                elif isinstance(img, dict) and img.get("url"):
                                    image_url = img.get("url")
                                elif isinstance(img, str):
                                    image_url = img
                            
                            offers = item.get("offers")
                            if offers:
                                if isinstance(offers, list) and offers:
                                    offers = offers[0]
                                price_val = offers.get("price")
                                if price_val and not price:
                                    price = clean_number(str(price_val))
                                mrp_val = offers.get("priceSpecification", {}).get("price") or offers.get("highPrice")
                                if mrp_val and not mrp:
                                    mrp = clean_number(str(mrp_val))
                except:
                    pass
        except:
            pass

        # 2. Try Open Graph & Twitter meta tags fallback
        try:
            if not title:
                for selector in ["meta[property='og:title']", "meta[name='twitter:title']", "meta[name='title']"]:
                    try:
                        title = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("content").strip()
                        if title: break
                    except: pass
            if not image_url:
                for selector in ["meta[property='og:image']", "meta[name='twitter:image']"]:
                    try:
                        image_url = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("content").strip()
                        if image_url: break
                    except: pass
            if not price:
                for selector in ["meta[property='product:price:amount']", "meta[property='og:price:amount']"]:
                    try:
                        p_val = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("content")
                        price = clean_number(p_val)
                        if price: break
                    except: pass
        except:
            pass

        # 3. Platform-specific CSS Selector Fallbacks
        # Titles
        if not title:
            selectors = []
            if platform == "amazon":
                selectors = ["#productTitle", "span#productTitle", ".qa-title-text"]
            elif platform == "flipkart":
                selectors = [".VU-ZEg", "span.B_NuCI", "h1.yrwE28", "h1 span"]
            elif platform == "myntra":
                selectors = [".pdp-title", ".pdp-name"]
            elif platform == "ajio":
                selectors = ["h1.prod-name", "h2.brand-name"]
            elif platform == "meesho":
                selectors = ["span[class*='ProductTitle']", "h3[class*='ProductTitle']"]
            elif platform == "tatacliq":
                selectors = ["h1.ProductDetails__name"]
            elif platform == "jiomart":
                selectors = ["div.product-title", "h1.title"]
                
            for selector in selectors:
                try:
                    title = driver.find_element(By.CSS_SELECTOR, selector).text.strip()
                    if title: break
                except: pass
                
        # Generic Title Fallback
        if not title:
            try: title = driver.find_element(By.TAG_NAME, "h1").text.strip()
            except: pass
            
        # Prices
        if not price:
            selectors = []
            if platform == "amazon":
                selectors = [".a-price-whole", "span.a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice", ".apexPriceToPay span.a-offscreen", ".a-color-price"]
            elif platform == "flipkart":
                selectors = [".Nx9w7A", "._30jeq3", "div._30jeq3._16JkK1", "div.hlbKVd"]
            elif platform == "myntra":
                selectors = ["span.pdp-price strong", ".pdp-price"]
            elif platform == "ajio":
                selectors = ["div.prod-sp", ".prod-sp"]
            elif platform == "meesho":
                selectors = ["h4[class*='PriceText']", "span[class*='PriceText']"]
            elif platform == "tatacliq":
                selectors = ["h3.ProductDetails__price"]
            elif platform == "jiomart":
                selectors = ["span.prod-price", "span.price", ".price"]
                
            for selector in selectors:
                try:
                    p_text = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent")
                    price = clean_number(p_text)
                    if price > 0: break
                except: pass
                
        # MRPs
        if not mrp:
            selectors = []
            if platform == "amazon":
                selectors = ["span.a-price.a-text-price span.a-offscreen", "#listPrice", "#priceblock_listprice", "span.a-list-price"]
            elif platform == "flipkart":
                selectors = [".y3NYbL", "._3I9_ww", "div._3I9_ww"]
            elif platform == "myntra":
                selectors = ["span.pdp-mrp", ".pdp-mrp"]
            elif platform == "ajio":
                selectors = ["span.prod-cp", ".prod-cp", ".strike"]
            elif platform == "meesho":
                selectors = ["p[class*='OriginalPriceText']", "span[class*='OriginalPriceText']", "span.mrp"]
            elif platform == "tatacliq":
                selectors = ["span.ProductDetails__mrp"]
            elif platform == "jiomart":
                selectors = ["span.prod-mrp", "span.strike", ".strike"]
                
            for selector in selectors:
                try:
                    m_text = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent")
                    mrp = clean_number(m_text)
                    if mrp > 0: break
                except: pass
                
        # Images
        if not image_url:
            selectors = []
            if platform == "amazon":
                selectors = ["#landingImage", "#imgBlkFront", ".imgTagWrapper img", "#main-image"]
            elif platform == "flipkart":
                selectors = ["img.DByoR4", "img._396cs4", "img.jfZQxf", "div.CXW8mj img"]
            elif platform == "myntra":
                selectors = ["img.pdp-image", ".image-grid-image"]
            elif platform == "ajio":
                selectors = ["img.img-alignment", ".img-container img"]
            elif platform == "meesho":
                selectors = ["img[class*='ProductImage']"]
            elif platform == "tatacliq":
                selectors = ["img.ProductDetails__image"]
            elif platform == "jiomart":
                selectors = ["img#product-image", "img.product-image"]
                
            for selector in selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    for attr in ["data-src", "data-original", "data-img-src", "src"]:
                        val = element.get_attribute(attr)
                        if val and val.startswith("http"):
                            image_url = val
                            break
                    if image_url: break
                except: pass

        # Fallback image extraction: scan for any large product image on page
        if not image_url:
            try:
                images = driver.find_elements(By.TAG_NAME, "img")
                for img in images:
                    src = img.get_attribute("src")
                    w = int(img.get_attribute("width") or 0)
                    h = int(img.get_attribute("height") or 0)
                    if src and ("product" in src.lower() or "media" in src.lower() or "dp" in src.lower() or w > 200 or h > 200):
                        image_url = src
                        break
            except: pass
            
        # 5. Clean up & validate data values
        if not title:
            title = "Manual Deal Product"
        else:
            title = re.sub(r'\s+', ' ', title).strip()
            
        if price > 0 and mrp == 0:
            mrp = int(price * 1.35)
        elif mrp > 0 and price == 0:
            price = int(mrp * 0.7)
        elif price > mrp:
            price, mrp = mrp, price
            
        body_text = ""
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
        except:
            pass
            
        from utils.parser import extract_rating_and_reviews, detect_bank_offers
        rating, reviews = extract_rating_and_reviews(body_text)
        has_bank_offer = detect_bank_offers(body_text)
        
        # Scrape specific bank offers and coupons
        bank_offers = []
        coupon_detail = ""
        try:
            if platform == "amazon":
                offer_elems = driver.find_elements(By.CSS_SELECTOR, "#sopp-offers-list-content, .sopp-offers-list, [id*='bankOffer']")
                for elem in offer_elems:
                    txt = elem.text.strip()
                    if txt and "bank" in txt.lower():
                        lines = [l.strip() for l in txt.split('\n') if l.strip()]
                        for l in lines:
                            if any(x in l.lower() for x in ["sbi", "hdfc", "icici", "axis", "onecard", "discount", "cashback"]):
                                if l not in bank_offers:
                                    bank_offers.append(l)
                coupon_elems = driver.find_elements(By.CSS_SELECTOR, "#couponBadge, .coupon-badge, #clip-coupon")
                for elem in coupon_elems:
                    txt = elem.text.strip()
                    if txt:
                        coupon_detail = txt
                        break
            elif platform == "flipkart":
                offer_elems = driver.find_elements(By.CSS_SELECTOR, ".wtv7sz, .x3G5F3, ._2-gKeT, .promo-desc-text")
                for elem in offer_elems:
                    txt = elem.text.strip()
                    if txt:
                        lines = [l.strip() for l in txt.split('\n') if l.strip()]
                        for l in lines:
                            if "bank offer" in l.lower() or any(x in l.lower() for x in ["sbi", "hdfc", "icici", "axis", "onecard"]):
                                if l not in bank_offers:
                                    bank_offers.append(l)
                coupon_elems = driver.find_elements(By.CSS_SELECTOR, ".coupon-badge, .W44C-B, [class*='coupon']")
                for elem in coupon_elems:
                    txt = elem.text.strip()
                    if txt and "coupon" in txt.lower():
                        coupon_detail = txt
                        break
        except Exception as promo_err:
            logging.warning(f"Promo scraping failed for {unique_id}: {promo_err}")

        # Compute Review Trust Grade (Feature 16)
        review_grade = "N/A"
        if rating:
            if rating >= 4.3:
                review_grade = "A"
            elif rating >= 4.0:
                review_grade = "B"
            elif rating >= 3.7:
                review_grade = "C"
            elif rating >= 3.3:
                review_grade = "D"
            else:
                review_grade = "F"
                
            if reviews and reviews > 1000 and review_grade in ["A", "B", "C"]:
                review_grade += "+"
            elif reviews and reviews < 15:
                review_grade += " (Low Sample)"
            
        return {
            "platform": platform,
            "title": title,
            "price": price,
            "mrp": mrp,
            "image_url": image_url,
            "rating": rating,
            "reviews": reviews,
            "has_bank_offer": has_bank_offer or bool(bank_offers),
            "bank_offers": bank_offers[:3],
            "coupon_detail": coupon_detail,
            "review_grade": review_grade
        }
    finally:
        driver.quit()

def main():
    import signal
    def handle_termination(signum, frame):
        logging.warning(f"Termination signal {signum} received. Turning pipeline off safely...")
        try:
            from deal_engine.channel_mirror import stop_channel_mirror
            stop_channel_mirror()
        except Exception as e:
            logging.error(f"Error stopping channel mirror on signal: {e}")
        # Terminate process
        sys.exit(0)
        
    signal.signal(signal.SIGINT, handle_termination)
    signal.signal(signal.SIGTERM, handle_termination)

    # 0. Clean up zombie chrome and python processes
    run_zombie_cleanup()
    
    # 1. Initialize SQLite Database Tables & Seed Selectors
    init_db()
    initialize_database_selectors()
    
    # 2. Start Asynchronous Notification Queue Thread
    start_notifier()
    
    # 3. Start Asynchronous Telegram Bot Updates Listener
    start_telegram_bot_listener()
    
    single_run = "--single-run" in sys.argv or os.environ.get('GITHUB_ACTIONS') == 'true'
    
    if not single_run:
        start_api_server(5555)
        
        # 4. Start Asynchronous Competitor Mirroring Listener
        try:
            from deal_engine.channel_mirror import start_channel_mirror
            start_channel_mirror()
        except Exception as mirror_err:
            logging.error(f"Failed to start Channel Mirroring bot: {mirror_err}")
            
        # 5. Start Asynchronous Catalog Priority Monitor
        try:
            from deal_engine.catalog_monitor import start_catalog_monitor
            start_catalog_monitor()
        except Exception as catalog_err:
            logging.error(f"Failed to start Catalog Monitor: {catalog_err}")
            
        # 5.5 Start Asynchronous Supermarket Loot Drop Monitor (Feature 28)
        try:
            from deal_engine.supermarket_monitor import start_supermarket_monitor
            start_supermarket_monitor()
        except Exception as supermarket_err:
            logging.error(f"Failed to start Supermarket Monitor: {supermarket_err}")
            
        logging.info("Master Engine Activated. Scanners operating.")
    else:
        logging.info("Single-run execution mode activated (Cloud/CI environment).")
    
    try:
        while True:
            if not single_run:
                if not scraper_state["is_running"] and not scraper_state["scan_trigger"]:
                    time.sleep(1)
                    continue
                    
                if scraper_state["scan_trigger"]:
                    logging.info("Manual scan triggered via REST API. Starting execute sequence.")
                    scraper_state["scan_trigger"] = False
                
            try:
                db = SessionLocal()
                try:
                    # Query active platform matrices from SQLite
                    matrices = db.query(SelectorMatrix).all()
                    matrix = {m.platform: {
                        "url": m.url,
                        "card_selector": m.card_selector,
                        "title_selector": m.title_selector,
                        "link_selector": m.link_selector,
                        "image_selector": m.image_selector
                    } for m in matrices}
                    
                    # Fetch all existing product IDs to track duplicates
                    products = db.query(Product.id).all()
                    history = {p[0] for p in products}
                finally:
                    db.close()
                
                settings = load_settings()
                concurrency = settings.get("scraper_concurrency", 3)
                logging.info(f"Initiating scraping scan frame using {concurrency} parallel workers.")
                
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = []
                    for platform, config in matrix.items():
                        futures.append(executor.submit(scrape_platform, platform, config, history))
                    
                    for fut in futures:
                        try:
                            fut.result()
                        except Exception as thread_err:
                            logging.error(f"Thread execution error: {thread_err}")
                
                # Export SQLite state to JSON for static host environment (like GitHub Pages)
                sync_database_to_json()
                
                if single_run:
                    try:
                        from deal_engine.channel_mirror import run_mirror_single_run
                        logging.info("Initiating single-run competitor channel mirror scan...")
                        run_mirror_single_run()
                    except Exception as mirror_err:
                        logging.error(f"Failed to execute single-run channel mirror scan: {mirror_err}")
                
                scraper_state["scans_completed"] += 1
                scraper_state["last_scan_time"] = time.time()
                logging.info("Inter-stream sequence frame complete. Pausing current execution cycle.")
                
            except Exception as loop_err:
                logging.error(f"Error in main scanner loop: {loop_err}")
                
            if single_run:
                logging.info("Waiting for notification queue to finish dispatching...")
                try:
                    from deal_engine.notifier import notification_queue
                    notification_queue.join()
                    logging.info("All notifications successfully dispatched.")
                except Exception as queue_err:
                    logging.error(f"Error waiting for notification queue: {queue_err}")
                logging.info("Single-run execution complete. Exiting scraper loop.")
                break
                
            for _ in range(60):
                if not scraper_state["is_running"] or scraper_state["scan_trigger"]:
                    break
                time.sleep(1)
                
    except KeyboardInterrupt:
        logging.warning("SIGINT operational interrupt recognized. Turning pipeline off safely.")
        try:
            from deal_engine.channel_mirror import stop_channel_mirror
            stop_channel_mirror()
        except Exception:
            pass
