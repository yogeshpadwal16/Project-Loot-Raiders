import os
import json
import time as _time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# Settings cache with TTL to avoid excessive disk reads
_settings_cache = None
_settings_cache_time = 0
_SETTINGS_CACHE_TTL = 30  # seconds

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
    global _settings_cache, _settings_cache_time
    if _settings_cache is not None and (_time.time() - _settings_cache_time) < _SETTINGS_CACHE_TTL:
        return _settings_cache.copy()
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
        "sendgrid_api_key": "",
        "notification_uris": [],
        "shlink_api_url": "",
        "shlink_api_key": "",
        "n8n_webhook_url": "",
        "scraper_loop_interval": 300,
        "channel_mirror_enabled": False,
        "catalog_monitor_enabled": False,
        "supermarket_monitor_enabled": False,
        "external_price_tracker_enabled": False,
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
        except Exception:
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
    env_sendgrid = os.environ.get("SENDGRID_API_KEY")
    if env_sendgrid:
        saved["sendgrid_api_key"] = env_sendgrid
    env_shlink_url = os.environ.get("SHLINK_API_URL")
    if env_shlink_url:
        saved["shlink_api_url"] = env_shlink_url
    env_shlink_key = os.environ.get("SHLINK_API_KEY")
    if env_shlink_key:
        saved["shlink_api_key"] = env_shlink_key
        
    # SMTP email configuration overrides
    env_smtp_server = os.environ.get("SMTP_SERVER")
    if env_smtp_server:
        saved["smtp_server"] = env_smtp_server
    env_smtp_port = os.environ.get("SMTP_PORT")
    if env_smtp_port:
        try: saved["smtp_port"] = int(env_smtp_port)
        except (ValueError, TypeError): pass
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
        
    # Dynamic environmental overrides for notification URIs
    env_uris = os.environ.get("NOTIFICATION_URIS")
    if env_uris:
        try:
            import json as _json
            saved["notification_uris"] = _json.loads(env_uris)
        except Exception:
            saved["notification_uris"] = [u.strip() for u in env_uris.split(",") if u.strip()]
            
    # Backward compatibility conversion: translate legacy fields to Apprise format if URIs not configured
    if not saved.get("notification_uris"):
        uris = []
        # Telegram
        tg_token = saved.get("telegram_bot_token")
        tg_chat = saved.get("telegram_chat_id")
        if tg_token and tg_chat and "YOUR_TELEGRAM" not in tg_token and tg_token.strip() != "" and tg_chat.strip() != "":
            # Normalize chat ID for Apprise: must start with @ or be numeric
            uris.append(f"tgram://{tg_token.strip()}/{tg_chat.strip()}")
            
        # Discord
        discord_url = saved.get("discord_webhook_url")
        if discord_url and "discord.com" in discord_url.lower():
            parts = discord_url.split('/api/webhooks/')
            if len(parts) > 1:
                webhook_parts = parts[1].split('?')[0].split('/')
                if len(webhook_parts) >= 2:
                    uris.append(f"discord://{webhook_parts[0]}/{webhook_parts[1]}")
                    
        # SMTP
        smtp_srv = saved.get("smtp_server")
        smtp_u = saved.get("smtp_username")
        smtp_p = saved.get("smtp_password")
        smtp_f = saved.get("smtp_from")
        smtp_t = saved.get("smtp_to")
        if smtp_srv and smtp_u and smtp_p and smtp_f and smtp_t:
            import urllib.parse
            srv_esc = urllib.parse.quote(smtp_srv)
            u_esc = urllib.parse.quote(smtp_u)
            p_esc = urllib.parse.quote(smtp_p)
            f_esc = urllib.parse.quote(smtp_f)
            t_esc = urllib.parse.quote(smtp_t)
            port = saved.get("smtp_port", 587)
            uris.append(f"mailt://{u_esc}:{p_esc}@{srv_esc}:{port}?from={f_esc}&to={t_esc}")
            
        saved["notification_uris"] = uris
    
    _settings_cache = saved.copy()
    _settings_cache_time = _time.time()
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
            ("SENDGRID_API_KEY", "sendgrid_api_key"),
            ("SMTP_SERVER", "smtp_server"),
            ("SMTP_PORT", "smtp_port"),
            ("SMTP_USERNAME", "smtp_username"),
            ("SMTP_PASSWORD", "smtp_password"),
            ("SMTP_FROM", "smtp_from"),
            ("SMTP_TO", "smtp_to"),
            ("NOTIFICATION_URIS", "notification_uris"),
            ("SHLINK_API_URL", "shlink_api_url"),
            ("SHLINK_API_KEY", "shlink_api_key"),
        ]:
            if os.environ.get(env_key) and to_save.get(setting_key) == os.environ.get(env_key):
                to_save[setting_key] = f"YOUR_{env_key}"
            
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=2)
        global _settings_cache
        _settings_cache = None  # Invalidate cache after save
    except Exception as e:
        import logging
        logging.error(f"Failed to save settings.json: {e}")
