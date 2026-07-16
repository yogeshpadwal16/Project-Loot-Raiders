import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

def load_settings() -> dict:
    default_settings = {
        "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
        "gemini_api_key": "YOUR_GEMINI_API_KEY",
        "amazon_tag": "lootraiders-21",
        "flipkart_affid": "YOUR_FLIPKART_AFFILIATE_ID",
        "discord_webhook_url": "",
        "min_discount": 30.0,
        "min_deal_price": 299,
        "min_deal_savings": 250,
        "blocklist_keywords": [
            "back cover", "case", "cover", "tempered glass", "screen guard", 
            "screen protector", "camera lens protector", "camera protector",
            "keychain", "pouch", "skin", "strap", "cable", "usb cable", 
            "charging cable", "otg", "ring light", "tripod", "selfie stick",
            "sticker", "decal", "stand", "holder", "mobile holder"
        ],
        "proxy_list": [],
        "proxies_enabled": False,
        "scoring_rules": {
            "min_publish_score": 70.0,
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
            
    # Environmental variable overrides for secure cloud environments (e.g. GitHub Actions)
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        saved["telegram_bot_token"] = env_token
    env_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if env_chat_id:
        saved["telegram_chat_id"] = env_chat_id
    env_gemini_key = os.environ.get("GEMINI_API_KEY")
    if env_gemini_key:
        saved["gemini_api_key"] = env_gemini_key
        
    return saved

def save_settings(settings: dict):
    try:
        # Don't save environment variables overrides back to local settings.json
        to_save = settings.copy()
        if os.environ.get("TELEGRAM_BOT_TOKEN") and to_save.get("telegram_bot_token") == os.environ.get("TELEGRAM_BOT_TOKEN"):
            to_save["telegram_bot_token"] = "YOUR_TELEGRAM_BOT_TOKEN"
        if os.environ.get("TELEGRAM_CHAT_ID") and to_save.get("telegram_chat_id") == os.environ.get("TELEGRAM_CHAT_ID"):
            to_save["telegram_chat_id"] = "YOUR_TELEGRAM_CHAT_ID"
        if os.environ.get("GEMINI_API_KEY") and to_save.get("gemini_api_key") == os.environ.get("GEMINI_API_KEY"):
            to_save["gemini_api_key"] = "YOUR_GEMINI_API_KEY"
            
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=2)
    except Exception as e:
        import logging
        logging.error(f"Failed to save settings.json: {e}")
