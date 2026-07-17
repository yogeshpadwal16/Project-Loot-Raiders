import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

def load_dotenv():
    dotenv_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(dotenv_path):
        try:
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ[key] = val
        except Exception as e:
            pass

def load_settings() -> dict:
    load_dotenv()
    
    default_settings = {
        "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
        "telegram_invite_link": "https://t.me/LootRaidersDeals",
        "gemini_api_key": "YOUR_GEMINI_API_KEY",
        "amazon_tag": "YOUR_AMAZON_TAG",
        "flipkart_affid": "YOUR_FLIPKART_AFFILIATE_ID",
        "cuelinks_pub_id": "",
        "earnkaro_pub_id": "",
        "discord_webhook_url": "",
        "min_discount": 30.0,
        "min_deal_price": 299,
        "min_deal_savings": 250,
        "smtp_server": "",
        "smtp_port": 587,
        "smtp_username": "",
        "smtp_password": "",
        "smtp_from": "",
        "smtp_to": "",
        "blocklist_keywords": [
            "back cover", "case", "cover", "tempered glass", "screen guard", 
            "screen protector", "camera lens protector", "camera protector",
            "keychain", "pouch", "skin", "strap", "cable", "usb cable", 
            "charging cable", "otg", "ring light", "tripod", "selfie stick",
            "sticker", "decal", "stand", "holder", "mobile holder"
        ],
        "proxy_list": [],
        "proxies_enabled": False,
        "scraper_concurrency": 1,
        "scoring_rules": {
            "min_publish_score": 45.0,
            "weights": {
                "discount": 0.35,
                "savings": 0.20,
                "history": 0.25,
                "urgency": 0.10,
                "trust": 0.10
            },
            "retailer_trust_scores": {
                "amazon_master_lightning_deals": 95,
                "amazon_sitewide_search_deals": 80,
                "flipkart_sitewide_offers": 80,
                "flipkart_clearance_master_feed": 85
            }
        }
    }
    
    saved = default_settings.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for k, v in loaded.items():
                    saved[k] = v
        except:
            pass
            
    # Environmental variable overrides for secure production environments
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        saved["telegram_bot_token"] = env_token
    env_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if env_chat_id:
        saved["telegram_chat_id"] = env_chat_id
    env_invite_link = os.environ.get("TELEGRAM_INVITE_LINK")
    if env_invite_link:
        saved["telegram_invite_link"] = env_invite_link
    env_gemini_key = os.environ.get("GEMINI_API_KEY")
    if env_gemini_key:
        saved["gemini_api_key"] = env_gemini_key
    env_flipkart = os.environ.get("FLIPKART_AFFID")
    if env_flipkart:
        saved["flipkart_affid"] = env_flipkart
    env_amazon = os.environ.get("AMAZON_TAG")
    if env_amazon:
        saved["amazon_tag"] = env_amazon
    env_discord = os.environ.get("DISCORD_WEBHOOK_URL")
    if env_discord:
        saved["discord_webhook_url"] = env_discord
    env_cuelinks = os.environ.get("CUELINKS_PUB_ID")
    if env_cuelinks:
        saved["cuelinks_pub_id"] = env_cuelinks
    env_earnkaro = os.environ.get("EARNKARO_PUB_ID")
    if env_earnkaro:
        saved["earnkaro_pub_id"] = env_earnkaro
        
    # SMTP email configuration overrides
    env_smtp_server = os.environ.get("SMTP_SERVER")
    if env_smtp_server:
        saved["smtp_server"] = env_smtp_server
    env_smtp_port = os.environ.get("SMTP_PORT")
    if env_smtp_port:
        try: saved["smtp_port"] = int(env_smtp_port)
        except: pass
    env_smtp_user = os.environ.get("SMTP_USERNAME")
    if env_smtp_user:
        saved["smtp_username"] = env_smtp_user
    env_smtp_pass = os.environ.get("SMTP_PASSWORD")
    if env_smtp_pass:
        saved["smtp_password"] = env_smtp_pass
    env_smtp_from = os.environ.get("SMTP_FROM")
    if env_smtp_from:
        saved["smtp_from"] = env_smtp_from
    env_smtp_to = os.environ.get("SMTP_TO")
    if env_smtp_to:
        saved["smtp_to"] = env_smtp_to
        
    return saved

def save_settings(settings: dict):
    try:
        # Don't save environment variables overrides back to local settings.json
        to_save = settings.copy()
        for env_key, setting_key in [
            ("TELEGRAM_BOT_TOKEN", "telegram_bot_token"),
            ("TELEGRAM_CHAT_ID", "telegram_chat_id"),
            ("TELEGRAM_INVITE_LINK", "telegram_invite_link"),
            ("GEMINI_API_KEY", "gemini_api_key"),
            ("FLIPKART_AFFID", "flipkart_affid"),
            ("AMAZON_TAG", "amazon_tag"),
            ("CUELINKS_PUB_ID", "cuelinks_pub_id"),
            ("EARNKARO_PUB_ID", "earnkaro_pub_id"),
            ("DISCORD_WEBHOOK_URL", "discord_webhook_url"),
            ("SMTP_SERVER", "smtp_server"),
            ("SMTP_PORT", "smtp_port"),
            ("SMTP_USERNAME", "smtp_username"),
            ("SMTP_PASSWORD", "smtp_password"),
            ("SMTP_FROM", "smtp_from"),
            ("SMTP_TO", "smtp_to"),
        ]:
            if os.environ.get(env_key) and to_save.get(setting_key) == os.environ.get(env_key):
                to_save[setting_key] = f"YOUR_{env_key}"
            
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=2)
    except Exception as e:
        import logging
        logging.error(f"Failed to save settings.json: {e}")
