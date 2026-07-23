import json
import logging
import time
import redis
from typing import Optional, List, Dict, Any
from deal_engine.mirroring.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
from deal_engine.mirroring.schemas import NormalizedMessage

# Redis Queue Keys
QUEUE_PENDING = "loot_raiders:mirror_queue:pending"
QUEUE_PROCESSING = "loot_raiders:mirror_queue:processing"
QUEUE_FAILED = "loot_raiders:mirror_queue:failed"

class RedisMessageQueue:
    def __init__(self):
        try:
            self.client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=5
            )
            self.client.ping()
            logging.info("[Redis Queue] Connected to Redis successfully.")
        except Exception as e:
            logging.error(f"[Redis Queue] Connection failed: {e}")
            self.client = None

    def is_connected(self) -> bool:
        if not self.client:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def enqueue(self, message: NormalizedMessage) -> bool:
        """Push a normalized message to the pending queue."""
        if not self.is_connected():
            logging.error("[Redis Queue] Redis not connected. Message lost!")
            return False
        try:
            data = message.model_dump_json()
            self.client.lpush(QUEUE_PENDING, data)
            logging.info(f"[Redis Queue] Enqueued message {message.message_id} from {message.channel_name} (CorrID: {message.correlation_id})")
            return True
        except Exception as e:
            logging.error(f"[Redis Queue] Enqueue failed: {e}")
            return False

    def dequeue(self, worker_id: str, timeout: int = 5) -> Optional[NormalizedMessage]:
        """
        Pops a message from the pending queue using the RPOPLPUSH pattern for reliability.
        The popped message is temporarily stored in a processing list specific to this worker.
        """
        if not self.is_connected():
            return None
        try:
            # We use worker-specific processing keys to support multiple concurrent workers
            worker_processing_key = f"{QUEUE_PROCESSING}:{worker_id}"
            
            # Atomic transition from pending to processing (RPOPLPUSH)
            # BRPOPLPUSH blocks until a message is available
            data = self.client.brpoplpush(QUEUE_PENDING, worker_processing_key, timeout)
            if data:
                msg_dict = json.loads(data)
                return NormalizedMessage(**msg_dict)
        except Exception as e:
            # Silence expected timeouts
            if "timeout" not in str(e).lower():
                logging.error(f"[Redis Queue] Dequeue failed: {e}")
        return None

    def commit(self, worker_id: str, message: NormalizedMessage) -> bool:
        """Removes the message from the worker's processing list after successful processing."""
        if not self.is_connected():
            return False
        try:
            worker_processing_key = f"{QUEUE_PROCESSING}:{worker_id}"
            data = message.model_dump_json()
            # Remove exact message from the processing list
            self.client.lrem(worker_processing_key, 0, data)
            return True
        except Exception as e:
            logging.error(f"[Redis Queue] Commit failed for message {message.correlation_id}: {e}")
            return False

    def fail(self, worker_id: str, message: NormalizedMessage, error_message: str) -> bool:
        """Move message from processing list to the failed list for diagnostic analysis."""
        if not self.is_connected():
            return False
        try:
            worker_processing_key = f"{QUEUE_PROCESSING}:{worker_id}"
            data_dict = message.model_dump()
            data_dict["error_reason"] = error_message
            data_dict["failed_at"] = time.time()
            data_json = json.dumps(data_dict)
            
            # Atomic transaction to remove from processing and push to failed list
            pipe = self.client.pipeline()
            pipe.lrem(worker_processing_key, 0, message.model_dump_json())
            pipe.lpush(QUEUE_FAILED, data_json)
            pipe.execute()
            return True
        except Exception as e:
            logging.error(f"[Redis Queue] Failed to flag message failure for {message.correlation_id}: {e}")
            return False

    def get_queue_sizes(self) -> Dict[str, int]:
        """Returns the current lengths of the pending and failed queues."""
        if not self.is_connected():
            return {"pending": 0, "failed": 0, "processing": 0}
        try:
            # Sum up all active worker processing keys
            keys = self.client.keys(f"{QUEUE_PROCESSING}:*")
            processing_size = sum(self.client.llen(k) for k in keys) if keys else 0
            
            return {
                "pending": self.client.llen(QUEUE_PENDING),
                "failed": self.client.llen(QUEUE_FAILED),
                "processing": processing_size
            }
        except Exception:
            return {"pending": 0, "failed": 0, "processing": 0}

    def recover_zombies(self) -> int:
        """Re-enqueues messages stuck in worker processing lists for more than 15 minutes (Feature 29)."""
        if not self.is_connected():
            return 0
        count = 0
        try:
            # Find all worker processing lists
            processing_keys = self.client.keys(f"{QUEUE_PROCESSING}:*")
            for key in processing_keys:
                items = self.client.lrange(key, 0, -1)
                for item in items:
                    try:
                        msg_dict = json.loads(item)
                        # If a message is enqueued/scanned more than 900 seconds ago and still processing
                        if time.time() - msg_dict.get("timestamp", 0) > 900:
                            # Atomic move back to pending queue
                            pipe = self.client.pipeline()
                            pipe.lrem(key, 0, item)
                            pipe.lpush(QUEUE_PENDING, item)
                            pipe.execute()
                            count += 1
                            logging.info(f"[Redis Queue] Recovered zombie message {msg_dict.get('message_id')} back to pending queue.")
                    except Exception as parse_err:
                        # If it is unparseable corrupted data, remove it
                        self.client.lrem(key, 0, item)
                        logging.warning(f"[Redis Queue] Removed unparseable zombie entry from processing list: {parse_err}")
        except Exception as e:
            logging.error(f"[Redis Queue] Zombie recovery sweep failed: {e}")
        return count
