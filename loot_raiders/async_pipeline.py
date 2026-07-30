import asyncio
import logging
import time

logger = logging.getLogger("loot_raiders.pipeline")


class DealIngestionPipeline:
    """
    Non-blocking asyncio queue-based pipeline for deal ingestion.
    Coordinates URL cleanup, OpenGraph scraping, price evaluation, A/B captioning,
    sparkline generation, voice alert creation, and Telegram syndication.
    """
    def __init__(self, bot_token=None, chat_id=None, concurrency_limit=2):
        self.queue = asyncio.Queue()
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.concurrency_limit = concurrency_limit
        self.workers = []
        self.is_running = False

    async def enqueue_deal(self, raw_deal: dict):
        """Pushes a newly scraped or mirrored deal into the pipeline queue."""
        await self.queue.put(raw_deal)
        logger.info(f"[Pipeline] Enqueued raw deal for processing: {raw_deal.get('title', '')[:35]}")

    async def _worker_loop(self):
        """Processes deals sequentially from the asyncio queue."""
        while self.is_running:
            deal = await self.queue.get()
            try:
                logger.info(f"[Pipeline] Worker picked up deal: {deal.get('title', '')[:35]}")
                await self._process_deal(deal)
            except Exception as e:
                logger.error(f"[Pipeline] Worker failed to process deal: {e}")
            finally:
                self.queue.task_done()

    async def _process_deal(self, deal: dict):
        """Processes and broadcasts a single deal."""
        # 1. Affiliate Link Expansion and Cleaning
        from affiliate_cleaner import clean_and_tag_url
        clean_url, platform = clean_and_tag_url(deal.get("url", ""))
        deal["url"] = clean_url
        deal["platform"] = platform

        # 2. Extract ASIN/PID as unique_id
        unique_id = deal.get("unique_id")
        if not unique_id:
            if "amazon" in platform.lower():
                from affiliate_cleaner import extract_asin
                unique_id = extract_asin(clean_url)
            if not unique_id:
                unique_id = str(int(time.time()))
            deal["unique_id"] = unique_id

        # 3. Media Scraping Fallback
        if not deal.get("image_url") or "base64" in deal.get("image_url", ""):
            from media_scraper import fetch_opengraph_image
            deal["image_url"] = fetch_opengraph_image(clean_url)

        # 4. Bank Discount Calculation
        from bank_offers import get_best_bank_effective_price
        price = deal.get("price", 0)
        bank_offers = deal.get("bank_offers", [])
        eff_price, bank_summary = get_best_bank_effective_price(price, bank_offers)
        deal["effective_price"] = eff_price
        deal["bank_summary"] = bank_summary

        # 5. DB Save & History Check
        from database import SessionLocal, Product, PriceHistory
        db = SessionLocal()
        is_verified_low = False
        try:
            prod = db.query(Product).filter_by(id=unique_id).first()
            if not prod:
                prod = Product(
                    id=unique_id,
                    platform=platform,
                    title=deal.get("title", ""),
                    image_url=deal.get("image_url"),
                    url=clean_url
                )
                db.add(prod)
            
            # Fetch past prices
            history = db.query(PriceHistory).filter_by(product_id=unique_id).order_by(PriceHistory.price.asc()).first()
            if not history or price < history.price:
                is_verified_low = True
            
            hist_entry = PriceHistory(
                product_id=unique_id,
                price=price,
                mrp=deal.get("mrp", price),
                discount=deal.get("discount", 0.0),
                is_verified_low=is_verified_low,
                deal_score=deal.get("deal_score", 50.0)
            )
            db.add(hist_entry)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[Pipeline] DB insertion failed: {e}")
        finally:
            db.close()

        deal["is_verified_low"] = is_verified_low

        # 6. Check Personal Wishlist Keyword DMs
        from wishlist_bot import check_deal_against_keyword_alerts
        check_deal_against_keyword_alerts(self.bot_token, deal)

        # 7. Channel Routing
        from channel_router import resolve_target_channel_id
        target_chat = resolve_target_channel_id(deal.get("title", ""), self.chat_id)

        # 8. A/B Smart Caption Building
        from template_engine import build_html_caption, build_inline_buttons
        from ab_testing import select_ab_template
        ab_variant, tracking_tag = select_ab_template(unique_id)
        
        caption = build_html_caption(deal, ab_variant, tracking_tag)

        # 9. Voice Alert Generation (for massive drops/glitches)
        if deal.get("discount", 0.0) >= 70.0:
            try:
                from voice_alerts import generate_voice_alert
                voice_path = await generate_voice_alert(deal.get("title", ""), price)
                deal["voice_path"] = voice_path
            except Exception as e:
                logger.warning(f"Voice alert generation skipped: {e}")

        # 10. Sparkline Thumbnail Overlay
        from sparkline_generator import generate_sparkline_thumbnail
        thumbnail_path = generate_sparkline_thumbnail(unique_id, deal.get("image_url"), price, deal.get("mrp", price))
        if thumbnail_path:
            deal["card_image_path"] = thumbnail_path

        # 11. Broadcast to Target Channel
        # Simulates Telegram broadcast by logging the message payload
        logger.info(
            f"\n=== BROADCASTING DEAL TO {target_chat} ===\n"
            f"Image: {deal.get('card_image_path') or deal.get('image_url')}\n"
            f"Caption:\n{caption}\n"
            f"Buttons: {build_inline_buttons(deal)}\n"
            f"=========================================="
        )

    def start(self):
        """Launches background workers for pipeline queue processing."""
        if self.is_running:
            return
        self.is_running = True
        for _ in range(self.concurrency_limit):
            self.workers.append(asyncio.create_task(self._worker_loop()))
        logger.info("[Pipeline] Async deal pipeline workers launched.")

    async def stop(self):
        """Stops background workers and waits for queue completion."""
        self.is_running = False
        await self.queue.join()
        for worker in self.workers:
            worker.cancel()
        self.workers.clear()
        logger.info("[Pipeline] Async deal pipeline workers stopped.")
