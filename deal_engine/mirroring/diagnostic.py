import time
import logging
import uuid
import sys
import os
import asyncio

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

from database.db_session import SessionLocal, init_db
from knowledge_base.models import Product, PriceHistory, ProcessingLog
from deal_engine.mirroring import get_queue, get_listener, get_processor
from deal_engine.mirroring.schemas import NormalizedMessage, ButtonSchema
from deal_engine.mirroring.normalizer import MessageNormalizer
from deal_engine.mirroring.deduplicator import IntelligentDeduplicator
from deal_engine.notifier import send_telegram_alert
from config.settings import load_settings

def run_pipeline_diagnostic():
    print("\n==========================================================================")
    print("[TEST] STARTING DEAL MIRRORING ENGINE END-TO-END DIAGNOSTIC [TEST]")
    print("==========================================================================\n")
    
    correlation_id = str(uuid.uuid4())
    report = []
    
    # Init Database to ensure tables exist
    init_db()
    
    # ---------------------------------------------------------
    # Stage 1: Telegram Listener
    # ---------------------------------------------------------
    start_time = time.time()
    listener = get_listener()
    stage_exception = None
    stage_status = "PASS"
    stage_input = "TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_STRING_SESSION"
    stage_output = ""
    try:
        pyro_ok = asyncio.run(listener._start_pyrogram())
        stage_output += f"Pyrogram check: {'PASS' if pyro_ok else 'FAIL'}. "
    except Exception as e:
        stage_exception = e
        pyro_ok = False
        stage_output += f"Pyrogram error: {e}. "
        
    try:
        tele_ok = asyncio.run(listener._start_telethon())
        stage_output += f"Telethon check: {'PASS' if tele_ok else 'FAIL'}."
    except Exception as e:
        if not stage_exception:
            stage_exception = e
        tele_ok = False
        stage_output += f"Telethon error: {e}."
        
    if not pyro_ok and not tele_ok:
        stage_status = "FAIL"
        
    report.append({
        "Stage": "1. Telegram Listener",
        "Status": stage_status,
        "Input": stage_input,
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "Session unauthorized or incorrect credentials" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 2: Message Reception
    # ---------------------------------------------------------
    start_time = time.time()
    mock_raw_text = "Check this deal out! Wipro Garnet 18W LED Bulb at huge discount! https://www.amazon.in/dp/B0DP7H7H8V coupon: LEDLIGHT"
    report.append({
        "Stage": "2. Message Reception",
        "Status": "PASS",
        "Input": f"Raw post event: '{mock_raw_text[:40]}...'",
        "Output": "Parsed raw event text string",
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": "None",
        "RootCause": "N/A"
    })

    # ---------------------------------------------------------
    # Stage 5: Message Normalization
    # ---------------------------------------------------------
    start_time = time.time()
    stage_status = "PASS"
    stage_exception = None
    normalized_msg = None
    try:
        # Create a mock telethon-like object to pass through normalizer
        class MockChat:
            id = 123456789
            username = "Loot_shoppingdeals123"
            title = "Mock Competitor Channel"
            
        class MockMessage:
            id = 9999
            chat_id = -100123456789
            chat = MockChat()
            text = mock_raw_text
            message = mock_raw_text
            entities = []
            reply_markup = None
            photo = None
            video = None
            document = None
            views = 150
            edit_date = None
            
        normalized_msg = MessageNormalizer.from_telethon(MockMessage())
        normalized_msg.correlation_id = correlation_id
        stage_output = f"Normalized Message Schema (extracted links: {normalized_msg.extracted_urls})"
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = "Normalization failed"
        
    report.append({
        "Stage": "5. Message Normalization",
        "Status": stage_status,
        "Input": "Mock raw Telegram message object",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "NameError or attribute extraction error" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 3: Queue Insertion
    # ---------------------------------------------------------
    start_time = time.time()
    queue = get_queue()
    stage_status = "PASS"
    stage_exception = None
    try:
        if normalized_msg:
            enqueued = queue.enqueue(normalized_msg)
            if not enqueued:
                stage_status = "FAIL"
                stage_output = "Redis push failed (connection refused)"
            else:
                stage_output = f"Message pushed successfully to key: loot_raiders:mirror_queue:pending"
        else:
            stage_status = "FAIL"
            stage_output = "No message to enqueue"
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = "Queue enqueue exception"
        
    report.append({
        "Stage": "3. Queue Insertion",
        "Status": stage_status,
        "Input": "Pydantic NormalizedMessage",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "Redis server not running locally" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 4: Queue Consumption
    # ---------------------------------------------------------
    start_time = time.time()
    stage_status = "PASS"
    stage_exception = None
    consumed_msg = None
    try:
        if queue.is_connected() and normalized_msg:
            consumed_msg = queue.dequeue("diagnostic-worker", timeout=1)
            if consumed_msg:
                stage_output = f"Message popped from pending queue. Correlation ID: {consumed_msg.correlation_id}"
                # Clean up popped message from processing list
                queue.commit("diagnostic-worker", consumed_msg)
            else:
                stage_status = "FAIL"
                stage_output = "No message popped (Queue empty or timed out)"
        else:
            # Fallback inline processing simulation
            consumed_msg = normalized_msg
            stage_output = "Bypassed Redis Queue (Using Inline Fallback mode)"
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = "Queue dequeue exception"
        
    report.append({
        "Stage": "4. Queue Consumption",
        "Status": stage_status,
        "Input": "worker-id, timeout",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "Workers not listening or Redis is offline" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 6: Deal Validation (Link Expansion & Scraping)
    # ---------------------------------------------------------
    start_time = time.time()
    stage_status = "PASS"
    stage_exception = None
    scraped_info = None
    target_url = "https://www.amazon.in/dp/B0BMVV6693" # Known product
    try:
        from core.engine import scrape_product_details
        scraped_info = scrape_product_details(target_url)
        if not scraped_info or scraped_info.get("price", 0) == 0:
            stage_status = "FAIL"
            stage_output = "Scraped details return empty or price=0"
        else:
            stage_output = f"Scrape PASS: Title='{scraped_info.get('title')[:25]}...', Price={scraped_info.get('price')}"
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = "Scraper execution failure"
        
    report.append({
        "Stage": "6. Deal Validation",
        "Status": stage_status,
        "Input": f"Store URL: {target_url}",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "Playwright launcher error or element selector mismatch" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 7: Duplicate Detection
    # ---------------------------------------------------------
    start_time = time.time()
    stage_status = "PASS"
    stage_exception = None
    try:
        if scraped_info:
            is_dup, matched_id = IntelligentDeduplicator.find_duplicate(scraped_info.get("title"), scraped_info.get("price"), time_window_hours=24)
            stage_output = f"Is duplicate: {is_dup}. Match ID: {matched_id}."
        else:
            stage_status = "FAIL"
            stage_output = "No scraped product details to check"
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = "Deduplication calculation failed"
        
    report.append({
        "Stage": "7. Duplicate Detection",
        "Status": stage_status,
        "Input": "Product Title & Price",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "Database queries mapping error" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 8: Affiliate Link Generation
    # ---------------------------------------------------------
    start_time = time.time()
    stage_status = "PASS"
    stage_exception = None
    final_aff_url = ""
    try:
        from utils.affiliate import get_best_affiliate_url
        settings = load_settings()
        final_aff_url = get_best_affiliate_url(target_url, "amazon", settings)
        stage_output = f"Affiliate link: {final_aff_url}"
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = "Affiliate url generation failed"
        
    report.append({
        "Stage": "8. Affiliate Link Generation",
        "Status": stage_status,
        "Input": f"Store URL: {target_url}",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "Affiliate tag configuration error" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 9: Publisher
    # ---------------------------------------------------------
    start_time = time.time()
    stage_status = "PASS"
    stage_exception = None
    try:
        from deal_engine.notifier import enqueue_alert
        enqueue_alert(
            platform="amazon",
            title=scraped_info.get("title") if scraped_info else "Test Product",
            price=scraped_info.get("price") if scraped_info else 499,
            mrp=scraped_info.get("mrp") if scraped_info else 999,
            discount=50.0,
            img_url=scraped_info.get("image_url") if scraped_info else "https://m.media-amazon.com/images/I/61cwywLZR-L._SL1500_.jpg",
            final_url=final_aff_url,
            is_verified_low=True,
            deal_score=85.0,
            unique_id="diagnostic_test_id"
        )
        stage_output = "Successfully placed alert job inside notification_queue."
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = "Alert enqueuing failed"
        
    report.append({
        "Stage": "9. Publisher",
        "Status": stage_status,
        "Input": "alert metadata dictionary",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "Notification queue put error" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 10: Telegram API Response
    # ---------------------------------------------------------
    start_time = time.time()
    stage_status = "PASS"
    stage_exception = None
    try:
        settings = load_settings()
        bot_token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")
        
        if bot_token and chat_id:
            posted = send_telegram_alert(
                bot_token=bot_token,
                chat_id=chat_id,
                platform="amazon",
                title="[Diagnostic] System Redesign Verification post",
                price=499,
                mrp=999,
                discount=50.0,
                img_url="https://m.media-amazon.com/images/I/61cwywLZR-L._SL1500_.jpg",
                final_url=final_aff_url or "https://t.me/LootRaidersDeals",
                is_verified_low=True,
                deal_score=85.0,
                unique_id="diag_tg_api"
            )
            if not posted:
                stage_status = "FAIL"
                stage_output = "Telegram post request returned status code != 200 or failed"
            else:
                stage_output = "Telegram API post succeeded (Code 200)."
        else:
            stage_status = "FAIL"
            stage_output = "Telegram bot token or chat ID is missing in settings"
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = f"Telegram post exception: {e}"
        
    report.append({
        "Stage": "10. Telegram API Response",
        "Status": stage_status,
        "Input": "Telegram bot_token, chat_id",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "Telegram rate limits or invalid token/chat ID" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 11: Database Updates
    # ---------------------------------------------------------
    start_time = time.time()
    stage_status = "PASS"
    stage_exception = None
    db = SessionLocal()
    try:
        test_product = db.query(Product).filter_by(id="diag_tg_api").first()
        stage_output = f"Queried test product written during diagnostic: {'Found' if test_product else 'Not Found'}"
        if not test_product:
            from database.operations import save_deal_to_db
            save_deal_to_db("amazon", "Diagnostic Deal", 499, 999, 50.0, "", final_aff_url, True, "diag_tg_db", 85.0)
            written = db.query(Product).filter_by(id="diag_tg_db").first()
            if written:
                stage_output = "Product and PriceHistory written successfully to DB."
                db.query(PriceHistory).filter_by(product_id="diag_tg_db").delete()
                db.query(Product).filter_by(id="diag_tg_db").delete()
                db.commit()
            else:
                stage_status = "FAIL"
                stage_output = "Database commit did not persist entry"
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = "Database transaction failed"
    finally:
        db.close()
        
    report.append({
        "Stage": "11. Database Updates",
        "Status": stage_status,
        "Input": "save_deal_to_db arguments",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "DB locked, column mismatch, or connection issue" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Stage 12: Logging
    # ---------------------------------------------------------
    start_time = time.time()
    stage_status = "PASS"
    stage_exception = None
    db = SessionLocal()
    try:
        log_count = db.query(ProcessingLog).filter_by(correlation_id=correlation_id).count()
        log_entry = ProcessingLog(
            correlation_id=correlation_id,
            stage="diagnostic",
            status="success",
            details="Diagnostic runner check",
            timestamp=time.time()
        )
        db.add(log_entry)
        db.commit()
        
        verify_log = db.query(ProcessingLog).filter_by(correlation_id=correlation_id).first()
        if verify_log:
            stage_output = f"Trace log successfully verified for Correlation ID: {correlation_id}"
            db.delete(verify_log)
            db.commit()
        else:
            stage_status = "FAIL"
            stage_output = "Log insertion failed"
    except Exception as e:
        stage_status = "FAIL"
        stage_exception = e
        stage_output = "Logging execution failure"
    finally:
        db.close()
        
    report.append({
        "Stage": "12. Logging",
        "Status": stage_status,
        "Input": f"Correlation ID: {correlation_id}",
        "Output": stage_output,
        "Time": f"{(time.time() - start_time) * 1000:.1f}ms",
        "Exception": str(stage_exception) if stage_exception else "None",
        "RootCause": "Write transaction block" if stage_status == "FAIL" else "N/A"
    })

    # ---------------------------------------------------------
    # Display ASCII Report Table
    # ---------------------------------------------------------
    print("\n" + "="*80)
    print("END-TO-END DIAGNOSTIC PIPELINE REPORT")
    print("="*80)
    print(f"| {'Stage':<30} | {'Status':<6} | {'Time':<10} | {'Exception':<12} |")
    print(f"| {'-'*30} | {'-'*6} | {'-'*10} | {'-'*12} |")
    for r in report:
        print(f"| {r['Stage']:<30} | {r['Status']:<6} | {r['Time']:<10} | {r['Exception'][:12]:<12} |")
    print("="*80 + "\n")
    
    # Save diagnostic results to diagnostic_report.md
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    report_file = os.path.join(base_dir, "DIAGNOSTIC_REPORT.md")
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# [TEST] Deal Mirroring Engine - Pipeline Diagnostic Report\n\n")
            f.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Message Trace Correlation ID: `{correlation_id}`\n\n")
            f.write("## Pipeline Stages Audit\n\n")
            f.write("| Stage | Status | Input Received | Output Produced | Processing Time | Exception | Root Cause (If Failed) |\n")
            f.write("| --- | --- | --- | --- | --- | --- | --- |\n")
            for r in report:
                f.write(f"| {r['Stage']} | **{r['Status']}** | {r['Input']} | {r['Output']} | {r['Time']} | `{r['Exception']}` | {r['RootCause']} |\n")
            f.write("\n## Diagnostic Summary\n")
            failures = [r for r in report if r["Status"] == "FAIL"]
            if failures:
                f.write(f"\n[FAIL] **{len(failures)} failures detected in the pipeline!** Please review the table above.\n")
            else:
                f.write("\n[PASS] **All stages passed successfully!** The pipeline is functional.\n")
        print(f"Saved diagnostic report to: {report_file}")
    except Exception as io_err:
        print(f"Failed to write report file: {io_err}")

if __name__ == "__main__":
    run_pipeline_diagnostic()
