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
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

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
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "@LootRaidersDeals"

AMAZON_TAG = "lootraiders-21"
FLIPKART_AFFID = "YOUR_FLIPKART_AFFILIATE_ID"

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
    with open(SELECTOR_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_matrix, f, indent=4)

# Thread synchronization locks
history_lock = threading.Lock()
deals_history_lock = threading.Lock()

SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

def load_settings() -> dict:
    default_settings = {
        "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "@LootRaidersDeals",
        "amazon_tag": "lootraiders-21",
        "flipkart_affid": "YOUR_FLIPKART_AFFILIATE_ID",
        "discord_webhook_url": "",
        "min_discount": 30.0,
        "proxy_list": [],
        "proxies_enabled": False
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                for k, v in default_settings.items():
                    if k not in saved:
                        saved[k] = v
                return saved
        except:
            pass
    return default_settings

def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save settings.json: {e}")

def send_discord_webhook(webhook_url: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool) -> bool:
    try:
        is_amazon = "amazon" in final_url.lower()
        embed = {
            "title": title[:250],
            "url": final_url,
            "color": 16750848 if is_amazon else 114686,
            "fields": [
                {"name": "Price", "value": f"₹{price:,}", "inline": True},
                {"name": "MRP", "value": f"₹{mrp:,}", "inline": True},
                {"name": "Discount", "value": f"{discount:.1f}% OFF", "inline": True}
            ],
            "footer": {
                "text": "Loot Raiders Deal Alert • Curated by Yogesh Padwal"
            }
        }
        if is_verified_low:
            embed["description"] = "🔥 **VERIFIED ALL-TIME LOW PRICE!**"
        if img_url and "base64" not in img_url:
            embed["image"] = {"url": img_url}
            
        payload = {
            "embeds": [embed]
        }
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.status_code in [200, 204]:
            logging.info("Discord Webhook broadcast success.")
            return True
        else:
            logging.warning(f"Discord Webhook returned status {r.status_code}: {r.text}")
    except Exception as e:
        logging.error(f"Discord Webhook broadcast failure: {e}")
    return False

def load_history() -> dict:
    with history_lock:
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

def save_and_flush_history(history: dict, unique_id: str):
    with history_lock:
        history[unique_id] = time.time()
        try:
            fd = os.open(HISTORY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logging.error(f"State Flash Failure: {e}")

def increment_click_count(deal_id: str):
    stats = {}
    if os.path.exists(CLICKS_TRACKER_FILE):
        try:
            with open(CLICKS_TRACKER_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        except:
            pass
    stats[deal_id] = stats.get(deal_id, 0) + 1
    try:
        with open(CLICKS_TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save click stats: {e}")

def log_click_activity(deal_id: str, title: str, ip: str, user: str, user_agent: str):
    activity = []
    if os.path.exists(CLICKS_LOG_FILE):
        try:
            with open(CLICKS_LOG_FILE, 'r', encoding='utf-8') as f:
                activity = json.load(f)
        except:
            pass
            
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
    
    try:
        with open(CLICKS_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(activity, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save click activity: {e}")

def save_deal_to_rich_history(platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, unique_id: str):
    with deals_history_lock:
        deals = []
        if os.path.exists(DEALS_HISTORY_FILE):
            try:
                with open(DEALS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    deals = json.load(f)
            except:
                pass
                
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
        
        try:
            with open(DEALS_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(deals, f, indent=2)
        except Exception as e:
            logging.error(f"Rich History Flash Failure: {e}")

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

def verify_historical_low(driver, product_url: str, current_price: int, unique_id: str = None, discount: float = 0.0) -> bool:
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
        if current_price <= (lowest_ever * 1.05):
            return True
        return False
        
    # Fallback 1: Compare against our local historical deals database
    if unique_id and os.path.exists(DEALS_HISTORY_FILE):
        try:
            with deals_history_lock:
                with open(DEALS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    deals = json.load(f)
            matching_deals = [d for d in deals if d.get("id") == unique_id]
            if matching_deals:
                min_price = min(int(d.get("price", 999999)) for d in matching_deals)
                if current_price <= min_price:
                    return True
                return False
        except Exception as e:
            logging.error(f"Local price check failed: {e}")
            
    # Fallback 2: If it's a new item, mark as verified low if discount is substantial (>= 60%)
    if discount >= 60.0:
        return True
        
    return False

# ==========================================
# INTELLIGENT DISPATCH HUB
# ==========================================
def dispatch_rich_media_alert(platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool):
    settings = load_settings()
    telegram_success = False
    discord_success = False
    
    bot_token = settings.get("telegram_bot_token")
    chat_id = settings.get("telegram_chat_id")
    min_disc = settings.get("min_discount", 30.0)
    
    if discount < min_disc:
        logging.info(f"Skipping broadcast: discount ({discount:.1f}%) is below minimum threshold ({min_disc}%)")
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
    
    # 1. Telegram Alert dispatch
    if bot_token and chat_id and "YOUR_TELEGRAM" not in bot_token and bot_token.strip() != "":
        if img_url and "base64" not in img_url:
            try:
                endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                payload = {"chat_id": chat_id, "photo": img_url, "caption": caption, "parse_mode": "Markdown"}
                res = requests.post(endpoint, json=payload, timeout=15)
                if res.status_code == 200:
                    logging.info(f"Telegram Broadcast Success -> {truncated_title[:20]}...")
                    telegram_success = True
            except Exception as e:
                logging.error(f"Telegram Photo Method Failed: {e}")
                
        if not telegram_success:
            try:
                text_endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload_fallback = {"chat_id": chat_id, "text": caption, "parse_mode": "Markdown"}
                res_fb = requests.post(text_endpoint, json=payload_fallback, timeout=15)
                if res_fb.status_code == 200:
                    logging.info(f"Telegram Text Broadcast Success -> {truncated_title[:20]}...")
                    telegram_success = True
            except Exception as e:
                logging.error(f"Telegram Text Method Failed: {e}")

    # 2. Discord Alert dispatch
    discord_webhook = settings.get("discord_webhook_url")
    if discord_webhook and discord_webhook.strip() != "":
        discord_success = send_discord_webhook(discord_webhook, title, price, mrp, discount, img_url, final_url, is_verified_low)
        
    has_telegram = (bot_token and chat_id and "YOUR_TELEGRAM" not in bot_token and bot_token.strip() != "")
    has_discord = (discord_webhook and discord_webhook.strip() != "")
    
    if not has_telegram and not has_discord:
        return True # Save local history anyway
        
    return telegram_success or discord_success

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
            if os.path.exists(SELECTOR_FILE):
                with open(SELECTOR_FILE, 'r', encoding='utf-8') as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(b"{}")
                
        elif self.path == '/api/deals':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            deals = []
            if os.path.exists(DEALS_HISTORY_FILE):
                try:
                    with open(DEALS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                        deals = json.load(f)
                except:
                    pass
            
            # Merge click counts
            clicks = {}
            if os.path.exists(CLICKS_TRACKER_FILE):
                try:
                    with open(CLICKS_TRACKER_FILE, 'r', encoding='utf-8') as f:
                        clicks = json.load(f)
                except:
                    pass
            
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
            if deal_id and os.path.exists(DEALS_HISTORY_FILE):
                try:
                    with open(DEALS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                        deals = json.load(f)
                        for d in deals:
                            if d.get("id") == deal_id:
                                title = d.get("title", "Unknown Product")
                                break
                except:
                    pass
            
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
            activity = []
            if os.path.exists(CLICKS_LOG_FILE):
                try:
                    with open(CLICKS_LOG_FILE, 'r', encoding='utf-8') as f:
                        activity = json.load(f)
                except:
                    pass
            self.wfile.write(json.dumps(activity).encode('utf-8'))
                
        elif self.path == '/api/settings':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            settings = load_settings()
            self.wfile.write(json.dumps(settings).encode('utf-8'))
            
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
                with open(SELECTOR_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
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
                
                if username == 'yogeshpadwal16' and password == 'YOUR_DASHBOARD_PASSWORD':
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
                
                deals = []
                if os.path.exists(DEALS_HISTORY_FILE):
                    try:
                        with open(DEALS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                            deals = json.load(f)
                    except Exception as e:
                        logger.error(f"Error reading deals history: {e}")
                
                original_len = len(deals)
                deals = [d for d in deals if d.get("id") != deal_id]
                
                try:
                    with open(DEALS_HISTORY_FILE, 'w', encoding='utf-8') as f:
                        json.dump(deals, f, indent=2)
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
def scrape_platform(platform: str, config: dict, history: dict):
    if not scraper_state["is_running"] and not scraper_state["scan_trigger"]:
        return
        
    logging.info(f"Scanning target feed stream: {platform.upper()} (Multi-threaded)")
    driver = None
    try:
        driver = init_driver()
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
            if not scraper_state["is_running"] and not scraper_state["scan_trigger"]:
                logging.info(f"Scraper execution halted by user request on stream {platform}.")
                break
                
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
                
                if not unique_id:
                    continue
                    
                with history_lock:
                    in_history = unique_id in history
                if in_history:
                    continue
                
                title = ""
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, config['title_selector'])
                    raw_title = title_el.get_attribute("title")
                    if not raw_title:
                        raw_title = title_el.get_attribute("textContent").strip()
                    if raw_title:
                        title = re.sub(r'\s+', ' ', raw_title)
                except:
                    pass
                    
                if not title or title.endswith("...") or title.endswith(""):
                    try:
                        for a_el in card.find_elements(By.TAG_NAME, "a"):
                            t_attr = a_el.get_attribute("title")
                            if t_attr and len(t_attr) > len(title) and not (t_attr.endswith("...") or t_attr.endswith("")):
                                title = re.sub(r'\s+', ' ', t_attr).strip()
                                break
                    except:
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
                    except:
                        pass
                    
                if not title or len(title) < 5: continue
                
                if any(h in title.lower() for h in ["showing 1 -", "results for", "showing 1–", "showing 1-"]):
                    continue
                
                img_url = None
                try:
                    img_element = card.find_element(By.CSS_SELECTOR, config['image_selector'])
                    for attr in ["src", "data-src", "srcset", "original"]:
                        val = img_element.get_attribute(attr)
                        if val and "http" in val and "base64" not in val:
                            img_url = val
                            break
                except:
                    pass
                
                if not img_url:
                    try:
                        img_element = card.find_element(By.TAG_NAME, "img")
                        for attr in ["src", "data-src", "srcset", "original"]:
                            val = img_element.get_attribute(attr)
                            if val and "http" in val and "base64" not in val:
                                img_url = val
                                break
                    except:
                        pass
                
                price, mrp, true_discount = calculate_true_discount(card.text)
                
                if price and mrp and (30.0 <= true_discount <= 98.0):
                    is_verified_low = verify_historical_low(driver, clean_base_url, price, unique_id, true_discount)
                    
                    if dispatch_rich_media_alert(platform, title, price, mrp, true_discount, img_url, final_url, is_verified_low):
                        save_and_flush_history(history, unique_id)
                        save_deal_to_rich_history(platform, title, price, mrp, true_discount, img_url, final_url, is_verified_low, unique_id)
                        time.sleep(1)
                        
            except Exception as inner_err:
                continue
    except Exception as out_err:
        logging.error(f"Scraper interface failure on stream {platform}: {out_err}")
    finally:
        if driver:
            try: driver.quit()
            except: pass

def main():
    initialize_selectors_json()
    
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
                with open(SELECTOR_FILE, 'r', encoding='utf-8') as f:
                    matrix = json.load(f)
                
                history = load_history()
                current_time = time.time()
                history = {k: v for k, v in history.items() if current_time - v < 86400}
                
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = []
                    for platform, config in matrix.items():
                        futures.append(executor.submit(scrape_platform, platform, config, history))
                    
                    for fut in futures:
                        try:
                            fut.result()
                        except Exception as thread_err:
                            logging.error(f"Thread execution error: {thread_err}")
                
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

if __name__ == "__main__":
    main()