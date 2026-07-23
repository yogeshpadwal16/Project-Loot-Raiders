import logging
import asyncio
import threading
from deal_engine.mirroring import (
    start_mirror_engine, stop_mirror_engine, get_listener, get_queue
)

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
