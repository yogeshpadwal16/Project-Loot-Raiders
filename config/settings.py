import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        import logging
        logging.error(f"Failed to save settings.json: {e}")
