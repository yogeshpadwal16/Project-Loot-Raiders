import time
import logging
import threading
import uuid
import re
import requests
from typing import List, Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from deal_engine.mirroring.mirror_config import WORKER_COUNT, SIMILARITY_THRESHOLD
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.redis_queue import RedisMessageQueue
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
        
        # Apply tgcf-inspired plugins (filter, replace, ocr, format)
        from deal_engine.mirroring.plugins import apply_plugins
        message = apply_plugins(message)
        if not message:
            logging.info(f"[Mirror Engine] [CorrID: {correlation_id}] Message was filtered out by plugins.")
            return

        # Re-extract URLs from the modified message text to ensure we only scrape what remains
        from deal_engine.mirroring.normalizer import extract_urls_from_text
        combined_text = f"{message.raw_text or ''}\n{message.caption or ''}"
        message.extracted_urls = extract_urls_from_text(combined_text)
        for btn in message.buttons:
            if btn.url and btn.url not in message.extracted_urls:
                message.extracted_urls.append(btn.url)

        from config.settings import load_settings
        settings = load_settings()
        
        # 1. Verify links exist in message
        if not message.extracted_urls:
            logging.info(f"[PARSE] [CorrID: {correlation_id}] No URLs in message {message.message_id}. Skipping.")
            return

        db = SessionLocal()
        try:
            for raw_url in message.extracted_urls:
                # Skip known bad paths
                from deal_engine.channel_mirror import _should_skip_url
                if _should_skip_url(raw_url):
                    logging.info(f"[PARSE] [CorrID: {correlation_id}] Skipping non-deal link: {raw_url}")
                    continue
                
                # 2. Expand link
                expanded_url = self._expand_url_with_retry(raw_url, correlation_id)
                
                # Resolve competitor landing pages
                platform, unique_id = self._parse_url_metadata(expanded_url)
                if not platform or not unique_id:
                    # Attempt landing page parsing for non-direct links (e.g. linktree, link shorteners)
                    logging.info(f"[PARSE] [CorrID: {correlation_id}] Non-store URL: {expanded_url}. Scanning landing page...")
                    candidates = extract_store_url_from_competitor_landing_page(expanded_url)
                    if candidates:
                        expanded_url = candidates
                        platform, unique_id = self._parse_url_metadata(expanded_url)
                
                if not platform or not unique_id:
                    logging.warning(f"[PARSE] [CorrID: {correlation_id}] Could not resolve store identifier for: {expanded_url}")
                    continue
                    
                # 4. Scrape details
                # Priority A: Parse from Telegram message text (message.raw_text)
                # Priority B: Fallback to lightweight HTTP scrape (BeautifulSoup — no browser)
                title, price, mrp, img_url = "", 0, 0, message.media_file_id if (message.media_file_id and message.media_file_id.startswith("http")) else ""
                
                if message.raw_text and message.raw_text.strip():
                    import re
                    def extract_deal_number(pattern: str, text: str) -> int:
                        m = re.search(pattern, text.replace(',', ''), flags=re.IGNORECASE)
                        if m:
                            try:
                                return int(m.group(1))
                            except (ValueError, IndexError):
                                pass
                        return 0
                    
                    price_patterns = [
                        r'(?:price|deal\s+price|deal|now|at\s+just|at|for)\s*:?\s*(?:rs\.?|₹)\s*(\d+)',
                        r'(?:rs\.?|₹)\s*(\d+)\s*(?:/|-)\s*(?:rs\.?|₹)?\s*\d+',
                        r'(?:rs\.?|₹)\s*(\d[\d,]{1,6})',
                    ]
                    mrp_patterns = [
                        r'(?:mrp|original\s+price|was|m\.?r\.?p\.?)\s*:?\s*(?:rs\.?|₹)?\s*(\d+)',
                        r'(?:rs\.?|₹)\s*\d+\s*(?:/|-)\s*(?:rs\.?|₹)?\s*(\d+)',
                        r'(?:slash(?:ed)?|cut|was|original)\s+(?:rs\.?|₹)?\s*(\d+)',
                    ]
                    
                    msg_clean = message.raw_text.replace(',', '')
                    for pat in price_patterns:
                        extracted = extract_deal_number(pat, msg_clean)
                        if extracted > 0:
                            price = extracted
                            break
                            
                    for pat in mrp_patterns:
                        extracted = extract_deal_number(pat, msg_clean)
                        if extracted > 0 and extracted != price:
                            mrp = extracted
                            break
                            
                    if price > 0 and mrp == 0:
                        all_prices = [int(n) for n in re.findall(r'(?:rs\.?|₹)\s*(\d+)', msg_clean, flags=re.IGNORECASE)]
                        larger = [p for p in all_prices if p > price]
                        if larger:
                            mrp = min(larger)
                        else:
                            mrp = int(price * 1.4)
                            
                    if price > 0:
                        logging.info(f"[PARSE] [CorrID: {correlation_id}] Extracted from message text: Price=Rs.{price} MRP=Rs.{mrp}")
                        lines = [l.strip() for l in message.raw_text.split('\n') if l.strip()]
                        for line in lines:
                            if (len(line) >= 10 and 'http' not in line and
                                    not line.startswith('#') and
                                    not re.match(r'^[\d₹%\-\s,.:Rs]+$', line, flags=re.IGNORECASE)):
                                title = line[:120]
                                break
                        if not title:
                            title = "Competitor Deal"
                
                # Fallback to lightweight scraper if needed
                scraped = {}
                if price == 0:
                    logging.info(f"[PARSE] [CorrID: {correlation_id}] No price from message text — attempting lightweight HTTP scrape")
                    from deal_engine.deal_processor import scrape_product_lightweight
                    scraped_data = scrape_product_lightweight(expanded_url)
                    if scraped_data:
                        scraped = scraped_data
                        if not title or title == "Competitor Deal":
                            title = scraped_data.get("title", "Product Deal")
                        price = scraped_data.get("price", 0)
                        mrp = scraped_data.get("mrp", 0)
                        img_url = scraped_data.get("image_url", "")
                
                # Unrestricted Deal Mirroring: Format and post anyway if price extraction fails
                if price == 0:
                    logging.info(f"[PARSE] [CorrID: {correlation_id}] Could not extract price. Formatting anyway using original competitor text.")
                    price = 0
                    mrp = 0
                    discount = 0.0
                    if not title or title == "Competitor Deal":
                        title = message.raw_text[:120] if message.raw_text else "Competitor Deal"
                else:
                    discount = 0.0
                    if mrp > price:
                        discount = ((mrp - price) / mrp) * 100.0
                    
                rating = scraped.get("rating")
                reviews = scraped.get("reviews")
                has_bank_offer = scraped.get("has_bank_offer", False)
                
                # Bypassed: Smart Filter and keyword blacklists are disabled for unrestricted mirroring
                
                # 5. STRICT "SINGLE PRODUCT DEDUPLICATION" ONLY
                product_already_posted = False
                if platform and unique_id:
                    prod = db.query(Product).filter_by(id=unique_id).first()
                    if prod:
                        product_already_posted = True
                        
                if not product_already_posted and expanded_url:
                    from utils.deduplicator import get_canonical_url
                    canon_url = get_canonical_url(expanded_url)
                    if canon_url:
                        prod = db.query(Product).filter(Product.url.like(f"%{canon_url}%")).first()
                        if prod:
                            product_already_posted = True
                
                if product_already_posted:
                    logging.info(f"[DEDUP] [CorrID: {correlation_id}] Skipping duplicate: Product '{title[:30]}' ({unique_id}) was already posted to channel.")
                    continue
                
                # 6. Check price trends
                is_verified_low = True
                try:
                    settings = load_settings()
                    if settings.get("external_price_tracker_enabled", False):
                        from utils.playwright_adapter import get_playwright_driver
                        temp_driver = get_playwright_driver(settings)
                        try:
                            is_verified_low = verify_historical_low(temp_driver, expanded_url, price, unique_id, discount)
                        finally:
                            temp_driver.quit()
                    else:
                        is_verified_low = verify_historical_low(None, expanded_url, price, unique_id, discount)
                except Exception as verify_err:
                    logging.warning(f"[PARSE] [CorrID: {correlation_id}] Historical check failed, defaulting to True: {verify_err}")
                    
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
                    auto_cart_url=auto_cart_url,
                    is_mirror=True
                )
                logging.info(f"[QUEUE] [CorrID: {correlation_id}] Deal alerts enqueued for publishing: {title[:30]}")
        finally:
            db.close()

    def _expand_url_with_retry(self, url: str, correlation_id: str = "") -> str:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
        expanded = url
        try:
            import httpx
            with httpx.Client(headers=headers, follow_redirects=True, timeout=5.0) as client:
                res = client.head(url)
                if res.status_code >= 400 or str(res.url) == url:
                    res = client.get(url)
                expanded = str(res.url)
        except Exception as e:
            logging.warning(f"[PARSE] [CorrID: {correlation_id}] Short link expansion failed for {url}: {e}")

            
        # If it's still a non-store URL, use Playwright to resolve JS redirects
        store_domains = ["amazon.in", "flipkart.com", "myntra.com", "ajio.com", "meesho.com", "tatacliq.com", "jiomart.com"]
        if not any(d in expanded.lower() for d in store_domains):
            try:
                from utils.playwright_adapter import get_playwright_driver
                settings = load_settings()
                temp_driver = get_playwright_driver(settings)
                try:
                    temp_driver.get(expanded)
                    time.sleep(5)  # Wait for JS redirects to settle
                    final_url = temp_driver.page.url
                    if any(d in final_url.lower() for d in store_domains):
                        logging.info(f"[PARSE] [CorrID: {correlation_id}] Playwright resolved JS redirect: {url} -> {final_url}")
                        expanded = final_url
                finally:
                    temp_driver.quit()
            except Exception as e:
                logging.warning(f"[PARSE] [CorrID: {correlation_id}] Playwright redirect resolution failed: {e}")
                
        return expanded

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
        elif "jiomart.com" in url_lower:
            prod_id = None
            if "/p/" in url:
                try:
                    p_path = url.split("/p/")[-1].split("?")[0].rstrip("/")
                    parts = [p for p in p_path.split("/") if p]
                    if parts:
                        prod_id = parts[-1]
                except Exception:
                    pass
            if not prod_id:
                prod_id = str(abs(hash(url)))
            return "jiomart", f"jiomart_{prod_id}"
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
