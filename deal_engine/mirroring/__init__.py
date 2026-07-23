import logging
import asyncio
import threading
from deal_engine.mirroring.queue import RedisMessageQueue
from deal_engine.mirroring.listener import MultiClientMirrorListener
from deal_engine.mirroring.processor import DealMirrorProcessor
from deal_engine.mirroring.scheduler import MirrorScheduler

# Global singleton states
_queue = None
_listener = None
_processor = None
_scheduler = None
_loop = None
_thread = None

def get_queue() -> RedisMessageQueue:
    global _queue
    if _queue is None:
        _queue = RedisMessageQueue()
    return _queue

def get_listener() -> MultiClientMirrorListener:
    global _listener
    if _listener is None:
        _listener = MultiClientMirrorListener(get_queue())
    return _listener

def get_processor() -> DealMirrorProcessor:
    global _processor
    if _processor is None:
        _processor = DealMirrorProcessor(get_queue())
    return _processor

def get_scheduler() -> MirrorScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = MirrorScheduler(get_queue())
    return _scheduler

def _run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def start_background_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    if _loop is None:
        _loop = asyncio.new_event_loop()
        _thread = threading.Thread(target=_run_loop, args=(_loop,), name="MirrorAsyncioLoop", daemon=True)
        _thread.start()
        logging.info("[Mirror Engine] Background asyncio event loop thread started.")
    return _loop

def start_mirror_engine():
    """Starts the entire redesigned deal mirroring engine pipeline."""
    logging.info("[Mirror Engine] Initializing and starting Deal Mirroring subsystem...")
    
    # 1. Start Workers
    get_processor().start_workers()
    
    # 2. Start Scheduler tasks
    get_scheduler().start()
    
    # 3. Start background event loop
    loop = start_background_loop()
    
    # 4. Start Multi-Client listener
    asyncio.run_coroutine_threadsafe(get_listener().start_listening(), loop)
    logging.info("[Mirror Engine] Deal Mirroring subsystem pipeline is active.")

def stop_mirror_engine():
    """Stops the entire deal mirroring pipeline cleanly."""
    global _loop
    logging.info("[Mirror Engine] Stopping Deal Mirroring subsystem...")
    
    # 1. Stop Listener
    if _loop:
        future = asyncio.run_coroutine_threadsafe(get_listener().stop_listening(), _loop)
        try:
            future.result(timeout=10)
        except Exception as e:
            logging.warning(f"[Mirror Engine] Error stopping listener: {e}")
            
    # 2. Stop Scheduler
    get_scheduler().stop()
    
    # 3. Stop Workers
    get_processor().stop_workers()
    
    # 4. Stop event loop
    if _loop:
        _loop.call_soon_threadsafe(_loop.stop)
        _loop = None
        
    logging.info("[Mirror Engine] Deal Mirroring subsystem stopped.")
