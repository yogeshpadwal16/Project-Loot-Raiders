import os
import sys
import logging
import asyncio
import re

# Ensure parent root directory is in sys.path for relative imports under PM2
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

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
    Exposed for core/engine.py background thread launcher & PM2 process.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
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

import signal
import threading
import time

def run_channel_mirror_daemon():
    """
    Runs the Channel Mirroring Engine as a long-running foreground daemon.
    Designed for standalone PM2 service execution (`loot-raiders-mirror`),
    maintaining the process lifecycle and cleanly shutting down on OS signals.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logging.info("[Channel Mirror Daemon] Launching standalone deal mirror process...")

    stop_event = threading.Event()

    def _signal_handler(signum, frame):
        sig_name = str(signum)
        try:
            sig_name = signal.Signals(signum).name
        except Exception:
            pass
        logging.info(f"[Channel Mirror Daemon] Received signal {sig_name}. Initiating graceful shutdown...")
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
    except (ValueError, AttributeError):
        pass # Non-main thread or unsupported platform

    start_channel_mirror()
    logging.info("[Channel Mirror Daemon] Mirror engine is active. Awaiting deals / shutdown signals...")

    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1.0)
    except (KeyboardInterrupt, SystemExit):
        logging.info("[Channel Mirror Daemon] Interrupted by user/system.")
    finally:
        stop_channel_mirror()
        logging.info("[Channel Mirror Daemon] Shutdown complete. Process exiting cleanly.")

if __name__ == '__main__':
    run_channel_mirror_daemon()
