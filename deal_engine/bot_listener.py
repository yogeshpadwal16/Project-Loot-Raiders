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
                
                # Check for callback queries (Feature 3: inline button clicks from channel)
                callback_query = update.get("callback_query")
                if callback_query:
                    handle_callback_query(bot_token, callback_query)
                    continue
                    
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
                    
                # Resolve bot username on demand for invite links
                bot_username = "LootRaidersDealsBot"
                try:
                    res_me = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
                    if res_me.status_code == 200:
                        bot_username = res_me.json().get("result", {}).get("username", bot_username)
                except Exception:
                    pass

                # Handle /start or /help
                if text.startswith("/start") or text.startswith("/help"):
                    # Check if there is a referral parameter: e.g. "/start ref_12345" (Feature 21 & 24)
                    ref_match = re.match(r'^/start\s+ref_(\d+)', text)
                    if ref_match:
                        referrer_id = ref_match.group(1)
                        referred_id = str(user_id)
                        
                        if referrer_id != referred_id:
                            db = SessionLocal()
                            try:
                                from knowledge_base.models import ReferralLog
                                existing_ref = db.query(ReferralLog).filter_by(referred_id=referred_id).first()
                                if not existing_ref:
                                    # Log referral
                                    new_ref = ReferralLog(
                                        referrer_id=referrer_id,
                                        referred_id=referred_id
                                    )
                                    db.add(new_ref)
                                    db.commit()
                                    
                                    # Award points: +50 to referrer, +10 welcome bonus to referred
                                    ref_username = user.get("username") or user.get("first_name") or "Friend"
                                    award_points(db, referrer_id, None, 50, "referral")
                                    award_points(db, referred_id, user.get("username"), 10, "vote")
                                    
                                    # Notify referrer
                                    send_bot_message(bot_token, referrer_id, f"ðŸŽ‰ *Awesome!* Your friend @{ref_username} joined using your invite link. You earned *50 points*!")
                                    
                                    welcome = (
                                        f"🟠💣 *Welcome to Loot Raiders!* 💣🟠\n\n"
                                        f"You successfully joined via referral link. You have been awarded *10 welcome points*! ðŸŽ\n\n"
                                        "I can track Amazon & Flipkart items and message you *instantly* the second their price drops below your target!\n\n"
                                        "Type `/help` to see all commands."
                                    )
                                    send_bot_message(bot_token, chat_id_user, welcome)
                                    continue
                            except Exception as ref_err:
                                logging.error(f"Error handling referral start: {ref_err}")
                            finally:
                                db.close()

                    welcome = (
                        "🟠💣 *Welcome to Loot Raiders Price Alert Bot!* 💣🟠\n\n"
                        "I can track Amazon & Flipkart items and message you *instantly* the second their price drops below your target!\n\n"
                        "👉‰ *How to set an alert:*\n"
                        "Send me the product link and your target price in Indian Rupees.\n"
                        "Example:\n"
                        "`https://www.amazon.in/dp/B0CX1G2Y4C 499` or `/track https://www.amazon.in/dp/B0CX1G2Y4C 499`\n\n"
                        "👉‰ *Manage your watchlists:*\n"
                        "• `/watchlist` or `/list` - View your active price alerts\n"
                        "• `/untrack <product_id>` - Stop tracking a specific product\n\n"
                        "👉‰ *Manage your credit card wallet (Wallet Optimizer):*\n"
                        "• `/wallet` - View your saved cards\n"
                        "• `/wallet add <card>` - Add card (e.g. `sbi`, `hdfc`, `icici`, `axis`)\n"
                        "• `/wallet remove <card>` - Remove card\n\n"
                        "👉‰ *Rewards & Gamification:*\n"
                        "• `/points` or `/score` - View your profile and points\n"
                        "• `/leaderboard` or `/top` - View top 10 deal finders\n"
                        "• `/invite` or `/share` - Get your invite link to share on WhatsApp\n"
                        "• `/raffle` - Enter daily voucher giveaways\n\n"
                        "--- \n"
                        "⚡ ï¸ *Requirement:* You must be a joined subscriber of our main channel @LootRaidersDeals to use this free bot!"
                    )
                    send_bot_message(bot_token, chat_id_user, welcome)
                    continue
                    
                # Support command prefix for tracking
                if text.startswith("/track"):
                    text = text.replace("/track", "").strip()
                    
                # Handle /watchlist or /list
                if text.startswith("/watchlist") or text.startswith("/list"):
                    handle_watchlist_command(bot_token, chat_id_user, user_id)
                    continue
                    
                # Handle /untrack
                if text.startswith("/untrack"):
                    handle_untrack_command(bot_token, chat_id_user, user_id, text)
                    continue
                    
                # Handle /wallet
                if text.startswith("/wallet"):
                    handle_wallet_command(bot_token, chat_id_user, user_id, text)
                    continue

                # Handle /leaderboard or /top (Feature 25)
                if text.startswith("/leaderboard") or text.startswith("/top"):
                    handle_leaderboard_command(bot_token, chat_id_user, user_id)
                    continue

                # Handle /points or /score (Feature 25)
                if text.startswith("/points") or text.startswith("/score"):
                    handle_points_command(bot_token, chat_id_user, user_id)
                    continue

                # Handle /invite or /share (Feature 21 & 24)
                if text.startswith("/invite") or text.startswith("/share"):
                    handle_invite_command(bot_token, chat_id_user, user_id, bot_username)
                    continue

                # Handle /raffle (Feature 22)
                if text.startswith("/raffle"):
                    handle_raffle_command(bot_token, chat_id_user, user_id, text, chat_id)
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
                        "👉‰ [Click here to join @LootRaidersDeals](https://t.me/LootRaidersDeals)\n\n"
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
                        f"✨… *Price Alert Activated!* \n\n"
                        f"ðŸ“¦ *Product ID:* `{product_id}`\n"
                        f"ðŸ“ˆ *Target Price:* Under ₹{target_price:,}\n\n"
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

def award_points(db, user_id, username, points_to_add, action_type):
    from knowledge_base.models import UserScore
    user_score = db.query(UserScore).filter_by(user_id=str(user_id)).first()
    if not user_score:
        display_name = username or f"User_{str(user_id)[:5]}"
        user_score = UserScore(
            user_id=str(user_id),
            username=display_name,
            points=0,
            voted_count=0,
            referrals_count=0
        )
        db.add(user_score)
    
    user_score.points += points_to_add
    if username:
        user_score.username = username
        
    if action_type == "vote":
        user_score.voted_count += 1
    elif action_type == "referral":
        user_score.referrals_count += 1
        
    db.commit()
    logging.info(f"Awarded {points_to_add} points to user {user_id} ({username}) for {action_type}. Total: {user_score.points}")

def handle_callback_query(bot_token: str, callback_query: dict):
    """
    Processes inline button clicks (verified/expired votes) from the Telegram channel.
    """
    from database.db_session import SessionLocal
    from knowledge_base.models import DealVote
    from deal_engine.notifier import update_telegram_message
    
    query_id = callback_query.get("id")
    user = callback_query.get("from", {})
    user_id = str(user.get("id"))
    data = callback_query.get("data", "") # e.g. "vote:verify:product_id"
    
    if not data.startswith("vote:"):
        return
        
    parts = data.split(":")
    if len(parts) < 3:
        return
        
    action = parts[1] # "verify" or "expire"
    product_id = parts[2]
    
    db = SessionLocal()
    try:
        # Check if user already voted on this product
        existing_vote = db.query(DealVote).filter_by(
            product_id=product_id,
            user_id=user_id
        ).first()
        
        toast_text = ""
        if existing_vote:
            if existing_vote.vote_type == action:
                # Remove vote if clicked same button again (toggle off)
                db.delete(existing_vote)
                toast_text = f"Removed your '{action.capitalize()}' vote."
                # Subtract 5 points
                award_points(db, user_id, user.get("username") or user.get("first_name"), -5, "vote_remove")
            else:
                # Switch vote type if clicked different button
                existing_vote.vote_type = action
                existing_vote.timestamp = time.time()
                toast_text = f"Switched vote to '{action.capitalize()}'."
        else:
            # Record new vote
            new_vote = DealVote(
                product_id=product_id,
                vote_type=action,
                user_id=user_id,
                timestamp=time.time()
            )
            db.add(new_vote)
            toast_text = f"Registered your '{action.capitalize()}' vote."
            # Award 5 points
            award_points(db, user_id, user.get("username") or user.get("first_name"), 5, "vote")
            
        db.commit()
        
        # Answer callback query to display a brief toast
        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        payload = {
            "callback_query_id": query_id,
            "text": toast_text,
            "show_alert": False
        }
        requests.post(url, json=payload, timeout=10)
        
        # Trigger message update on the channel message
        update_telegram_message(product_id)
        
    except Exception as e:
        db.rollback()
        logging.error(f"Error handling callback query: {e}")
        try:
            url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
            payload = {
                "callback_query_id": query_id,
                "text": "Vote registration failed.",
                "show_alert": False
            }
            requests.post(url, json=payload, timeout=10)
        except Exception:
            pass
    finally:
        db.close()

def handle_watchlist_command(bot_token: str, chat_id_user: int, user_id: int):
    from database.db_session import SessionLocal
    from knowledge_base.models import AlertSubscription
    
    db = SessionLocal()
    try:
        subs = db.query(AlertSubscription).filter_by(user_chat_id=str(chat_id_user)).all()
        if not subs:
            reply = "ðŸ“¦ *You are not tracking any products right now.*\n\nSend a link followed by a target price to start tracking!"
        else:
            sub_list = []
            for i, sub in enumerate(subs, 1):
                sub_list.append(f"{i}. *{sub.platform.upper()} ID:* `{sub.product_id}` | Target: *₹{sub.target_price:,}*")
            reply = "ðŸ“¦ *Your Active Price Watchlist:*\n\n" + "\n".join(sub_list) + "\n\n👉‰ *To untrack:* `/untrack <product_id>`"
        send_bot_message(bot_token, chat_id_user, reply)
    except Exception as db_err:
        logging.error(f"Error listing watchlist: {db_err}")
        send_bot_message(bot_token, chat_id_user, "❌ Database error reading watchlist.")
    finally:
        db.close()

def handle_untrack_command(bot_token: str, chat_id_user: int, user_id: int, text: str):
    from database.db_session import SessionLocal
    from knowledge_base.models import AlertSubscription
    
    parts = text.split()
    if len(parts) < 2:
        send_bot_message(bot_token, chat_id_user, "❌ *Error:* Please specify a product ID (e.g. `/untrack B0CX1G2Y4C`).")
        return
        
    product_id = parts[1].strip()
    db = SessionLocal()
    try:
        sub = db.query(AlertSubscription).filter_by(user_chat_id=str(chat_id_user), product_id=product_id).first()
        if not sub:
            reply = f"❌ *Error:* Product ID `{product_id}` was not found in your watchlist."
        else:
            db.delete(sub)
            db.commit()
            reply = f"✨… Stopped tracking Product ID `{product_id}`."
        send_bot_message(bot_token, chat_id_user, reply)
    except Exception as db_err:
        db.rollback()
        logging.error(f"Error untracking product: {db_err}")
        send_bot_message(bot_token, chat_id_user, "❌ Failed to untrack product from database.")
    finally:
        db.close()

def handle_wallet_command(bot_token: str, chat_id_user: int, user_id: int, text: str):
    """
    Handles user credit card wallet configuration via the Telegram bot.
    """
    from database.db_session import SessionLocal
    from knowledge_base.models import UserWalletCard
    
    parts = text.split()
    if len(parts) == 1 or (len(parts) == 2 and parts[1].lower() == "list"):
        db = SessionLocal()
        try:
            cards = db.query(UserWalletCard).filter_by(user_id=str(user_id)).all()
            if not cards:
                reply = (
                    "💳 *Your Credit Card Wallet is empty!*\n\n"
                    "I can suggest the best card to use for discounts when matching alerts.\n\n"
                    "👉‰ *Add cards using:*\n"
                    "`/wallet add <card_name>` (e.g. `sbi`, `hdfc`, `icici`, `axis`, `onecard`)\n\n"
                    "Example:\n"
                    "`/wallet add SBI`"
                )
            else:
                card_list = "\n".join([f"• 💳 *{c.card_name.upper()}*" for c in cards])
                reply = (
                    "💳 *Your Tracked Credit Cards:*\n\n"
                    f"{card_list}\n\n"
                    "👉‰ *To add another card:*\n"
                    "`/wallet add <card_name>`\n\n"
                    "👉‰ *To remove a card:*\n"
                    "`/wallet remove <card_name>`"
                )
            send_bot_message(bot_token, chat_id_user, reply)
        except Exception as db_err:
            logging.error(f"Error querying user wallet: {db_err}")
            send_bot_message(bot_token, chat_id_user, "❌ Database error reading wallet.")
        finally:
            db.close()
            
    elif len(parts) >= 3 and parts[1].lower() == "add":
        card_name = parts[2].lower().strip()
        valid_cards = ["sbi", "hdfc", "icici", "axis", "onecard", "federal", "hsbc", "citi", "yesbank", "kotak", "rbl", "bob", "amex", "indusind"]
        if card_name not in valid_cards:
            reply = f"❌ *Error:* Unsupported card. Supported cards are: {', '.join([c.upper() for c in valid_cards])}."
            send_bot_message(bot_token, chat_id_user, reply)
            return
            
        db = SessionLocal()
        try:
            existing = db.query(UserWalletCard).filter_by(user_id=str(user_id), card_name=card_name).first()
            if existing:
                reply = f"💳 *{card_name.upper()}* is already in your wallet!"
            else:
                new_card = UserWalletCard(
                    user_id=str(user_id),
                    card_name=card_name
                )
                db.add(new_card)
                db.commit()
                reply = f"✨… Added *{card_name.upper()}* credit card to your wallet successfully!"
            send_bot_message(bot_token, chat_id_user, reply)
        except Exception as db_err:
            db.rollback()
            logging.error(f"Error adding wallet card: {db_err}")
            send_bot_message(bot_token, chat_id_user, "❌ Failed to add card to database.")
        finally:
            db.close()
            
    elif len(parts) >= 3 and parts[1].lower() == "remove":
        card_name = parts[2].lower().strip()
        db = SessionLocal()
        try:
            existing = db.query(UserWalletCard).filter_by(user_id=str(user_id), card_name=card_name).first()
            if not existing:
                reply = f"❌ *Error:* Card *{card_name.upper()}* not found in your wallet."
            else:
                db.delete(existing)
                db.commit()
                reply = f"✨… Removed *{card_name.upper()}* card from your wallet."
            send_bot_message(bot_token, chat_id_user, reply)
        except Exception as db_err:
            db.rollback()
            logging.error(f"Error removing wallet card: {db_err}")
            send_bot_message(bot_token, chat_id_user, "❌ Failed to remove card from database.")
        finally:
            db.close()
            
    else:
        reply = "❌ *Error:* Unknown command format. Use `/wallet`, `/wallet add <card>`, or `/wallet remove <card>`."
        send_bot_message(bot_token, chat_id_user, reply)

def get_matching_wallet_offers(user_id: str, bank_offers: list) -> str:
    """
    Compares product bank offers with user's wallet cards and recommends the matching cards.
    """
    from database.db_session import SessionLocal
    from knowledge_base.models import UserWalletCard
    
    db = SessionLocal()
    user_cards = []
    try:
        cards = db.query(UserWalletCard).filter_by(user_id=str(user_id)).all()
        user_cards = [c.card_name.lower() for c in cards]
    except Exception as e:
        logging.error(f"Failed to query wallet cards: {e}")
    finally:
        db.close()
        
    if not user_cards:
        return "ðŸ’¡ _Add your credit cards using `/wallet add <card>` (e.g. sbi, hdfc, icici) to get matching wallet suggestions!_"
        
    matched = []
    for offer in (bank_offers or []):
        for card in user_cards:
            if card in offer.lower():
                matched.append(f"💳 *{card.upper()}:* {offer}")
                
    if matched:
        return "ðŸ’¡ *Best Wallet Card to Use:*\n" + "\n".join(matched)
    else:
        return "ðŸ’¡ _None of your wallet cards match the current bank promotions._"

def check_and_dispatch_personal_alerts(product_id: str, platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, bank_offers: list = None):
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
            wallet_recommendation = get_matching_wallet_offers(sub.user_chat_id, bank_offers or [])
            alert_copy = (
                f"🚨 *PRICE ALERT MATCHED!* 🚨\n\n"
                f"ðŸ“¦ *{title[:80]}...*\n\n"
                f"💰 *Current Price:* ₹{price:,} (MRP: ₹{mrp:,})\n"
                f"ðŸ“ˆ *Your Target:* Under ₹{sub.target_price:,}\n"
                f"📉 *Discount:* {discount:.0f}% OFF\n\n"
                f"{wallet_recommendation}\n\n"
                f"👉‰ [GRAB YOUR LOOT DEAL NOW]({final_url})"
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

def check_is_admin(bot_token: str, chat_id: str, user_id: int) -> bool:
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
        params = {"chat_id": chat_id, "user_id": user_id}
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            status = data.get("result", {}).get("status", "left")
            return status in ["administrator", "creator"]
    except Exception as e:
        logging.error(f"Error checking admin status: {e}")
    return False

def handle_leaderboard_command(bot_token: str, chat_id: str, user_id: str):
    from knowledge_base.models import UserScore
    db = SessionLocal()
    try:
        top_users = db.query(UserScore).order_by(UserScore.points.desc()).limit(10).all()
        user_rank_query = db.query(UserScore).order_by(UserScore.points.desc()).all()
        
        user_rank = "N/A"
        user_pts = 0
        for idx, u in enumerate(user_rank_query, 1):
            if u.user_id == str(user_id):
                user_rank = f"#{idx}"
                user_pts = u.points
                break
                
        text = "ðŸ† *LOOT RAIDERS LEADERBOARD* ðŸ†\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        
        icons = ["ðŸ¥‡", "ðŸ¥ˆ", "ðŸ¥‰"] + ["👉¤"] * 7
        for idx, u in enumerate(top_users):
            icon = icons[idx] if idx < len(icons) else "👉¤"
            uname = f"@{u.username}" if u.username else f"User {u.user_id[:5]}..."
            text += f"{icon} *{idx+1}.* {uname} â€” `{u.points:,} pts` (Votes: {u.voted_count}, Refs: {u.referrals_count})\n"
            
        text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"ðŸŽ¯ *Your Rank:* `{user_rank}` (Points: `{user_pts:,} pts`)\n"
        text += "\nInvite friends with `/invite` to climb the ranks! 🚀"
        send_bot_message(bot_token, chat_id, text)
    except Exception as e:
        logging.error(f"Error serving leaderboard: {e}")
    finally:
        db.close()

def handle_points_command(bot_token: str, chat_id: str, user_id: str):
    from knowledge_base.models import UserScore
    db = SessionLocal()
    try:
        u = db.query(UserScore).filter_by(user_id=str(user_id)).first()
        if not u:
            text = "â„¹ï¸ *You don't have any points yet!* Start voting on deals or invite friends using `/invite` to earn points."
        else:
            text = (
                f"👉¤ *Your Loot Raiders Profile* 👉¤\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🪙 *Loot Points:* `{u.points:,} pts`\n"
                f"ðŸ—³ï¸ *Total Votes cast:* `{u.voted_count}`\n"
                f"👉¥ *Total Referrals:* `{u.referrals_count}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Keep voting and inviting to earn more points! 🚀"
            )
        send_bot_message(bot_token, chat_id, text)
    except Exception as e:
        logging.error(f"Error serving points: {e}")
    finally:
        db.close()

def handle_invite_command(bot_token: str, chat_id: str, user_id: str, bot_username: str):
    import urllib.parse
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    whatsapp_text = urllib.parse.quote(
        f"Get premium deals and pricing errors instantly on Loot Raiders! Join using my invite link: {ref_link}"
    )
    whatsapp_share_url = f"https://api.whatsapp.com/send?text={whatsapp_text}"
    
    text = (
        f"👉¥ *Loot Raiders Referrals* 👉¥\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Invite your friends to Loot Raiders and earn rewards:\n"
        f"• *+50 Points* per friend referred (when they start the bot).\n"
        f"• *+10 Points* welcome bonus for your friend.\n\n"
        f"ðŸ”— *Your Invite Link:*\n"
        f"`{ref_link}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"ðŸ“² *Share directly on WhatsApp:*\n"
        f"[Click here to Share on WhatsApp]({whatsapp_share_url})"
    )
    send_bot_message(bot_token, chat_id, text)

def handle_raffle_command(bot_token: str, chat_id: str, user_id: str, text: str, chat_id_channel: str):
    import random
    settings = load_settings()
    raffle_entries = settings.get("raffle_entries", [])
    
    parts = text.split()
    if len(parts) >= 2 and parts[1].lower() == "enter":
        db = SessionLocal()
        try:
            from knowledge_base.models import UserScore
            u = db.query(UserScore).filter_by(user_id=str(user_id)).first()
            if not u or (u.voted_count == 0 and u.referrals_count == 0):
                reply = "❌ *Entry Denied:* You must vote on at least 1 deal or invite 1 friend to enter the daily raffle! Go vote on deals in the channel."
                send_bot_message(bot_token, chat_id, reply)
                return
                
            user_str = str(user_id)
            if user_str in raffle_entries:
                reply = "â„¹ï¸ *You are already entered* in today's Daily Loot Raffle!"
            else:
                raffle_entries.append(user_str)
                settings["raffle_entries"] = raffle_entries
                save_settings(settings)
                reply = "ðŸŽ‰ *Congratulations!* You have been entered into today's Daily Loot Raffle. Win up to ₹500 voucher!"
            send_bot_message(bot_token, chat_id, reply)
        except Exception as e:
            logging.error(f"Error entering raffle: {e}")
        finally:
            db.close()
            
    elif len(parts) >= 2 and parts[1].lower() == "draw":
        if not check_is_admin(bot_token, chat_id_channel, user_id):
            send_bot_message(bot_token, chat_id, "❌ *Access Denied:* Only channel administrators can draw the raffle.")
            return
            
        if not raffle_entries:
            send_bot_message(bot_token, chat_id, "❌ *Error:* No entries found in the daily raffle.")
            return
            
        winner_id = random.choice(raffle_entries)
        
        # Resolve winner username
        db = SessionLocal()
        winner_name = f"User {winner_id[:5]}..."
        try:
            from knowledge_base.models import UserScore
            w = db.query(UserScore).filter_by(user_id=winner_id).first()
            if w and w.username:
                winner_name = f"@{w.username}"
        finally:
            db.close()
            
        # Announce Winner
        announcement = (
            f"ðŸŽ‰ðŸŽ <b>DAILY LOOT RAFFLE DRAW</b> ðŸŽðŸŽ‰\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"And the lucky winner of today's <b>₹500 Amazon Gift Card</b> is...\n\n"
            f"ðŸ† <b>Winner:</b> {winner_name} (ID: <code>{winner_id}</code>)\n\n"
            f"Congratulations! Admins will contact you shortly to transfer your prize. 🚀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Everyone else, stay tuned! Next raffle draw starts tomorrow!"
        )
        
        # Broadcast to channel
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id_channel, "text": announcement, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        
        # Clear entries for next draw
        settings["raffle_entries"] = []
        save_settings(settings)
        
        # Notify the sender
        send_bot_message(bot_token, chat_id, f"ðŸŽ‰ Drawn winner successfully: {winner_name}")
        
    else:
        entry_count = len(raffle_entries)
        reply = (
            f"ðŸŽ *Daily Loot Raffle* ðŸŽ\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"ðŸŽ *Today's Prize:* ₹500 Amazon Gift Card\n"
            f"ðŸŽŸï¸ *Total Entries today:* `{entry_count}`\n\n"
            f"👉‰ *How to enter:*\n"
            f"Type `/raffle enter` to submit your entry. "
            f"_(Requires at least 1 vote or 1 referral today)_"
        )
        send_bot_message(bot_token, chat_id, reply)

def start_telegram_bot_listener():
    t = threading.Thread(target=bot_listener_loop, daemon=True)
    t.start()
