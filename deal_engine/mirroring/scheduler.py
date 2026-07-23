import logging
import time
import os
import psutil
from apscheduler.schedulers.background import BackgroundScheduler
from database.db_session import SessionLocal
from knowledge_base.models import SystemHealth, ProcessingLog
from deal_engine.mirroring.queue import RedisMessageQueue

class MirrorScheduler:
    def __init__(self, queue: RedisMessageQueue):
        self.queue = queue
        self.scheduler = BackgroundScheduler()
        
    def start(self):
        """Starts background scheduled tasks."""
        # 1. Health Log Sweep (every 5 minutes)
        self.scheduler.add_job(
            self._log_system_health,
            'interval',
            minutes=5,
            id='health_check_job',
            replace_existing=True
        )
        
        # 2. Zombie Queue Clean (every 10 minutes)
        self.scheduler.add_job(
            self._recover_zombies,
            'interval',
            minutes=10,
            id='zombie_recovery_job',
            replace_existing=True
        )
        
        # 3. Old Logs Cleanup (every 12 hours)
        self.scheduler.add_job(
            self._cleanup_old_logs,
            'interval',
            hours=12,
            id='logs_cleanup_job',
            replace_existing=True
        )
        
        self.scheduler.start()
        logging.info("[Mirror Scheduler] APScheduler background tasks started successfully.")

    def stop(self):
        """Stops background scheduled tasks cleanly."""
        self.scheduler.shutdown()
        logging.info("[Mirror Scheduler] APScheduler background tasks shut down.")

    def _log_system_health(self):
        """Gathers CPU, memory, and Redis queue size metrics and saves them to the DB."""
        db = SessionLocal()
        try:
            # 1. Gather Queue Sizes
            q_sizes = self.queue.get_queue_sizes()
            
            # 2. Gather System Usage
            process = psutil.Process(os.getpid())
            cpu_usage = psutil.cpu_percent(interval=None)
            mem_usage = process.memory_info().rss / (1024 * 1024) # MB
            
            metrics = {
                "queue_pending_size": float(q_sizes.get("pending", 0)),
                "queue_processing_size": float(q_sizes.get("processing", 0)),
                "queue_failed_size": float(q_sizes.get("failed", 0)),
                "system_cpu_usage": cpu_usage,
                "system_memory_usage_mb": mem_usage
            }
            
            for name, val in metrics.items():
                health_record = SystemHealth(
                    metric_name=name,
                    metric_value=val,
                    timestamp=time.time()
                )
                db.add(health_record)
            db.commit()
            logging.info(f"[Mirror Scheduler] Recorded system health stats: CPU={cpu_usage}%, MEM={mem_usage:.1f}MB, PendingQueue={q_sizes.get('pending')}")
        except Exception as e:
            logging.error(f"[Mirror Scheduler] Failed recording health stats: {e}")
        finally:
            db.close()

    def _recover_zombies(self):
        """Trigger queue recovery sweep for stuck items."""
        logging.info("[Mirror Scheduler] Running zombie message queue recovery sweep...")
        recovered_count = self.queue.recover_zombies()
        if recovered_count > 0:
            logging.info(f"[Mirror Scheduler] Successfully enqueued {recovered_count} zombie tasks back to pending queue.")

    def _cleanup_old_logs(self, max_days: int = 7):
        """Deletes database logs and records older than 7 days to maintain database storage health."""
        logging.info(f"[Mirror Scheduler] Running logs database clean (Retention: {max_days} days)...")
        db = SessionLocal()
        try:
            cutoff = time.time() - (max_days * 86400)
            
            # 1. Delete old system health entries
            health_deleted = db.query(SystemHealth).filter(SystemHealth.timestamp < cutoff).delete()
            
            # 2. Delete old processing logs
            logs_deleted = db.query(ProcessingLog).filter(ProcessingLog.timestamp < cutoff).delete()
            
            db.commit()
            logging.info(f"[Mirror Scheduler] Cleanup complete. Deleted {health_deleted} health logs and {logs_deleted} processing logs.")
        except Exception as e:
            logging.error(f"[Mirror Scheduler] Logs database cleanup failed: {e}")
        finally:
            db.close()
