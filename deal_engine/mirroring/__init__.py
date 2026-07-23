import logging
import asyncio
from deal_engine.mirroring.queue import RedisMessageQueue
from deal_engine.mirroring.listener import MultiClientMirrorListener
from deal_engine.mirroring.processor import DealMirrorProcessor
from deal_engine.mirroring.scheduler import MirrorScheduler

# Global singleton states
_queue = None
_listener = None
_processor = None
_scheduler = None

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

def start_mirror_engine():
    """Starts the entire redesigned deal mirroring engine pipeline."""
    logging.info("[Mirror Engine] Initializing and starting Deal Mirroring subsystem...")
    
    # 1. Start Workers
    get_processor().start_workers()
    
    # 2. Start Scheduler tasks
    get_scheduler().start()
    
    # 3. Start Multi-Client listener
    asyncio.run_coroutine_threadsafe(get_listener().start_listening(), asyncio.get_event_loop())
    logging.info("[Mirror Engine] Deal Mirroring subsystem pipeline is active.")

def stop_mirror_engine():
    """Stops the entire deal mirroring pipeline cleanly."""
    logging.info("[Mirror Engine] Stopping Deal Mirroring subsystem...")
    
    # 1. Stop Listener
    asyncio.run_coroutine_threadsafe(get_listener().stop_listening(), asyncio.get_event_loop())
    
    # 2. Stop Scheduler
    get_scheduler().stop()
    
    # 3. Stop Workers
    get_processor().stop_workers()
    logging.info("[Mirror Engine] Deal Mirroring subsystem stopped.")
