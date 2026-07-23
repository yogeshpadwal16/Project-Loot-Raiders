import time
import logging
import threading
import uuid
from typing import List, Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from deal_engine.mirroring.config import WORKER_COUNT, SIMILARITY_THRESHOLD
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.queue import RedisMessageQueue
from deal_engine.mirroring.deduplicator import IntelligentDeduplicator

# Import core business logic from other modules
from deal_engine.deal_processor import extract_store_url_from_competitor_landing_page
from deal_engine.scorer import calculate_deal_score, should_publish_deal
from deal_engine.notifier import enqueue_alert
from core.engine import scrape_product_details
from database.operations import verify_historical_low, save_deal_to_db
from utils.affiliate import get_best_affiliate_url, generate_auto_cart_url
from config.settings import load_settings

class DealMirrorProcessor:
    def __init__(self, queue: RedisMessageQueue):
        self.queue = queue
        self.workers: List[threading.Thread] = []
        self.should_stop = False

    def start_workers(self):
        """Spawns the configured number of background queue worker threads."""
        self.should_stop = False
        for i in range(WORKER_COUNT):
            worker_id = f"worker-{i+1}-{str(uuid.uuid4())[:8]}"
            t = threading.Thread(
                target=self._worker_loop,
                args=(worker_id,),
                name=f"Mirror-Queue-{worker_id}",
                daemon=True
            )
            t.start()
            self.workers.append(t)
            logging.info(f"[Mirror Processor] Spawned worker thread: {t.name}")

    def stop_workers(self):
        """Signals worker threads to exit cleanly."""
        self.should_stop = True
        logging.info("[Mirror Processor] Stopping all queue worker threads...")

    def _worker_loop(self, worker_id: str):
        """Worker loop that pulls tasks from Redis queue and processes them."""
        # Warmup delay
        time.sleep(1)
        while not self.should_stop:
            try:
                # Dequeue a message using the reliable queue pattern
                message = self.queue.dequeue(worker_id, timeout=5)
                if not message:
                    continue
                
                logging.info(f"[{worker_id}] Dequeued message {message.message_id} (CorrID: {message.correlation_id})")
                self._process_message_with_retries(worker_id, message)
            except Exception as e:
                logging.error(f"[{worker_id}] Critical worker loop exception: {e}")
                time.sleep(2)

    def _process_message_with_retries(self, worker_id: str, message: NormalizedMessage):
        """Wrap the message processing in a try/except to capture failure logs."""
        correlation_id = message.correlation_id
        db = SessionLocal()
        
        try:
            # We use a Tenacity-retried helper for the actual processing
            self._execute_pipeline(message)
            
            # Commit (delete from processing list) on success
            self.queue.commit(worker_id, message)
            
            # Log success
            self._log_stage(db, correlation_id, "pipeline", "success", "Deal processed and enqueued successfully.")
            logging.info(f"[{worker_id}] Message {message.message_id} processed successfully.")
        except Exception as err:
            err_msg = str(err)
            logging.error(f"[{worker_id}] Message {message.message_id} failed: {err_msg}")
            
            # Flag failure in Redis queue (move to failed list)
            self.queue.fail(worker_id, message, err_msg)
            
            # Log failure in Database
            self._log_stage(db, correlation_id, "pipeline", "failure", err_msg)
        finally:
            db.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _execute_pipeline(self, message: NormalizedMessage):
        """Decoupled processing pipeline steps matching the required architecture."""
        correlation_id = message.correlation_id
        
        # 1. Verify links exist in message
        if not message.extracted_urls:
            logging.info(f"[Mirror Pipeline] No URLs in message {message.message_id}. Skipping.")
            return

        db = SessionLocal()
        try:
            for raw_url in message.extracted_urls:
                # Skip known bad paths
                from deal_engine.channel_mirror import _should_skip_url
                if _should_skip_url(raw_url):
                    logging.info(f"[Mirror Pipeline] Skipping non-deal link: {raw_url}")
                    continue
                
                # 2. Expand link
                expanded_url = self._expand_url_with_retry(raw_url)
                
                # Resolve competitor landing pages
                store_domains = ["amazon.in", "flipkart.com", "myntra.com", "ajio.com", "meesho.com", "tatacliq.com", "jiomart.com"]
                if not any(d in expanded_url.lower() for d in store_domains):
                    logging.info(f"[Mirror Pipeline] Non-store URL: {expanded_url}. Scanning landing page...")
                    extracted = extract_store_url_from_competitor_landing_page(expanded_url)
                    if extracted:
                        expanded_url = self._expand_url_with_retry(extracted)
                        
                # 3. Extract platform and ID
                platform, unique_id = self._parse_url_metadata(expanded_url)
                if not platform or not unique_id:
                    logging.warning(f"[Mirror Pipeline] Could not resolve store identifier for: {expanded_url}")
                    continue
                    
                # 4. Scrape details
                scraped = scrape_product_details(expanded_url)
                title = scraped.get("title", "Product Deal")
                price = scraped.get("price", 0)
                mrp = scraped.get("mrp", 0)
                img_url = scraped.get("image_url", "")
                rating = scraped.get("rating")
                reviews = scraped.get("reviews")
                has_bank_offer = scraped.get("has_bank_offer", False)
                
                if price == 0:
                    logging.warning(f"[Mirror Pipeline] Scraped price is 0. Skipping.")
                    continue
                    
                discount = 0.0
                if mrp > price:
                    discount = ((mrp - price) / mrp) * 100.0
                    
                # 5. Duplicate Detection (Intelligent RapidFuzz check)
                is_dup, matched_id = IntelligentDeduplicator.find_duplicate(title, price, time_window_hours=24)
                if is_dup:
                    # Update price history under the matched parent ID
                    logging.info(f"[Mirror Pipeline] Deduplicated: '{title[:30]}' mapped to existing deal {matched_id}")
                    unique_id = matched_id
                    
                # 6. Check price trends
                is_verified_low = True
                try:
                    from utils.playwright_adapter import get_playwright_driver
                    settings = load_settings()
                    temp_driver = get_playwright_driver(settings)
                    try:
                        is_verified_low = verify_historical_low(temp_driver, expanded_url, price, unique_id, discount)
                    finally:
                        temp_driver.quit()
                except Exception as verify_err:
                    logging.warning(f"[Mirror Pipeline] Historical check failed, defaulting to True: {verify_err}")
                    
                # 7. Scorer & Database Commit
                deal_score = calculate_deal_score(
                    platform, price, mrp, discount, is_verified_low, False,
                    product_id=unique_id, title=title, rating=rating, reviews=reviews,
                    has_bank_offer=has_bank_offer
                )
                
                unique_id = save_deal_to_db(platform, title, price, mrp, discount, img_url, expanded_url, is_verified_low, unique_id, deal_score)
                
                # 8. Affiliate URL Generator
                settings = load_settings()
                final_url = get_best_affiliate_url(expanded_url, platform, settings)
                auto_cart_url = generate_auto_cart_url(expanded_url, platform, settings)
                
                # 9. Publisher dispatch
                enqueue_alert(
                    platform=platform,
                    title=title,
                    price=price,
                    mrp=mrp,
                    discount=discount,
                    img_url=img_url,
                    final_url=final_url,
                    is_verified_low=is_verified_low,
                    deal_score=deal_score,
                    unique_id=unique_id,
                    bank_offers=scraped.get("bank_offers", []),
                    coupon_detail=scraped.get("coupon_detail", ""),
                    review_grade=scraped.get("review_grade", "N/A"),
                    auto_cart_url=auto_cart_url
                )
                logging.info(f"[Mirror Pipeline] Deal alerts enqueued for publishing: {title[:30]}")
        finally:
            db.close()

    def _expand_url_with_retry(self, url: str) -> str:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
        try:
            res = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
            if res.status_code >= 400 or res.url == url:
                res = requests.get(url, headers=headers, allow_redirects=True, stream=True, timeout=10)
            return res.url
        except Exception:
            return url

    def _parse_url_metadata(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        url_lower = url.lower()
        if "amazon.in" in url_lower:
            from utils.parser import extract_amazon_asin
            asin = extract_amazon_asin(url)
            return "amazon", asin
        elif "flipkart.com" in url_lower:
            from utils.parser import extract_flipkart_pid
            pid = extract_flipkart_pid(url)
            return "flipkart", pid
        elif "myntra.com" in url_lower:
            match = re.search(r'/(\d+)/buy', url)
            return "myntra", f"myntra_{match.group(1)}" if match else f"myntra_{str(hash(url))}"
        elif "meesho.com" in url_lower:
            match = re.search(r'/p/([a-zA-Z0-9]+)', url)
            return "meesho", f"meesho_{match.group(1)}" if match else f"meesho_{str(hash(url))}"
        elif "ajio.com" in url_lower:
            return "ajio", f"ajio_{str(hash(url))}"
        return None, None

    def _log_stage(self, db, correlation_id: str, stage: str, status: str, details: str):
        """Helper to write structured processing stage log entries into database."""
        try:
            from knowledge_base.models import ProcessingLog
            log_entry = ProcessingLog(
                correlation_id=correlation_id,
                stage=stage,
                status=status,
                details=details[:500],
                timestamp=time.time()
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logging.warning(f"[Mirror Processor] Failed to save DB log entry: {e}")
