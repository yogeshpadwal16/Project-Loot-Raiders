import queue
import threading
import time
import logging
import requests
import json
from config.settings import load_settings

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

def send_telegram_alert(bot_token: str, chat_id: str, platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, deal_score: float) -> bool:
    is_amazon = "amazon" in platform.lower()
    platform_header = "🍊 [ AMAZON INDIA ]" if is_amazon else "💣 [ FLIPKART ]"
    
    clean_title = title.split('\n')[0].strip()
    truncated_title = clean_title[:107] + "..." if len(clean_title) > 110 else clean_title
    
    validation_badge = "🔥 [ VERIFIED ALL-TIME LOW PRICE ]\n" if is_verified_low else ""
    
    caption = (
        f"{platform_header}\n"
        f"{validation_badge}"
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
    
    # Try sending with Photo
    if img_url and "base64" not in img_url:
        try:
            endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            payload = {"chat_id": chat_id, "photo": img_url, "caption": caption, "parse_mode": "Markdown"}
            res = requests.post(endpoint, json=payload, timeout=15)
            if res.status_code == 200:
                logging.info(f"Telegram Background Photo Broadcast Success -> {truncated_title[:20]}...")
                return True
        except Exception as e:
            logging.error(f"Telegram Photo Method Failed in background: {e}")
            
    # Try sending with Text fallback
    try:
        text_endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload_fallback = {"chat_id": chat_id, "text": caption, "parse_mode": "Markdown"}
        res_fb = requests.post(text_endpoint, json=payload_fallback, timeout=15)
        if res_fb.status_code == 200:
            logging.info(f"Telegram Background Text Broadcast Success -> {truncated_title[:20]}...")
            return True
    except Exception as e:
        logging.error(f"Telegram Text Method Failed in background: {e}")
        
    return False

def notifier_worker():
    logging.info("Background Alert Dispatch Worker Activated.")
    while True:
        job = notification_queue.get()
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
        retries = job.get("retries", 0)
        
        settings = load_settings()
        bot_token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")
        discord_webhook = settings.get("discord_webhook_url")
        
        has_telegram = (bot_token and chat_id and "YOUR_TELEGRAM" not in bot_token and bot_token.strip() != "")
        has_discord = (discord_webhook and discord_webhook.strip() != "")
        
        telegram_ok = True
        discord_ok = True
        
        if has_telegram:
            telegram_ok = send_telegram_alert(bot_token, chat_id, platform, title, price, mrp, discount, img_url, final_url, is_verified_low, deal_score)
            
        if has_discord:
            discord_ok = send_discord_webhook(discord_webhook, title, price, mrp, discount, img_url, final_url, is_verified_low, deal_score)
            
        # If any active dispatch channels failed, retry with exponential backoff
        if (has_telegram and not telegram_ok) or (has_discord and not discord_ok):
            if retries < 3:
                job["retries"] = retries + 1
                backoff = (2 ** retries) * 5 # 5s, 10s, 20s
                logging.warning(f"Notification broadcast failed. Retrying job in {backoff} seconds (Attempt {retries + 1}/3)...")
                threading.Timer(backoff, lambda: notification_queue.put(job)).start()
            else:
                logging.error(f"Failed to broadcast notification after 3 attempts: {title[:30]}...")
                
        notification_queue.task_done()

def enqueue_alert(platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, deal_score: float):
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
        "retries": 0
    }
    notification_queue.put(job)

def start_notifier():
    t = threading.Thread(target=notifier_worker, daemon=True)
    t.start()
