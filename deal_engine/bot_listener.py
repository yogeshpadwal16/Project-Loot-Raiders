import time
import logging
import threading
import requests
import re
from urllib.parse import urlparse, parse_qs
from database.db_session import SessionLocal
from knowledge_base.models import AlertSubscription
from utils.parser import extract_amazon_asin, extract_flipkart_pid
from config.settings import load_settings

def check_channel_membership(bot_token: str, channel_id: str, user_id: int) -> bool:
    """
    Checks if a user is a member of the main Telegram channel.
    """
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
        params = {"chat_id": channel_id, "user_id": user_id}
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            status = data.get("result", {}).get("status", "left")
            return status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Error checking channel membership: {e}")
    return False

def send_bot_message(bot_token: str, chat_id: str, text: str):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Error sending bot reply: {e}")

def bot_listener_loop():
    logging.info("Telegram Bot Updates Listener thread started.")
    offset = 0
    
    while True:
        settings = load_settings()
        bot_token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id") # e.g., @LootRaidersDeals
        
        if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "":
            # Bot not configured yet, pause
            time.sleep(10)
            continue
            
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            params = {"offset": offset, "timeout": 20}
            res = requests.get(url, params=params, timeout=25)
            
            if res.status_code != 200:
                time.sleep(5)
                continue
                
            updates = res.json().get("result", [])
            for update in updates:
                offset = update.get("update_id", 0) + 1
                message = update.get("message", {})
                if not message:
                    continue
                    
                chat = message.get("chat", {})
                user = message.get("from", {})
                text = message.get("text", "").strip()
                
                user_id = user.get("id")
                chat_id_user = chat.get("id")
                
                if not text or not user_id:
                    continue
                    
                # Handle /start or /help
                if text.startswith("/start") or text.startswith("/help"):
                    welcome = (
                        "🍊💣 *Welcome to Loot Raiders Price Alert Bot!* 💣🍊\n\n"
                        "I can track Amazon & Flipkart items and message you *instantly* the second their price drops below your target!\n\n"
                        "👉 *How to set an alert:*\n"
                        "Send me the product link and your target price in Indian Rupees.\n\n"
                        "Example:\n"
                        "`https://www.amazon.in/dp/B0CX1G2Y4C 499`\n\n"
                        "--- \n"
                        "⚠️ *Requirement:* You must be a joined subscriber of our main channel @LootRaidersDeals to use this free bot!"
                    )
                    send_bot_message(bot_token, chat_id_user, welcome)
                    continue
                    
                # Parse message for link and target price
                urls = re.findall(r'(https?://[^\s]+)', text)
                if not urls:
                    reply = "❌ *Error:* Please send a valid product link followed by your target price (e.g. `https://amazon.in/dp/B0CX1G2Y4C 499`)."
                    send_bot_message(bot_token, chat_id_user, reply)
                    continue
                    
                product_url = urls[0]
                # Find any digits remaining in message to parse target price
                text_no_url = text.replace(product_url, "").strip()
                digits = re.findall(r'\b[0-9]+\b', text_no_url)
                
                if not digits:
                    reply = "❌ *Error:* Please specify a target price in rupees (e.g. `[link] 499`)."
                    send_bot_message(bot_token, chat_id_user, reply)
                    continue
                    
                target_price = int(digits[0])
                
                # Check channel membership (growth gate!)
                is_member = check_channel_membership(bot_token, chat_id, user_id)
                if not is_member:
                    join_req = (
                        "❌ *Access Denied!*\n\n"
                        "To activate free personal price alerts, you must first join our main Loot Alerts channel: @LootRaidersDeals.\n\n"
                        "👉 [Click here to join @LootRaidersDeals](https://t.me/LootRaidersDeals)\n\n"
                        "After joining, send me the product link and price again!"
                    )
                    send_bot_message(bot_token, chat_id_user, join_req)
                    continue
                    
                # Extract product id and platform
                product_id = None
                platform = None
                
                if "amazon" in product_url.lower():
                    product_id = extract_amazon_asin(product_url)
                    platform = "amazon"
                elif "flipkart" in product_url.lower():
                    product_id = extract_flipkart_pid(product_url)
                    platform = "flipkart"
                    
                if not product_id:
                    reply = "❌ *Error:* Could not recognize a valid Amazon ASIN or Flipkart PID in that link. Make sure it is a standard product page."
                    send_bot_message(bot_token, chat_id_user, reply)
                    continue
                    
                # Save subscription in Database
                db = SessionLocal()
                try:
                    # Check if already exists, else create
                    sub = db.query(AlertSubscription).filter_by(user_chat_id=str(chat_id_user), product_id=product_id).first()
                    if not sub:
                        sub = AlertSubscription(
                            user_chat_id=str(chat_id_user),
                            product_id=product_id,
                            platform=platform,
                            target_price=target_price
                        )
                        db.add(sub)
                    else:
                        sub.target_price = target_price
                    db.commit()
                    
                    ok_msg = (
                        f"✅ *Price Alert Activated!* \n\n"
                        f"📦 *Product ID:* `{product_id}`\n"
                        f"📈 *Target Price:* Under ₹{target_price:,}\n\n"
                        f"I am monitoring this item. The second it falls to or below ₹{target_price:,}, I will DM you here! Thank you for subscribing."
                    )
                    send_bot_message(bot_token, chat_id_user, ok_msg)
                except Exception as db_err:
                    db.rollback()
                    send_bot_message(bot_token, chat_id_user, "❌ Failed to save alert subscription due to database error.")
                finally:
                    db.close()
                    
        except Exception as e:
            logging.error(f"Error in Telegram Bot listener loop: {e}")
            time.sleep(5)

def check_and_dispatch_personal_alerts(product_id: str, platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str):
    """
    Checks if any personal alert subscriptions match a newly crawled drop,
    and dispatches direct messages to those users.
    """
    settings = load_settings()
    bot_token = settings.get("telegram_bot_token")
    if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "":
        return
        
    db = SessionLocal()
    try:
        subs = db.query(AlertSubscription).filter(
            AlertSubscription.product_id == product_id,
            AlertSubscription.target_price >= price
        ).all()
        
        for sub in subs:
            alert_copy = (
                f"🚨 *PRICE ALERT MATCHED!* 🚨\n\n"
                f"📦 *{title[:80]}...*\n\n"
                f"💰 *Current Price:* ₹{price:,} (MRP: ₹{mrp:,})\n"
                f"📈 *Your Target:* Under ₹{sub.target_price:,}\n"
                f"📉 *Discount:* {discount:.0f}% OFF\n\n"
                f"👉 [GRAB YOUR LOOT DEAL NOW]({final_url})"
            )
            # Send DM
            send_bot_message(bot_token, sub.user_chat_id, alert_copy)
            
            # Delete subscription after match (one-shot alert!)
            db.delete(sub)
        db.commit()
    except Exception as e:
        db.rollback()
        logging.error(f"Error processing personal alerts: {e}")
    finally:
        db.close()

def start_telegram_bot_listener():
    t = threading.Thread(target=bot_listener_loop, daemon=True)
    t.start()
