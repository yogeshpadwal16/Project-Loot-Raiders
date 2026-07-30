import os
import json
import logging
from typing import List, Dict, Any

# Load base configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

def load_mirror_settings() -> Dict[str, Any]:
    settings = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except Exception as e:
            logging.error(f"[Mirror Config] Failed to read settings.json: {e}")
    return settings

# Monitored source channels (can be overridden by environment variable SOURCE_CHANNELS)
DEFAULT_SOURCE_CHANNELS = [
    'Loot_shoppingdeals123',
    'EPM_Deals',
    'idoffers',
    'indiafreestuffin',
    '+jY1FAgS1Wx80Mjk1',
    'countingunique'
]

def get_source_channels() -> List[str]:
    env_channels = os.environ.get("SOURCE_CHANNELS")
    if env_channels:
        return [c.strip() for c in env_channels.split(",") if c.strip()]
    
    settings = load_mirror_settings()
    return settings.get("source_channels", DEFAULT_SOURCE_CHANNELS)

# Telegram Client credentials
TELEGRAM_API_ID = os.environ.get("TELEGRAM_API_ID", "39413198")
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH", "d648fd457db96dffa53ae18d3d1869d8")

def load_string_session() -> str:
    session_str = os.environ.get("TELEGRAM_STRING_SESSION", "").strip()
    if session_str:
        return session_str
    # Fallback: read from TELEGRAM_STRING_SESSION.txt in project root
    session_file = os.path.join(BASE_DIR, "TELEGRAM_STRING_SESSION.txt")
    if os.path.exists(session_file):
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                return content
        except Exception:
            pass
    return ""

TELEGRAM_STRING_SESSION = load_string_session()

# Redis Configuration (For persistent message queues)
REDIS_HOST = os.environ.get("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)

# Pipeline Configuration
WORKER_COUNT = int(os.environ.get("MIRROR_WORKERS", 2))
MAX_RETRIES = int(os.environ.get("MIRROR_MAX_RETRIES", 3))
RETRY_BACKOFF = int(os.environ.get("MIRROR_RETRY_BACKOFF", 10))

# Rate Limits (aiolimiter config: number of requests per period in seconds)
RATE_LIMIT_REQUESTS = int(os.environ.get("MIRROR_RATE_LIMIT_REQUESTS", 5))
RATE_LIMIT_PERIOD = int(os.environ.get("MIRROR_RATE_LIMIT_PERIOD", 10)) # e.g. 5 requests per 10 seconds

# Duplicate Similarity Configuration
SIMILARITY_THRESHOLD = float(os.environ.get("MIRROR_SIMILARITY_THRESHOLD", 85.0)) # 85% match via RapidFuzz
