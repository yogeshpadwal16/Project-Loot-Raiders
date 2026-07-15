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
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

sys.stdout.reconfigure(encoding='utf-8')

# Gracefully load environment variables if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==========================================
# ROOT SYSTEM MATRIX PATHING
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
SELECTOR_FILE = os.path.join(BASE_DIR, "selectors.json")
HISTORY_FILE = os.path.join(BASE_DIR, "omega_history.json")
DEALS_HISTORY_FILE = os.path.join(DASHBOARD_DIR, "deals_history.json")
LOG_FILE = os.path.join(BASE_DIR, "execution.log")
CLICKS_TRACKER_FILE = os.path.join(BASE_DIR, "clicks_tracker.json")
CLICKS_LOG_FILE = os.path.join(BASE_DIR, "clicks_activity.json")

# 🚨 CONFIGURATION CONTROL INTERFACE
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@LootRaidersDeals")

AMAZON_TAG = os.environ.get("AMAZON_TAG", "lootraiders-21")
FLIPKART_AFFID = os.environ.get("FLIPKART_AFFID", "YOUR_FLIPKART_AFFILIATE_ID")

DASHBOARD_USERNAME = os.environ.get("DASHBOARD_USERNAME", "yogeshpadwal16")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "YOUR_DASHBOARD_PASSWORD")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
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
    "scan_trigger": False        # External trigger for manual scan
}

# Thread lock for safe JSON file reads and writes
file_lock = threading.Lock()

def read_json_file(filepath: str, default_val=None):
    if default_val is None:
        default_val = {}
    if not os.path.exists(filepath):
        return default_val
    with file_lock:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to read JSON from {filepath}: {e}")
            return default_val

def write_json_file(filepath: str, data):
    with file_lock:
        try:
            temp_filepath = filepath + ".tmp"
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_filepath, filepath)
        except Exception as e:
            logging.error(f"Failed to write JSON to {filepath}: {e}")

def initialize_selectors_json():
    # Only create if the file doesn't exist, to preserve user customizations
    if os.path.exists(SELECTOR_FILE):
        return
        
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
        "flipkart_sitewide_offers": {
            "url": "https://www.flipkart.com/search?q=offers&p%5B%5D=facets.discount_range_v1%255B%255D%3D40%2525%2Bor%2Bmore",
            "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
            "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
            "link_selector": "a",
            "image_selector": "img"
        },
        "flipkart_clearance_master_feed": {
            "url": "https://www.flipkart.com/search?q=clearance+sale",
            "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
            "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
            "link_selector": "a",
            "image_selector": "img"
        }
    }
    write_json_file(SELECTOR_FILE, default_matrix)

def load_history() -> dict:
    return read_json_file(HISTORY_FILE, default_val={})

def save_and_flush_history(history: dict, unique_id: str):
    history[unique_id] = time.time()
    write_json_file(HISTORY_FILE, history)

def increment_click_count(deal_id: str):
    stats = read_json_file(CLICKS_TRACKER_FILE, default_val={})
    stats[deal_id] = stats.get(deal_id, 0) + 1
    write_json_file(CLICKS_TRACKER_FILE, stats)

def log_click_activity(deal_id: str, title: str, ip: str, user: str, user_agent: str):
    activity = read_json_file(CLICKS_LOG_FILE, default_val=[])
    new_entry = {
        "deal_id": deal_id,
        "title": title,
        "ip": ip,
        "user": user,
        "user_agent": user_agent,
        "timestamp": time.time()
    }
    activity.insert(0, new_entry)
    activity = activity[:50] # keep last 50 entries
    write_json_file(CLICKS_LOG_FILE, activity)

def save_deal_to_rich_history(platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, unique_id: str):
    deals = read_json_file(DEALS_HISTORY_FILE, default_val=[])
    
    # Remove any existing deal with the same ID to prevent duplicates
    deals = [d for d in deals if d.get("id") != unique_id]
            
    new_deal = {
        "id": unique_id,
        "platform": platform,
        "title": title,
        "price": price,
        "mrp": mrp,
        "discount": discount,
        "image_url": img_url,
        "url": final_url,
        "is_verified_low": is_verified_low,
        "timestamp": time.time()
    }
    
    # Prepend new deals, limit to last 100 entries
    deals.insert(0, new_deal)
    deals = deals[:100]
    write_json_file(DEALS_HISTORY_FILE, deals)

def extract_amazon_asin(url: str) -> str:
    match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', url)
    return match.group(1) if match else None

def extract_flipkart_pid(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if 'pid' in params:
        return params['pid'][0]
    match = re.search(r'pid=([a-zA-Z0-9]{16})', url)
    if match: return match.group(1)
    match_path = re.search(r'/p/([a-zA-Z0-9]{16})', url)
    if match_path: return match_path.group(1)
    return None

def calculate_true_discount(text_content: str):
    # Pre-strip percentage discounts (e.g. "50% off", "82%") so they don't concatenate with price numbers
    clean_text = re.sub(r'[0-9]{1,2}\s*%\s*(?:off)?', ' ', text_content, flags=re.IGNORECASE)
    
    clean_text = clean_text.replace(',', '').replace('\n', ' ')
    clean_text = re.sub(r'(?:₹|Rs\.?)\s*[0-9]+\s*/\s*[a-zA-Z]+', '', clean_text)
    clean_text = re.sub(r'\(\s*(?:₹|Rs\.?)\s*[0-9]+\s*[^)]*\)', '', clean_text)

    numbers = [int(n) for n in re.findall(r'(?:₹|Rs\.?)\s*([0-9]+)', clean_text)]
    if len(numbers) < 2:
        numbers = [int(n) for n in re.findall(r'\b[0-9]{2,7}\b', clean_text) if int(n) > 49]

    if len(numbers) < 2:
        return None, None, None
        
    selling_price = numbers[0]
    mrp = max(numbers)
    
    if mrp == 0 or selling_price >= mrp:
        return None, None, None
        
    true_discount = ((mrp - selling_price) / mrp) * 100
    return selling_price, mrp, true_discount

def verify_historical_low(driver, product_url: str, current_price: int) -> bool:
    try:
        encoded_url = urllib.parse.quote_plus(product_url)
        tracker_query_url = f"https://price.buyhatke.com/products.php?url={encoded_url}"
        
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.set_page_load_timeout(10)
        
        historical_prices = []
        try:
            driver.get(tracker_query_url)
            
            # Dynamic polling to support fast loading and early-exit on 404 pages
            start_time = time.time()
            while time.time() - start_time < 5.0:
                try:
                    page_text = driver.find_element(By.TAG_NAME, "body").text
                    clean_text = page_text.replace(',', '')
                    
                    # Early termination if BuyHatke displays a 404 or product not found
                    if "404" in clean_text or "can't find that page" in clean_text.lower() or "uh-oh!" in clean_text.lower():
                        break
                    
                    # Parse prices
                    prices = [int(n) for n in re.findall(r'(?:Rs\.?|₹)\s*([0-9]+)', clean_text)]
                    if prices:
                        historical_prices = prices
                        break
                except Exception:
                    pass
                time.sleep(0.3)
        except Exception as e:
            logging.error(f"Error fetching BuyHatke page: {e}")
            
        try:
            driver.close()
        except Exception:
            pass
            
        try:
            driver.switch_to.window(driver.window_handles[0])
        except Exception:
            pass
        
        if historical_prices:
            lowest_ever = min(historical_prices)
            if current_price <= (lowest_ever * 1.05):
                return True
        return False
    except Exception as e:
        logging.error(f"Failed historical price check: {e}")
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except Exception:
            pass
        return False

# ==========================================
# INTELLIGENT DISPATCH HUB
# ==========================================
def dispatch_rich_media_alert(platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool):
    if "YOUR_TELEGRAM" in TELEGRAM_BOT_TOKEN or not TELEGRAM_BOT_TOKEN:
        logging.warning("Skipping Broadcast: Secret Token parameters remain default.")
        return False

    is_amazon = "amazon" in platform.lower()
    platform_header = "🍊 [ AMAZON INDIA ]" if is_amazon else "💣 [ FLIPKART ]"
    
    clean_title = title.split('\n')[0].strip()
    truncated_title = clean_title[:107] + "..." if len(clean_title) > 110 else clean_title
    
    validation_badge = "🔥 [ VERIFIED ALL-TIME LOW PRICE ]\n" if is_verified_low else ""
    
    caption = (
        f"{platform_header}\n"
        f"{validation_badge}"
        f"📌 *{truncated_title}*\n\n"
        f"```\n"
        f"💰 Deal Price: ₹{price:,}\n"
        f"❌ True MRP:   ₹{mrp:,}\n"
        f"📉 Discount:   {discount:.1f}% OFF\n"
        f"```\n"
        f"⚡ *HURRY, PRICE DROP SEEN!*\n"
        f"👉 [GRAB THIS LAUNCH DEAL NOW]({final_url})\n\n"
        f"--- \n"
        f"🛒 Curated by: *Yogesh Padwal*"
    )
    
    # Check if image is valid, if not use fallback textual alert immediately
    if not img_url or "base64" in img_url:
         try:
            text_endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload_fallback = {"chat_id": TELEGRAM_CHAT_ID, "text": caption, "parse_mode": "Markdown"}
            res_fb = requests.post(text_endpoint, json=payload_fallback, timeout=15)
            return res_fb.status_code == 200
         except Exception:
            return False

    try:
        endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": caption, "parse_mode": "Markdown"}
        res = requests.post(endpoint, json=payload, timeout=15)
        if res.status_code == 200:
            logging.info(f"Telegram Broadcast Success -> {truncated_title[:20]}...")
            return True
    except Exception:
        pass

    try:
        text_endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload_fallback = {"chat_id": TELEGRAM_CHAT_ID, "text": caption, "parse_mode": "Markdown"}
        res_fb = requests.post(text_endpoint, json=payload_fallback, timeout=15)
        return res_fb.status_code == 200
    except Exception:
        return False

def init_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
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
        # Serve static dashboard files
        if self.path == '/' or self.path == '/index.html':
            filepath = os.path.join(DASHBOARD_DIR, 'index.html')
            mime = 'text/html'
            self._serve_static(filepath, mime)
        elif self.path == '/index.js' or self.path == '/main.js':
            filepath = os.path.join(DASHBOARD_DIR, 'index.js')
            mime = 'application/javascript'
            self._serve_static(filepath, mime)
        elif self.path == '/index.css' or self.path == '/style.css':
            filepath = os.path.join(DASHBOARD_DIR, 'index.css')
            mime = 'text/css'
            self._serve_static(filepath, mime)
        
        # API Endpoints
        elif self.path == '/api/status':
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
            selectors = read_json_file(SELECTOR_FILE, default_val={})
            self.wfile.write(json.dumps(selectors).encode('utf-8'))
                
        elif self.path == '/api/deals':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            deals = read_json_file(DEALS_HISTORY_FILE, default_val=[])
            clicks = read_json_file(CLICKS_TRACKER_FILE, default_val={})
            
            for d in deals:
                d["clicks"] = clicks.get(d.get("id"), 0)
                
            self.wfile.write(json.dumps(deals).encode('utf-8'))
            
        elif self.path.startswith('/api/redirect'):
            # Parse query params
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            deal_id = params.get('id', [None])[0]
            target_url = params.get('url', [None])[0]
            user = params.get('user', ['Anonymous'])[0]
            
            # Identify title
            title = "Unknown Product"
            if deal_id:
                deals = read_json_file(DEALS_HISTORY_FILE, default_val=[])
                for d in deals:
                    if d.get("id") == deal_id:
                        title = d.get("title", "Unknown Product")
                        break
            
            if deal_id:
                increment_click_count(deal_id)
                # Capture caller details
                client_ip = self.client_address[0]
                user_agent = self.headers.get('User-Agent', 'Unknown')
                log_click_activity(deal_id, title, client_ip, user, user_agent)
                
            # Send redirect
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
            activity = read_json_file(CLICKS_LOG_FILE, default_val=[])
            self.wfile.write(json.dumps(activity).encode('utf-8'))
                
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
                write_json_file(SELECTOR_FILE, data)
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
            
        elif parsed_path == '/api/login':
            try:
                data = json.loads(post_data.decode('utf-8'))
                username = str(data.get('username', '')).strip().lower()
                password = str(data.get('password', '')).strip()
                logger.info(f"Auth attempt: username='{username}'")
                
                if username == DASHBOARD_USERNAME.lower() and password == DASHBOARD_PASSWORD:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {
                        "status": "success",
                        "token": "admin_session_key_vihan_143",
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
                
                deals = read_json_file(DEALS_HISTORY_FILE, default_val=[])
                original_len = len(deals)
                deals = [d for d in deals if d.get("id") != deal_id]
                
                try:
                    write_json_file(DEALS_HISTORY_FILE, deals)
                except Exception as e:
                    logger.error(f"Error saving deals history after deletion: {e}")
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"Failed to save deals: {e}"}).encode('utf-8'))
                    return

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "deleted": original_len - len(deals)}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
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
    
    server = HTTPServer(('127.0.0.1', port), ScraperAPIHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logging.info(f"Dashboard REST API engine running at http://127.0.0.1:{port}/")

# ==========================================
# CORE SCANNERS MAIN LOOP
# ==========================================
def main():
    initialize_selectors_json()
    
    # Check for single-run mode (command-line arg or GITHUB_ACTIONS env var)
    single_run = "--single-run" in sys.argv or os.environ.get('GITHUB_ACTIONS') == 'true'
    
    if not single_run:
        start_api_server(5555)
        logging.info("Master Engine Activated. Scanners operating.")
    else:
        logging.info("Single-run execution mode activated (Cloud/CI environment).")
    
    driver = None
    
    try:
        while True:
            if not single_run:
                # Check state flags: Sleep if not running and no manual scan triggered
                if not scraper_state["is_running"] and not scraper_state["scan_trigger"]:
                    time.sleep(1)
                    continue
                    
                # Handle manual scan trigger
                if scraper_state["scan_trigger"]:
                    logging.info("Manual scan triggered via REST API. Starting execute sequence.")
                    scraper_state["scan_trigger"] = False
                
            # Initialize or recover chrome driver session
            if driver is None:
                try:
                    driver = init_driver()
                    driver.set_page_load_timeout(30)
                except Exception as de:
                    logging.error(f"Failed to initialize Chrome Driver: {de}. Retrying in 10s...")
                    time.sleep(10)
                    continue

            # Core scanning logic wrapped inside try block for selenium crash recovery
            try:
                matrix = read_json_file(SELECTOR_FILE, default_val={})
                
                history = load_history()
                current_time = time.time()
                history = {k: v for k, v in history.items() if current_time - v < 86400}
                
                for platform, config in matrix.items():
                    # Check loop flags mid-stream to toggle instantly
                    if not scraper_state["is_running"] and not scraper_state["scan_trigger"]:
                        logging.info("Scraper execution halted by user request.")
                        break
                        
                    logging.info(f"Scanning target feed stream: {platform.upper()}")
                    try:
                        driver.set_page_load_timeout(30)
                        driver.get(config['url'])
                        time.sleep(4)
                        
                        # 1. Human-Simulated Scroll Matrix to load images completely
                        for scroll in range(1, 6):
                            driver.execute_script(f"window.scrollTo(0, {scroll * 500});")
                            time.sleep(1.5) 
                        
                        cards = driver.find_elements(By.CSS_SELECTOR, config['card_selector'])
                        logging.info(f"Targeting matrix: Found {len(cards)} node objects inside {platform}")
                        
                        for card in cards:
                            try:
                                links = card.find_elements(By.TAG_NAME, "a")
                                raw_url = None
                                
                                for l in links:
                                    href = l.get_attribute("href")
                                    if href and ("javascript" not in href) and ("/p/" in href or "pid=" in href or "/dp/" in href):
                                        raw_url = href
                                        break
                                        
                                if not raw_url and links:
                                    for l in links:
                                        href = l.get_attribute("href")
                                        if href and ("javascript" not in href):
                                            raw_url = href
                                            break
                                            
                                if not raw_url: continue
                                
                                unique_id = None
                                clean_base_url = ""
                                norm_plat = platform.lower()
                                
                                if "amazon" in norm_plat:
                                    unique_id = extract_amazon_asin(raw_url)
                                    if unique_id:
                                        clean_base_url = f"https://www.amazon.in/dp/{unique_id}"
                                        final_url = f"{clean_base_url}?tag={AMAZON_TAG}"
                                elif "flipkart" in norm_plat:
                                    unique_id = extract_flipkart_pid(raw_url)
                                    if not unique_id:
                                        unique_id = str(hash(card.text[:40]))
                                    clean_base_url = f"https://www.flipkart.com/product/p/itm?pid={unique_id}"
                                    final_url = raw_url if "affid=" in raw_url else f"{clean_base_url}&affid={FLIPKART_AFFID}"
                                
                                if not unique_id or unique_id in history:
                                    continue
                                
                                title = ""
                                try:
                                    # First check if the custom title selector extracts anything
                                    title_el = card.find_element(By.CSS_SELECTOR, config['title_selector'])
                                    # Try to fetch full title from the title attribute first (avoids site truncation)
                                    raw_title = title_el.get_attribute("title")
                                    if not raw_title:
                                        raw_title = title_el.get_attribute("textContent").strip()
                                    if raw_title:
                                        title = re.sub(r'\s+', ' ', raw_title)
                                except Exception:
                                    pass
                                    
                                # If title is still empty, or if it is truncated (ends with ellipsis), check other links inside the card
                                if not title or title.endswith("...") or title.endswith(""):
                                    try:
                                        for a_el in card.find_elements(By.TAG_NAME, "a"):
                                            t_attr = a_el.get_attribute("title")
                                            if t_attr and len(t_attr) > len(title) and not (t_attr.endswith("...") or t_attr.endswith("")):
                                                title = re.sub(r'\s+', ' ', t_attr).strip()
                                                break
                                    except Exception:
                                        pass
                                    
                                if not title:
                                    try:
                                        blacklist = ["limited time deal", "deal of the day", "lowest price", "super deals", "bank offer", "only few left", "mobiles & accessories", "showing 1 -", "other colors/patterns", "colors/patterns", "other colors"]
                                        for text_segment in card.text.split("\n"):
                                            seg = text_segment.strip()
                                            if (len(seg) > 15 
                                                and not seg.startswith("₹") 
                                                and "OFF" not in seg 
                                                and "%" not in seg
                                                and not any(b in seg.lower() for b in blacklist)):
                                                title = seg
                                                break
                                    except Exception:
                                        pass
                                    
                                if not title or len(title) < 5: continue
                                
                                # Skip page-layout search headers
                                if any(h in title.lower() for h in ["showing 1 -", "results for", "showing 1–", "showing 1-"]):
                                    continue
                                
                                # 2. Resilient Adaptive Image Extraction Layer
                                img_url = None
                                try:
                                    img_element = card.find_element(By.CSS_SELECTOR, config['image_selector'])
                                    for attr in ["src", "data-src", "srcset", "original"]:
                                        val = img_element.get_attribute(attr)
                                        if val and "http" in val and "base64" not in val:
                                            img_url = val
                                            break
                                except Exception:
                                    pass
                                
                                if not img_url:
                                    try:
                                        img_element = card.find_element(By.TAG_NAME, "img")
                                        for attr in ["src", "data-src", "srcset", "original"]:
                                            val = img_element.get_attribute(attr)
                                            if val and "http" in val and "base64" not in val:
                                                img_url = val
                                                break
                                    except Exception:
                                        pass
                                
                                price, mrp, true_discount = calculate_true_discount(card.text)
                                
                                if price and mrp and (30.0 <= true_discount <= 98.0):
                                    is_verified_low = verify_historical_low(driver, clean_base_url, price)
                                    
                                    # 3. Safe Dispatch (Will switch to text mode if image fails)
                                    if dispatch_rich_media_alert(platform, title, price, mrp, true_discount, img_url, final_url, is_verified_low):
                                        save_and_flush_history(history, unique_id)
                                        save_deal_to_rich_history(platform, title, price, mrp, true_discount, img_url, final_url, is_verified_low, unique_id)
                                        time.sleep(1)
                                        
                            except Exception:
                                continue
                    except Exception as out_err:
                        logging.error(f"Scraper interface failure on stream {platform}: {out_err}")
                
                # Update loop stats
                scraper_state["scans_completed"] += 1
                scraper_state["last_scan_time"] = time.time()
                logging.info("Inter-stream sequence frame complete. Pausing current execution cycle.")
                
            except webdriver.exceptions.WebDriverException as wde:
                logging.error(f"WebDriver crash recognized: {wde}. Terminating session for auto-recreation.")
                try: driver.quit()
                except Exception: pass
                driver = None
                
            if single_run:
                logging.info("Single-run execution complete. Exiting scraper loop.")
                break
                
            # Responsive sleep cycle check
            for _ in range(60): # 60 seconds sleep, checked every 1 second
                if not scraper_state["is_running"] or scraper_state["scan_trigger"]:
                    break
                time.sleep(1)
                
    except KeyboardInterrupt:
        logging.warning("SIGINT operational interrupt recognized. Turning pipeline off safely.")
    finally:
        if driver is not None:
            driver.quit()

if __name__ == "__main__":
    main()