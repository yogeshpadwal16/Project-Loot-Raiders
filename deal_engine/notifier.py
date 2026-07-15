import os
import queue
import threading
import time
import logging
import requests
import json
from datetime import datetime
from config.settings import load_settings, save_settings
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from utils.image_generator import generate_deal_image
from deal_engine.bot_listener import check_and_dispatch_personal_alerts

notification_queue = queue.Queue()

def send_discord_webhook(webhook_url: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, deal_score: float = 0.0) -> bool:
    try:
        is_amazon = "amazon" in final_url.lower()
        embed = {
            "title": title[:250],
            "url": final_url,
            "color": 16750848 if is_amazon else 114686,
            "fields": [
                {"name": "Price", "value": f"₹{price:,}", "inline": True},
                {"name": "MRP", "value": f"₹{mrp:,}", "inline": True},
                {"name": "Discount", "value": f"{discount:.1f}% OFF", "inline": True},
                {"name": "Deal Score", "value": f"{deal_score:.1f}/100", "inline": True}
            ],
            "footer": {
                "text": "Loot Raiders Deal Alert • Curated by Yogesh Padwal"
            }
        }
        if is_verified_low:
            embed["description"] = "🔥 **VERIFIED ALL-TIME LOW PRICE!**"
        if img_url and "base64" not in img_url:
            embed["image"] = {"url": img_url}
            
        payload = {
            "embeds": [embed]
        }
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.status_code in [200, 204]:
            logging.info("Discord Webhook background broadcast success.")
            return True
        else:
            logging.warning(f"Discord Webhook returned status {r.status_code}: {r.text}")
    except Exception as e:
        logging.error(f"Discord Webhook background broadcast failure: {e}")
    return False

def send_telegram_alert(bot_token: str, chat_id: str, platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, deal_score: float, unique_id: str) -> bool:
    is_amazon = "amazon" in platform.lower()
    is_glitch = discount >= 75.0
    
    # 1. Siren Alert mode formatting for Glitches vs Regular drops
    if is_glitch:
        platform_header = "🚨🚨 *[ DANGER: LOOT GLITCH ALERT ]* 🚨🚨\n🔥 *PRICE ERROR DETECTED* 🔥"
        validation_badge = "⚠️ *HURRY! Price will rise or sell out in seconds!*\n⚠️ *Forward to friends immediately!*\n"
    else:
        platform_header = "🍊 *[ AMAZON INDIA ]*" if is_amazon else "💣 *[ FLIPKART ]*"
        validation_badge = "🔥 *[ VERIFIED ALL-TIME LOW PRICE ]*\n" if is_verified_low else ""
        
    clean_title = title.split('\n')[0].strip()
    truncated_title = clean_title[:107] + "..." if len(clean_title) > 110 else clean_title
    
    caption = (
        f"{platform_header}\n"
        f"{validation_badge}\n"
        f"📌 *{truncated_title}*\n\n"
        f"```\n"
        f"💰 Deal Price: ₹{price:,}\n"
        f"❌ True MRP:   ₹{mrp:,}\n"
        f"📉 Discount:   {discount:.1f}% OFF\n"
        f"🔥 Deal Score: {deal_score:.1f}/100\n"
        f"```\n"
        f"⚡ *HURRY, PRICE DROP SEEN!*\n"
        f"👉 [GRAB THIS LAUNCH DEAL NOW]({final_url})\n\n"
        f"--- \n"
        f"🛒 Curated by: *Yogesh Padwal*"
    )
    
    # 2. Dynamic Price-Drop verification Card generation (Visual Proof)
    local_card_path = None
    try:
        local_card_path = generate_deal_image(
            unique_id=unique_id,
            platform=platform,
            title=title,
            price=price,
            mrp=mrp,
            discount=discount,
            original_image_url=img_url,
            is_verified_low=is_verified_low,
            deal_score=deal_score
        )
    except Exception as img_gen_err:
        logging.error(f"Image generation failed inside notifier: {img_gen_err}")

    # 3. Upload dynamic image card to Telegram
    if local_card_path and os.path.exists(local_card_path):
        try:
            endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(local_card_path, "rb") as f:
                files = {"photo": f}
                payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
                res = requests.post(endpoint, data=payload, files=files, timeout=25)
                
                # Cleanup local scratch file
                try: os.remove(local_card_path)
                except: pass
                
                if res.status_code == 200:
                    logging.info(f"Telegram verification card uploaded successfully -> {truncated_title[:20]}...")
                    return True
                else:
                    logging.warning(f"Telegram Photo method returned {res.status_code}: {res.text}")
        except Exception as upload_err:
            logging.error(f"Failed to upload photo card: {upload_err}")
            
    # Fallback to Text Alert if photo card failed
    try:
        text_endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload_fallback = {"chat_id": chat_id, "text": caption, "parse_mode": "Markdown"}
        res_fb = requests.post(text_endpoint, json=payload_fallback, timeout=15)
        if res_fb.status_code == 200:
            logging.info(f"Telegram Fallback Text Broadcast Success -> {truncated_title[:20]}...")
            return True
    except Exception as text_err:
        logging.error(f"Telegram Text Fallback Failed: {text_err}")
        
    return False

def send_daily_digest_if_time():
    """
    Checks if current time is past 9 PM (21:00) and aggregates the top 5 scored
    deals scanned today, sending them in a combined digest broadcast.
    """
    now = datetime.now()
    if now.hour < 21:
        return
        
    settings = load_settings()
    today_str = now.strftime("%Y-%m-%d")
    
    if settings.get("last_digest_date") == today_str:
        return # Already sent today
        
    bot_token = settings.get("telegram_bot_token")
    chat_id = settings.get("telegram_chat_id")
    if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "":
        return
        
    logging.info("Starting automated Daily Loot Digest aggregation.")
    db = SessionLocal()
    try:
        # Find start of today in float timestamp
        start_of_day = datetime(now.year, now.month, now.day).timestamp()
        
        # Query product deals scraped today
        products = db.query(Product).join(PriceHistory).filter(PriceHistory.timestamp >= start_of_day).all()
        
        deals_list = []
        for p in products:
            lp = db.query(PriceHistory).filter_by(product_id=p.id).order_by(PriceHistory.timestamp.desc()).first()
            if lp:
                deals_list.append((p, lp))
                
        if not deals_list:
            logging.info("No deals recorded today. Skipping digest.")
            return
            
        # Sort by deal score descending
        deals_list.sort(key=lambda x: x[1].deal_score, reverse=True)
        top_5 = deals_list[:5]
        
        digest_copy = (
            "🍊💣 *LOOT RAIDERS DAILY DIGEST* 💣🍊\n"
            f"📅 *Date:* {today_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Here are the top 5 highest-rated loot deals of the day:\n\n"
        )
        
        for idx, (p, lp) in enumerate(top_5, 1):
            is_amazon = "amazon" in p.platform.lower()
            badge = "🍊" if is_amazon else "💣"
            clean_title = p.title.split('\n')[0].strip()
            truncated_title = clean_title[:45] + "..." if len(clean_title) > 48 else clean_title
            
            digest_copy += (
                f"*{idx}️⃣ {badge} {truncated_title}*\n"
                f"💰 *Deal Price:* ₹{lp.price:,} (MRP: ₹{lp.mrp:,})\n"
                f"📉 *Discount:* {lp.discount:.0f}% OFF  🔥 *Score:* {lp.deal_score:.0f}/100\n"
                f"👉 [GRAB THIS LOOT DEAL]({p.url})\n\n"
            )
            
        digest_copy += (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ *Don't miss a single price drop! Join @LootRaidersDeals!*"
        )
        
        # Send digest
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": digest_copy, "parse_mode": "Markdown"}
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            logging.info("Daily Loot Digest broadcast sent successfully!")
            settings["last_digest_date"] = today_str
            save_settings(settings)
            
    except Exception as e:
        logging.error(f"Failed to generate daily digest: {e}")
    finally:
        db.close()

def notifier_worker():
    logging.info("Background Alert Dispatch Worker Activated.")
    while True:
        # Check and send Daily digests
        send_daily_digest_if_time()
        
        try:
            job = notification_queue.get(timeout=5)
        except queue.Empty:
            continue
            
        if job is None:
            break
            
        platform = job.get("platform")
        title = job.get("title")
        price = job.get("price")
        mrp = job.get("mrp")
        discount = job.get("discount")
        img_url = job.get("image_url")
        final_url = job.get("url")
        is_verified_low = job.get("is_verified_low")
        deal_score = job.get("deal_score")
        unique_id = job.get("unique_id")
        retries = job.get("retries", 0)
        
        settings = load_settings()
        bot_token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")
        discord_webhook = settings.get("discord_webhook_url")
        
        has_telegram = (bot_token and chat_id and "YOUR_TELEGRAM" not in bot_token and bot_token.strip() != "")
        has_discord = (discord_webhook and discord_webhook.strip() != "")
        
        telegram_ok = True
        discord_ok = True
        
        # A. Dispatch personal direct message alerts first
        try:
            check_and_dispatch_personal_alerts(unique_id, platform, title, price, mrp, discount, img_url, final_url)
        except Exception as alerts_err:
            logging.error(f"Personal alerts dispatcher failed: {alerts_err}")
        
        # B. Dispatch channel updates
        if has_telegram:
            telegram_ok = send_telegram_alert(
                bot_token=bot_token,
                chat_id=chat_id,
                platform=platform,
                title=title,
                price=price,
                mrp=mrp,
                discount=discount,
                img_url=img_url,
                final_url=final_url,
                is_verified_low=is_verified_low,
                deal_score=deal_score,
                unique_id=unique_id
            )
            
        if has_discord:
            discord_ok = send_discord_webhook(discord_webhook, title, price, mrp, discount, img_url, final_url, is_verified_low, deal_score)
            
        # Retry with exponential backoff on failure
        if (has_telegram and not telegram_ok) or (has_discord and not discord_ok):
            if retries < 3:
                job["retries"] = retries + 1
                backoff = (2 ** retries) * 5
                logging.warning(f"Notification broadcast failed. Retrying job in {backoff} seconds...")
                threading.Timer(backoff, lambda: notification_queue.put(job)).start()
            else:
                logging.error(f"Failed to broadcast notification after 3 attempts: {title[:30]}...")
                
        notification_queue.task_done()

def enqueue_alert(platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, deal_score: float, unique_id: str):
    job = {
        "platform": platform,
        "title": title,
        "price": price,
        "mrp": mrp,
        "discount": discount,
        "image_url": img_url,
        "url": final_url,
        "is_verified_low": is_verified_low,
        "deal_score": deal_score,
        "unique_id": unique_id,
        "retries": 0
    }
    notification_queue.put(job)

def start_notifier():
    t = threading.Thread(target=notifier_worker, daemon=True)
    t.start()
