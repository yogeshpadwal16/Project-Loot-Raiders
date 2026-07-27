import logging
import asyncio
import re
from deal_engine.mirroring import (
    start_mirror_engine, stop_mirror_engine, get_listener, get_queue
)

# Non-product URL patterns to skip (search pages, category listings, etc.)
SKIP_URL_PATTERNS = [
    r'amazon\.in/s\?',        # Amazon search pages
    r'flipkart\.com/.*/pr\?', # Flipkart category pages
    r'/gp/goldbox',            # Amazon deals hub
    r'/gp/bestsellers',        # Amazon bestsellers
    r'/gp/new-releases',       # Amazon new releases
]

def _should_skip_url(url: str) -> bool:
    """Check if a URL is a non-product page (search, category, etc.) that should be skipped."""
    for pattern in SKIP_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False

def start_channel_mirror():
    """
    Backward-compatible wrapper to initiate the redesigned modular Deal Mirroring Engine.
    Exposed for core/engine.py background thread launcher.
    """
    logging.info("[Channel Mirror Wrapper] Initiating redesigned modular Deal Mirroring Engine...")
    start_mirror_engine()

def stop_channel_mirror():
    """
    Backward-compatible wrapper to cleanly shutdown the redesigned modular Deal Mirroring Engine.
    Exposed for core/engine.py shutdown hooks.
    """
    logging.info("[Channel Mirror Wrapper] Terminating redesigned modular Deal Mirroring Engine...")
    stop_mirror_engine()

def run_mirror_single_run():
    """
    Backward-compatible wrapper to execute a one-time competitor history sweep.
    Exposed for GitHub Actions run commands.
    """
    logging.info("[Channel Mirror Wrapper] Executing modular history sweep...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(get_listener().run_single_run_scan(limit=20))
    except Exception as e:
        logging.error(f"[Channel Mirror Wrapper] History sweep failed: {e}")
    finally:
        loop.close()

