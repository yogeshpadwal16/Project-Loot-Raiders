import os
import re
import sys
import time
import json
import logging
import urllib.parse
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from concurrent.futures import ThreadPoolExecutor

# Core database and configurations imports
from database.db_session import SessionLocal, init_db
from knowledge_base.models import Product, PriceHistory, ClickLog, SelectorMatrix
from config.settings import load_settings, save_settings
from deal_engine.scorer import calculate_deal_score, should_publish_deal
from deal_engine.notifier import start_notifier, enqueue_alert
from deal_engine.bot_listener import start_telegram_bot_listener

# Retailer Scraper Plugins
from plugins.amazon import AmazonRetailerPlugin
from plugins.flipkart import FlipkartRetailerPlugin
from plugins.generic import GenericRetailerPlugin

RETAILER_PLUGINS = {
    "amazon": AmazonRetailerPlugin(),
    "flipkart": FlipkartRetailerPlugin(),
    "myntra": GenericRetailerPlugin("myntra"),
    "ajio": GenericRetailerPlugin("ajio"),
    "meesho": GenericRetailerPlugin("meesho"),
    "tatacliq": GenericRetailerPlugin("tatacliq"),
    "jiomart": GenericRetailerPlugin("jiomart")
}

sys.stdout.reconfigure(encoding='utf-8')

# ==========================================
# ROOT SYSTEM MATRIX PATHING
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
LOG_FILE = os.path.join(BASE_DIR, "execution.log")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
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
    "scan_trigger": False        # External trigger for manual scan
}

def initialize_database_selectors():
    db = SessionLocal()
    try:
        default_matrix = {
            "amazon_master_lightning_deals": {
                "url": "https://www.amazon.in/gp/goldbox?pct-off=35-",
                "card_selector": "div[data-testid='product-card'], div[class*='ProductCard-module__card']",
                "title_selector": "span.a-truncate-full, .a-truncate-full",
                "link_selector": "a[data-testid='product-card-link'], a.a-link-normal",
                "image_selector": "img[class*='ProductCardImage-module__image'], img"
            },
            "amazon_sitewide_search_deals": {
                "url": "https://www.amazon.in/s?k=deals+of+the+day&pct-off=40-",
                "card_selector": "div[data-component-type='s-search-result']",
                "title_selector": "h2 a span",
                "link_selector": "a.a-link-normal",
                "image_selector": "img.s-image"
            },
            "amazon_electronics_deals": {
                "url": "https://www.amazon.in/s?k=electronics&pct-off=30-",
                "card_selector": "div[data-component-type='s-search-result']",
                "title_selector": "h2 a span",
                "link_selector": "a.a-link-normal",
                "image_selector": "img.s-image"
            },
            "amazon_appliances_deals": {
                "url": "https://www.amazon.in/s?k=home+appliances&pct-off=30-",
                "card_selector": "div[data-component-type='s-search-result']",
                "title_selector": "h2 a span",
                "link_selector": "a.a-link-normal",
                "image_selector": "img.s-image"
            },
            "flipkart_sitewide_offers": {
                "url": "https://www.flipkart.com/search?q=offers&p%5B%5D=facets.discount_range_v1%255B%255D%3D40%2525%2Bor%2Bmore",
                "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
                "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
                "link_selector": "a",
                "image_selector": "img"
            },
            "flipkart_clearance_master_feed": {
                "url": "https://www.flipkart.com/search?q=clearance sale",
                "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
                "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
                "link_selector": "a",
                "image_selector": "img"
            },
            "flipkart_electronics_deals": {
                "url": "https://www.flipkart.com/search?q=electronics&p%5B%5D=facets.discount_range_v1%255B%255D%3D30%2525%2Bor%2Bmore",
                "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
                "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
                "link_selector": "a",
                "image_selector": "img"
            },
            "flipkart_appliances_deals": {
                "url": "https://www.flipkart.com/search?q=appliances&p%5B%5D=facets.discount_range_v1%255B%255D%3D30%2525%2Bor%2Bmore",
                "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
                "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
                "link_selector": "a",
                "image_selector": "img"
            },
            "myntra_deals": {
                "url": "https://www.myntra.com/deals?f=discount%3A50.0",
                "card_selector": "li.product-base",
                "title_selector": "h4.product-product, h3.product-brand",
                "link_selector": "a",
                "image_selector": "img"
            },
            "ajio_deals": {
                "url": "https://www.ajio.com/s/discount-50-percent-and-above",
                "card_selector": "div.item",
                "title_selector": "div.name",
                "link_selector": "a",
                "image_selector": "img"
            },
            "meesho_deals": {
                "url": "https://www.meesho.com/search?q=offers",
                "card_selector": "div[class*='ProductCard']",
                "title_selector": "p[class*='ProductTitle']",
                "link_selector": "a",
                "image_selector": "img"
            },
            "tatacliq_deals": {
                "url": "https://www.tatacliq.com/deals",
                "card_selector": "div[class*='ProductCard']",
                "title_selector": "h3[class*='ProductCard']",
                "link_selector": "a",
                "image_selector": "img"
            },
            "jiomart_deals": {
                "url": "https://www.jiomart.com/c/deals",
                "card_selector": "div.plp-card-container",
                "title_selector": "div.plp-card-name",
                "link_selector": "a",
                "image_selector": "img"
            }
        }
        for plat_key, config in default_matrix.items():
            existing = db.query(SelectorMatrix).filter_by(platform=plat_key).first()
            if not existing:
                existing = SelectorMatrix(platform=plat_key)
                db.add(existing)
            existing.url = config.get("url", "")
            existing.card_selector = config.get("card_selector", "")
            existing.title_selector = config.get("title_selector", "")
            existing.link_selector = config.get("link_selector", "")
            existing.image_selector = config.get("image_selector", "")
        db.commit()
        logging.info("Default scrapers selector matrix bootstrapped/updated in database.")
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to bootstrap selector matrix in DB: {e}")
    finally:
        db.close()



def save_deal_to_db(platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, unique_id: str, deal_score: float = 0.0):
    db = SessionLocal()
    try:
        product = db.query(Product).filter_by(id=unique_id).first()
        if not product:
            product = Product(
                id=unique_id,
                platform=platform,
                title=title,
                image_url=img_url,
                url=final_url
            )
            db.add(product)
            db.flush()
        else:
            # Keep details up-to-date
            product.title = title
            product.image_url = img_url
            product.url = final_url
        
        price_hist = PriceHistory(
            product_id=unique_id,
            price=price,
            mrp=mrp,
            discount=discount,
            is_verified_low=is_verified_low,
            deal_score=deal_score,
            timestamp=time.time()
        )
        db.add(price_hist)
        db.commit()
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to save deal to database: {e}")
    finally:
        db.close()

def log_click_to_db(deal_id: str, title: str, ip: str, user: str, user_agent: str):
    db = SessionLocal()
    try:
        click = ClickLog(
            product_id=deal_id,
            title=title,
            ip=ip,
            user=user,
            user_agent=user_agent,
            timestamp=time.time()
        )
        db.add(click)
        db.commit()
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to log click to database: {e}")
    finally:
        db.close()



def verify_historical_low(driver, product_url: str, current_price: int, unique_id: str = None, discount: float = 0.0) -> bool:
    # If the platform is not Amazon or Flipkart, we cannot query buyhatke, so we default to True
    is_supported = any(r in product_url.lower() for r in ["amazon", "flipkart"])
    if not is_supported:
        return True
        
    historical_prices = []
    try:
        encoded_url = urllib.parse.quote_plus(product_url)
        tracker_query_url = f"https://price.buyhatke.com/products.php?url={encoded_url}"
        
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.set_page_load_timeout(5)
        try:
            driver.get(tracker_query_url)
            time.sleep(1.5)
            page_text = driver.find_element(By.TAG_NAME, "body").text.replace(',', '')
            historical_prices = [int(n) for n in re.findall(r'(?:Rs\.?|₹)\s*([0-9]+)', page_text)]
        except:
            historical_prices = []
            
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
    except:
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except:
            pass

    # If external tracker succeeded, use its data
    if historical_prices:
        lowest_ever = min(historical_prices)
        highest_ever = max(historical_prices)
        
        is_near_low = current_price <= (lowest_ever * 1.05)
        has_real_drop = False
        if highest_ever > current_price:
            drop_from_peak = ((highest_ever - current_price) / highest_ever) * 100
            if drop_from_peak >= 15.0:
                has_real_drop = True
                
        if is_near_low and has_real_drop:
            return True
        return False
        
    # Fallback 1: Compare against our local historical deals database
    if unique_id:
        db = SessionLocal()
        try:
            prices = db.query(PriceHistory.price).filter_by(product_id=unique_id).all()
            if prices:
                prices_list = [p[0] for p in prices]
                min_price = min(prices_list)
                max_price = max(prices_list)
                
                is_near_low = current_price <= min_price
                has_real_drop = False
                if max_price > current_price:
                    drop_from_peak = ((max_price - current_price) / max_price) * 100
                    if drop_from_peak >= 15.0:
                        has_real_drop = True
                        
                if is_near_low and has_real_drop:
                    return True
        except Exception as e:
            logging.error(f"Local price check failed: {e}")
        finally:
            db.close()
            
    return True



def init_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    settings = load_settings()
    if settings.get("proxies_enabled") and settings.get("proxy_list"):
        import random
        # Clean and pick a random proxy
        valid_proxies = [p.strip() for p in settings["proxy_list"] if p.strip()]
        if valid_proxies:
            proxy = random.choice(valid_proxies)
            options.add_argument(f"--proxy-server={proxy}")
            logging.info(f"WebDriver initialized using proxy: {proxy}")
            
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        logging.warning(f"Default Chrome WebDriver initialization failed: {e}. Trying webdriver-manager fallback...")
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            logging.info("Chrome WebDriver successfully initialized using webdriver-manager fallback.")
        except Exception as fallback_err:
            logging.error(f"webdriver-manager fallback initialization also failed: {fallback_err}")
            raise e
            
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver

# ==========================================
# BUILT-IN LIGHTWEIGHT REST API & SERVER
# ==========================================
class ScraperAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Log REST requests to execution.log
        logger.info(f"REST API: {format % args}")
        
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
        
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # Serve static dashboard files dynamically
        clean_path = self.path.split('?')[0]
        if clean_path == '/':
            clean_path = '/index.html'
            
        path_mappings = {
            '/main.js': '/index.js',
            '/style.css': '/index.css'
        }
        mapped_path = path_mappings.get(clean_path, clean_path)
        local_filename = mapped_path.lstrip('/')
        filepath = os.path.join(DASHBOARD_DIR, local_filename)
        
        if os.path.exists(filepath) and os.path.isfile(filepath):
            ext = os.path.splitext(filepath)[1].lower()
            mime_types = {
                '.html': 'text/html',
                '.css': 'text/css',
                '.js': 'application/javascript',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.json': 'application/json',
                '.svg': 'image/svg+xml',
                '.ico': 'image/x-icon'
            }
            mime = mime_types.get(ext, 'application/octet-stream')
            self._serve_static(filepath, mime)
            return
        
        # API Endpoints
        if self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            status = {
                "is_running": scraper_state["is_running"],
                "scans_completed": scraper_state["scans_completed"],
                "last_scan_time": scraper_state["last_scan_time"],
                "uptime": time.time() - scraper_state["uptime_start"]
            }
            self.wfile.write(json.dumps(status).encode('utf-8'))
            
        elif self.path == '/api/selectors':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            db = SessionLocal()
            try:
                matrices = db.query(SelectorMatrix).all()
                data = {}
                for m in matrices:
                    data[m.platform] = {
                        "url": m.url,
                        "card_selector": m.card_selector,
                        "title_selector": m.title_selector,
                        "link_selector": m.link_selector,
                        "image_selector": m.image_selector
                    }
                self.wfile.write(json.dumps(data).encode('utf-8'))
            except Exception as e:
                self.wfile.write(b"{}")
            finally:
                db.close()
                
        elif self.path == '/api/deals':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            db = SessionLocal()
            try:
                products = db.query(Product).all()
                deals = []
                for p in products:
                    latest_price = db.query(PriceHistory).filter_by(product_id=p.id).order_by(PriceHistory.timestamp.desc()).first()
                    if not latest_price:
                        continue
                    
                    click_count = db.query(ClickLog).filter_by(product_id=p.id).count()
                    
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
                        "clicks": click_count
                    })
                deals.sort(key=lambda x: x["timestamp"], reverse=True)
                self.wfile.write(json.dumps(deals).encode('utf-8'))
            except Exception as e:
                self.wfile.write(b"[]")
            finally:
                db.close()
                
        elif self.path.startswith('/api/deals/history'):
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            deal_id = params.get('id', [None])[0]
            
            if not deal_id:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing product ID"}).encode('utf-8'))
                return
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            db = SessionLocal()
            try:
                history = db.query(PriceHistory).filter_by(product_id=deal_id).order_by(PriceHistory.timestamp.asc()).all()
                data = [{
                    "price": h.price,
                    "mrp": h.mrp,
                    "discount": h.discount,
                    "timestamp": h.timestamp,
                    "is_verified_low": h.is_verified_low,
                    "deal_score": h.deal_score
                } for h in history]
                self.wfile.write(json.dumps(data).encode('utf-8'))
            except Exception as e:
                self.wfile.write(b"[]")
            finally:
                db.close()
            
        elif self.path.startswith('/api/redirect'):
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            deal_id = params.get('id', [None])[0]
            target_url = params.get('url', [None])[0]
            user = params.get('user', ['Anonymous'])[0]
            
            title = "Unknown Product"
            if deal_id:
                db = SessionLocal()
                try:
                    product = db.query(Product).filter_by(id=deal_id).first()
                    if product:
                        title = product.title
                        
                    client_ip = self.client_address[0]
                    user_agent = self.headers.get('User-Agent', 'Unknown')
                    
                    # Log click directly to database
                    click = ClickLog(
                        product_id=deal_id,
                        title=title,
                        ip=client_ip,
                        user=user,
                        user_agent=user_agent,
                        timestamp=time.time()
                    )
                    db.add(click)
                    db.commit()
                    
                    # Recalculate and update the deal_score of this product to reflect the click popularity boost
                    latest_price = db.query(PriceHistory).filter_by(product_id=deal_id).order_by(PriceHistory.timestamp.desc()).first()
                    if latest_price:
                        new_score = calculate_deal_score(
                            platform=product.platform if product else "amazon",
                            price=latest_price.price,
                            mrp=latest_price.mrp,
                            discount=latest_price.discount,
                            is_verified_low=latest_price.is_verified_low,
                            is_lightning=("lightning" in product.platform.lower() if product else False),
                            product_id=deal_id
                        )
                        latest_price.deal_score = new_score
                        db.commit()
                        
                        # Sync static JSONs to keep dashboard UI elements in sync
                        sync_database_to_json()
                except Exception as e:
                    db.rollback()
                    logging.error(f"Redirect logging error: {e}")
                finally:
                    db.close()
                    
            if target_url:
                self.send_response(302)
                self.send_header('Location', target_url)
                self.end_headers()
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing target URL")
                
        elif self.path == '/api/clicks':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            db = SessionLocal()
            try:
                clicks = db.query(ClickLog).order_by(ClickLog.timestamp.desc()).limit(50).all()
                data = [{
                    "deal_id": c.product_id,
                    "title": c.title,
                    "ip": c.ip,
                    "user": c.user,
                    "user_agent": c.user_agent,
                    "timestamp": c.timestamp
                } for c in clicks]
                self.wfile.write(json.dumps(data).encode('utf-8'))
            except Exception as e:
                self.wfile.write(b"[]")
            finally:
                db.close()
                
        elif self.path == '/api/settings':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            settings = load_settings()
            self.wfile.write(json.dumps(settings).encode('utf-8'))
            
        elif self.path == '/api/logs/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            # Send initial logs
            initial_lines = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                        initial_lines = f.readlines()[-60:]
                except:
                    pass
            for line in initial_lines:
                try:
                    self.wfile.write(f"data: {json.dumps(line.strip())}\n\n".encode('utf-8'))
                except:
                    return
            try:
                self.wfile.flush()
            except:
                return
            
            # Tail log file
            try:
                with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(0, 2)
                    while True:
                        line = f.readline()
                        if not line:
                            time.sleep(0.5)
                            continue
                        self.wfile.write(f"data: {json.dumps(line.strip())}\n\n".encode('utf-8'))
                        self.wfile.flush()
            except Exception as e:
                pass
                
        elif self.path == '/api/logs':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            lines = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[-100:]
                except Exception as e:
                    lines = [f"Failed to read logs: {e}"]
            self.wfile.write(json.dumps(lines).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        parsed_path = urllib.parse.urlparse(self.path).path
        logger.info(f"POST Request: path='{self.path}' parsed='{parsed_path}'")
        
        if parsed_path == '/api/selectors':
            try:
                data = json.loads(post_data.decode('utf-8'))
                db = SessionLocal()
                try:
                    for plat_key, config in data.items():
                        matrix = db.query(SelectorMatrix).filter_by(platform=plat_key).first()
                        if not matrix:
                            matrix = SelectorMatrix(platform=plat_key)
                            db.add(matrix)
                        matrix.url = config.get("url", "")
                        matrix.card_selector = config.get("card_selector", "")
                        matrix.title_selector = config.get("title_selector", "")
                        matrix.link_selector = config.get("link_selector", "")
                        matrix.image_selector = config.get("image_selector", "")
                    db.commit()
                except Exception as db_err:
                    db.rollback()
                    raise db_err
                finally:
                    db.close()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif parsed_path == '/api/scan':
            scraper_state["scan_trigger"] = True
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "Manual scan triggered"}).encode('utf-8'))
            
        elif parsed_path == '/api/toggle':
            scraper_state["is_running"] = not scraper_state["is_running"]
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "is_running": scraper_state["is_running"]}).encode('utf-8'))
            
        elif parsed_path == '/api/settings':
            try:
                data = json.loads(post_data.decode('utf-8'))
                save_settings(data)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif parsed_path == '/api/login':
            try:
                data = json.loads(post_data.decode('utf-8'))
                username = str(data.get('username', '')).strip().lower()
                password = str(data.get('password', '')).strip()
                logger.info(f"Auth attempt: username='{username}'")
                
                # Retrieve credentials from environment variables
                env_user = os.environ.get("DASHBOARD_USERNAME", "yogeshpadwal16").strip().lower()
                env_pass = os.environ.get("DASHBOARD_PASSWORD", "YOUR_DASHBOARD_PASSWORD").strip()
                env_token = os.environ.get("DASHBOARD_SESSION_TOKEN", "admin_session_key_default").strip()
                
                if username == env_user and password == env_pass:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {
                        "status": "success",
                        "token": env_token,
                        "name": "Yogesh Padwal"
                    }
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                else:
                    self.send_response(401)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "failed", "message": "Invalid username or password"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
                
        elif parsed_path == '/api/deals/delete':
            try:
                data = json.loads(post_data.decode('utf-8'))
                deal_id = data.get('id')
                if not deal_id:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing deal ID"}).encode('utf-8'))
                    return
                
                db = SessionLocal()
                try:
                    product = db.query(Product).filter_by(id=deal_id).first()
                    if product:
                        db.delete(product)
                        db.commit()
                        deleted_count = 1
                    else:
                        deleted_count = 0
                except Exception as db_err:
                    db.rollback()
                    raise db_err
                finally:
                    db.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "deleted": deleted_count}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
                
        elif parsed_path == '/api/processes/cleanup':
            try:
                import psutil
                my_pid = os.getpid()
                parent_pid = os.getppid()
                terminated_list = []
                
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        pinfo = proc.info
                        pid = pinfo['pid']
                        name = pinfo['name']
                        cmdline = pinfo['cmdline']
                        
                        if pid in (my_pid, parent_pid):
                            continue
                            
                        # Terminate other python processes executing loot_scraper
                        if name and 'python' in name.lower():
                            if cmdline and any('loot_scraper.py' in arg for arg in cmdline):
                                proc.kill()
                                terminated_list.append(f"Python (PID {pid})")
                                continue
                                
                        # Terminate zombie webdrivers / browser sessions
                        if name and ('chromedriver' in name.lower() or 'chrome' in name.lower()):
                            proc.kill()
                            terminated_list.append(f"{name} (PID {pid})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "message": "Zombie cleanup execution successful",
                    "killed": terminated_list
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif parsed_path == '/api/manual/crawl':
            try:
                data = json.loads(post_data.decode('utf-8'))
                url = data.get('url', '').strip()
                if not url:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing URL"}).encode('utf-8'))
                    return
                
                result = scrape_product_details(url)
                
                # Convert affiliate link
                settings = load_settings()
                platform = result["platform"]
                aff_url = url
                unique_id = str(int(time.time()))
                
                if platform == "amazon":
                    from utils.parser import extract_amazon_asin
                    asin = extract_amazon_asin(url)
                    if asin:
                        aff_url = f"https://www.amazon.in/dp/{asin}?tag={settings.get('amazon_tag', 'lootraiders-21')}"
                        unique_id = asin
                elif platform == "flipkart":
                    from utils.parser import extract_flipkart_pid
                    pid = extract_flipkart_pid(url)
                    if pid:
                        aff_url = f"https://www.flipkart.com/product/p/itm?pid={pid}&affid={settings.get('flipkart_affid', 'YOUR_FLIPKART_AFFILIATE_ID')}"
                        unique_id = pid
                        
                result["affiliate_url"] = aff_url
                result["unique_id"] = unique_id
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif parsed_path == '/api/manual/post':
            try:
                data = json.loads(post_data.decode('utf-8'))
                platform = data.get('platform', 'generic')
                title = data.get('title', '').strip()
                price = int(data.get('price', 0))
                mrp = int(data.get('mrp', 0))
                image_url = data.get('image_url', '').strip()
                affiliate_url = data.get('affiliate_url', '').strip()
                unique_id = data.get('unique_id', str(int(time.time())))
                
                settings = load_settings()
                bot_token = settings.get("telegram_bot_token")
                chat_id = settings.get("telegram_chat_id")
                
                if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "":
                    raise Exception("Telegram Bot not configured in settings!")
                
                discount = 0.0
                if mrp > 0 and price > 0:
                    discount = ((mrp - price) / mrp) * 100.0
                    
                # Save product in DB to make sure sparkline history is generated/updated
                db = SessionLocal()
                try:
                    product = db.query(Product).filter_by(id=unique_id).first()
                    if not product:
                        product = Product(
                            id=unique_id,
                            platform=platform,
                            title=title,
                            image_url=image_url,
                            url=affiliate_url
                        )
                        db.add(product)
                        db.commit()
                        
                    # Save a price history point
                    ph = PriceHistory(
                        product_id=unique_id,
                        price=price,
                        mrp=mrp,
                        discount=discount,
                        is_verified_low=True,
                        deal_score=95.0,
                        timestamp=time.time()
                    )
                    db.add(ph)
                    db.commit()
                except Exception as db_err:
                    db.rollback()
                    logging.error(f"Error logging manual deal to DB: {db_err}")
                finally:
                    db.close()
                
                from deal_engine.notifier import send_telegram_alert
                posted = send_telegram_alert(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    platform=platform,
                    title=title,
                    price=price,
                    mrp=mrp,
                    discount=discount,
                    img_url=image_url,
                    final_url=affiliate_url,
                    is_verified_low=True,
                    deal_score=95.0,
                    unique_id=unique_id
                )
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "posted": posted}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_static(self, filepath, mime):
        if os.path.exists(filepath) and os.path.isfile(filepath):
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

def start_api_server(port=5555):
    # Ensure dashboard folder exists
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    
    server = ThreadingHTTPServer(('0.0.0.0', port), ScraperAPIHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logging.info(f"Dashboard REST API engine running at http://0.0.0.0:{port}/")

# ==========================================
# CORE SCANNERS MAIN LOOP
# ==========================================
def scrape_platform(platform: str, config: dict, history: set):
    if not scraper_state["is_running"] and not scraper_state["scan_trigger"]:
        return
        
    logging.info(f"Scanning target feed stream: {platform.upper()} (Multi-threaded)")
    driver = None
    
    # 1. Resolve matched plugin for platform
    plugin = None
    for key, instance in RETAILER_PLUGINS.items():
        if key in platform.lower():
            plugin = instance
            break
            
    if not plugin:
        logging.warning(f"No suitable retailer plugin registered for platform: {platform}")
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
            final_url = deal["url"]
            is_lightning = deal["is_lightning"]
            
            # Fetch latest price from DB to see if it's a duplicate or if the price changed
            price_changed = True
            is_price_drop = True
            db = SessionLocal()
            try:
                latest = db.query(PriceHistory).filter_by(product_id=unique_id).order_by(PriceHistory.timestamp.desc()).first()
                if latest:
                    if latest.price == price:
                        price_changed = False
                    else:
                        is_price_drop = price < latest.price
            except Exception as db_err:
                logging.error(f"Error querying latest price for duplicate check: {db_err}")
            finally:
                db.close()
                
            if not price_changed and unique_id in history:
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
            deal_score = calculate_deal_score(platform, price, mrp, discount, is_verified_low, is_lightning, product_id=unique_id)
            
            # Persist inside Knowledge Base database
            save_deal_to_db(platform, title, price, mrp, discount, img_url, final_url, is_verified_low, unique_id, deal_score)
            history.add(unique_id)
            
            # Dispatch notifications if score is above the configured threshold and it's a price drop (or new product)
            if should_publish_deal(platform, deal_score) and is_price_drop:
                enqueue_alert(platform, title, price, mrp, discount, img_url, final_url, is_verified_low, deal_score, unique_id)
                time.sleep(0.5)
            else:
                if not is_price_drop:
                    logging.info(f"Skipping deal broadcast: {title[:35]}... (Price increased from last scan)")
                else:
                    logging.info(f"Skipping deal broadcast: {title[:35]}... (Score: {deal_score:.1f} below threshold)")
                
    except Exception as out_err:
        logging.error(f"Scraper interface failure on stream {platform}: {out_err}")
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
                "clicks": click_count
            })
        deals.sort(key=lambda x: x["timestamp"], reverse=True)
        
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

def run_zombie_cleanup():
    try:
        import psutil
        my_pid = os.getpid()
        parent_pid = os.getppid()
        terminated_list = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pinfo = proc.info
                pid = pinfo['pid']
                name = pinfo['name']
                cmdline = pinfo['cmdline']
                
                if pid in (my_pid, parent_pid):
                    continue
                    
                # Terminate other python processes executing loot_scraper
                if name and 'python' in name.lower():
                    if cmdline and any('loot_scraper.py' in arg for arg in cmdline):
                        proc.kill()
                        terminated_list.append(f"Python (PID {pid})")
                        continue
                        
                # Terminate zombie webdrivers / browser sessions
                if name and ('chromedriver' in name.lower() or 'chrome' in name.lower()):
                    proc.kill()
                    terminated_list.append(f"{name} (PID {pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if terminated_list:
            logging.info(f"Automated startup zombie cleanup executed. Terminated: {', '.join(terminated_list)}")
    except Exception as e:
        logging.warning(f"Startup zombie cleanup warning: {e}")

def main():
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
                
                scraper_state["scans_completed"] += 1
                scraper_state["last_scan_time"] = time.time()
                logging.info("Inter-stream sequence frame complete. Pausing current execution cycle.")
                
            except Exception as loop_err:
                logging.error(f"Error in main scanner loop: {loop_err}")
                
            if single_run:
                logging.info("Single-run execution complete. Exiting scraper loop.")
                break
                
            for _ in range(60):
                if not scraper_state["is_running"] or scraper_state["scan_trigger"]:
                    break
                time.sleep(1)
                
    except KeyboardInterrupt:
        logging.warning("SIGINT operational interrupt recognized. Turning pipeline off safely.")

def scrape_product_details(url: str) -> dict:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    import time
    import re
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get(url)
        time.sleep(5)  # Wait for dynamic JS content to fully load
        
        title = ""
        price = 0
        mrp = 0
        image_url = ""
        platform = "generic"
        
        if "amazon" in url.lower():
            platform = "amazon"
        elif "flipkart" in url.lower():
            platform = "flipkart"
            
        # 1. Scrape Title
        if platform == "amazon":
            for selector in ["#productTitle", "span#productTitle", ".qa-title-text"]:
                try:
                    title = driver.find_element(By.CSS_SELECTOR, selector).text.strip()
                    if title: break
                except: pass
        elif platform == "flipkart":
            for selector in [".VU-ZEg", "span.B_NuCI", "h1.yrwE28", "h1 span"]:
                try:
                    title = driver.find_element(By.CSS_SELECTOR, selector).text.strip()
                    if title: break
                except: pass
                
        # Generic Title extraction fallback
        if not title:
            try: title = driver.find_element(By.TAG_NAME, "h1").text.strip()
            except: pass
        if not title:
            try:
                raw_title = driver.title
                if "Buy" in raw_title:
                    raw_title = raw_title.split("Buy")[1].strip()
                if "Online at Low Prices" in raw_title:
                    raw_title = raw_title.split("Online")[0].strip()
                if "amazon.in" in raw_title.lower() or "amazon.com" in raw_title.lower():
                    raw_title = raw_title.split(":")[0].strip()
                if "flipkart.com" in raw_title.lower():
                    raw_title = raw_title.split("-")[0].strip()
                title = raw_title
            except:
                pass
                
        # 2. Scrape Price
        if platform == "amazon":
            for selector in [".a-price-whole", "span.a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice", ".apexPriceToPay span.a-offscreen", ".a-color-price"]:
                try:
                    p_text = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent")
                    p_text = p_text.split(".")[0]
                    price = int(re.sub(r'\D', '', p_text))
                    if price > 0: break
                except: pass
        elif platform == "flipkart":
            for selector in [".Nx9w7A", "._30jeq3", "div._30jeq3._16JkK1", "div.hlbKVd"]:
                try:
                    p_text = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent")
                    p_text = p_text.split(".")[0]
                    price = int(re.sub(r'\D', '', p_text))
                    if price > 0: break
                except: pass
                
        # 3. Scrape MRP
        if platform == "amazon":
            for selector in ["span.a-price.a-text-price span.a-offscreen", "#listPrice", "#priceblock_listprice", "span.a-list-price"]:
                try:
                    m_text = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent")
                    m_text = m_text.split(".")[0]
                    mrp = int(re.sub(r'\D', '', m_text))
                    if mrp > 0: break
                except: pass
        elif platform == "flipkart":
            for selector in [".y3NYbL", "._3I9_ww", "div._3I9_ww"]:
                try:
                    m_text = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent")
                    m_text = m_text.split(".")[0]
                    mrp = int(re.sub(r'\D', '', m_text))
                    if mrp > 0: break
                except: pass
                
        # 4. Scrape Image
        if platform == "amazon":
            for selector in ["#landingImage", "#imgBlkFront", ".imgTagWrapper img", "#main-image"]:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    for attr in ["data-old-hires", "data-a-dynamic-image", "src"]:
                        val = element.get_attribute(attr)
                        if val:
                            val = val.strip()
                            if val.startswith("{"):
                                try:
                                    import json
                                    urls = json.loads(val)
                                    if urls:
                                        image_url = list(urls.keys())[-1]
                                        break
                                except: pass
                            elif val.startswith("http"):
                                image_url = val
                                break
                    if image_url: break
                except: pass
        elif platform == "flipkart":
            for selector in ["img.DByoR4", "img._396cs4", "img.jfZQxf", "div.CXW8mj img"]:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    for attr in ["data-src", "src"]:
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
            
        return {
            "platform": platform,
            "title": title,
            "price": price,
            "mrp": mrp,
            "image_url": image_url
        }
    finally:
        driver.quit()

if __name__ == "__main__":
    main()