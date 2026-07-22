# utils/scrapy_crawler.py
import scrapy
from scrapy.crawler import CrawlerProcess
import logging
import re
import time
import hashlib
from database.db_session import SessionLocal
from knowledge_base.models import SelectorMatrix, PriceHistory
from deal_engine.scorer import calculate_deal_score, should_publish_deal
from deal_engine.notifier import enqueue_alert
from database.operations import save_deal_to_db
from config.settings import load_settings
from utils.parser import calculate_true_discount, extract_rating_and_reviews, detect_bank_offers, extract_amazon_asin
from utils.affiliate import get_best_affiliate_url, generate_auto_cart_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ScrapyCrawler")

class LootSpider(scrapy.Spider):
    name = "loot_spider"
    
    def __init__(self, platform_configs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform_configs = platform_configs
        
    def start_requests(self):
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        
        for config in self.platform_configs:
            url = config["url"]
            yield scrapy.Request(
                url=url,
                headers={"User-Agent": user_agent},
                meta={"config": config},
                callback=self.parse
            )
            
    def parse(self, response):
        config = response.meta["config"]
        platform = config["platform"]
        settings = load_settings()
        
        # Check card selector
        card_sel = config["card_selector"]
        cards = response.css(card_sel)
        logger.info(f"[Scrapy Spider] Found {len(cards)} elements for platform: {platform}")
        
        for card in cards:
            try:
                # 1. Extract Target URL
                hrefs = card.css("a::attr(href)").getall()
                raw_url = None
                for href in hrefs:
                    if href and ("javascript" not in href) and ("/dp/" in href or "product" in href or "/gp/product/" in href or "/p/" in href):
                        if "/s?" not in href and "/b?" not in href and "node=" not in href:
                            raw_url = response.urljoin(href)
                            break
                            
                if not raw_url and hrefs:
                    raw_url = response.urljoin(hrefs[0])
                    
                if not raw_url:
                    continue
                    
                # Generate unique ID
                unique_id = None
                if "amazon" in platform.lower():
                    unique_id = extract_amazon_asin(raw_url)
                else:
                    clean_url = raw_url.split("?")[0]
                    unique_id = hashlib.md5(clean_url.encode("utf-8")).hexdigest()
                    
                if not unique_id:
                    continue
                    
                final_url = get_best_affiliate_url(raw_url, platform, settings)
                
                # 2. Extract Title
                title = ""
                title_sel = config.get("title_selector")
                if title_sel:
                    # check title attribute or text content
                    title = card.css(title_sel).attrib.get("title") or card.css(title_sel).attrib.get("alt")
                    if not title:
                        title = "".join(card.css(f"{title_sel} ::text").getall()).strip()
                        
                if not title or len(title) < 5:
                    continue
                    
                title = re.sub(r'\s+', ' ', title)
                
                # 3. Extract Image
                img_url = None
                img_sel = config.get("image_selector")
                if img_sel:
                    img_url = card.css(img_sel).attrib.get("src") or card.css(img_sel).attrib.get("data-src")
                    if img_url:
                        img_url = response.urljoin(img_url)
                        
                # 4. Extract Pricing
                card_text = " ".join(card.css("::text").getall())
                price, mrp, true_discount = calculate_true_discount(card_text)
                
                if not price or not mrp or not (30.0 <= true_discount <= 98.0):
                    continue
                    
                # 5. Check keyword blocklist
                blocklist = settings.get("blocklist_keywords", [])
                title_lower = title.lower()
                blocked_match = any(b_word.lower().strip() in title_lower for b_word in blocklist)
                if blocked_match:
                    continue
                    
                min_price = settings.get("min_deal_price", 299)
                min_savings = settings.get("min_deal_savings", 250)
                savings = mrp - price
                if price < min_price or savings < min_savings:
                    continue
                    
                # 6. Check if price changed
                price_changed = True
                is_price_drop = False
                db = SessionLocal()
                try:
                    latest = db.query(PriceHistory).filter_by(product_id=unique_id).order_by(PriceHistory.timestamp.desc()).first()
                    if latest:
                        price_changed = (latest.price != price)
                        is_price_drop = (price < latest.price)
                    else:
                        price_changed = True
                        is_price_drop = True
                except Exception:
                    pass
                finally:
                    db.close()
                    
                if not price_changed:
                    continue
                    
                is_verified_low = True
                rating, reviews = extract_rating_and_reviews(card_text)
                has_bank_offer = detect_bank_offers(card_text)
                
                # Calculate deal score
                deal_score = calculate_deal_score(
                    platform, price, mrp, true_discount, is_verified_low, False,
                    product_id=unique_id, title=title, rating=rating, reviews=reviews,
                    has_bank_offer=has_bank_offer
                )
                
                # 7. Persist and resolve semantic ID
                resolved_id = save_deal_to_db(
                    platform=platform,
                    title=title,
                    price=price,
                    mrp=mrp,
                    discount=true_discount,
                    img_url=img_url,
                    final_url=final_url,
                    is_verified_low=is_verified_low,
                    unique_id=unique_id,
                    deal_score=deal_score
                )
                
                # 8. Alert Dispatch
                if should_publish_deal(platform, deal_score) and is_price_drop:
                    auto_cart_url = None
                    try:
                        auto_cart_url = generate_auto_cart_url(final_url, platform, settings)
                    except Exception:
                        pass
                        
                    enqueue_alert(
                        platform=platform,
                        title=title,
                        price=price,
                        mrp=mrp,
                        discount=true_discount,
                        img_url=img_url,
                        final_url=final_url,
                        is_verified_low=is_verified_low,
                        deal_score=deal_score,
                        unique_id=resolved_id,
                        bank_offers=[],
                        coupon_detail="",
                        review_grade="N/A",
                        auto_cart_url=auto_cart_url
                    )
                    logger.info(f"🏆 [Scrapy] Alert dispatched for deal '{title[:35]}' (Resolved ID: {resolved_id})")
            except Exception as e:
                logger.error(f"[Scrapy Spider] Failed parsing card item: {e}")

def run_scrapy_crawler():
    db = SessionLocal()
    try:
        matrices = db.query(SelectorMatrix).all()
        configs = []
        for m in matrices:
            configs.append({
                "platform": m.platform,
                "url": m.url,
                "card_selector": m.card_selector,
                "title_selector": m.title_selector,
                "link_selector": m.link_selector,
                "image_selector": m.image_selector
            })
    except Exception as e:
        logger.error(f"Failed loading selectors matrix for Scrapy: {e}")
        return
    finally:
        db.close()
        
    if not configs:
        logger.warning("No selector matrices configured in database. Skipping Scrapy crawl.")
        return
        
    logger.info(f"Starting asynchronous Scrapy crawl on {len(configs)} feeds...")
    process = CrawlerProcess(settings={
        "LOG_LEVEL": "INFO",
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0.5,
        "COOKIES_ENABLED": False
    })
    process.crawl(LootSpider, platform_configs=configs)
    process.start()

if __name__ == "__main__":
    run_scrapy_crawler()
