import os
import queue
import threading
import time
import logging
import requests
import json
import re
from datetime import datetime
from config.settings import load_settings, save_settings
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from utils.image_generator import generate_deal_image
from deal_engine.bot_listener import check_and_dispatch_personal_alerts

notification_queue = queue.Queue()

def log_failure(component: str, context: str, err: Exception, severity: str = "ERROR", recovery_status: str = "Unresolved", recommended_action: str = ""):
    timestamp = datetime.now().isoformat()
    msg = (
        f"\n==========================================================================\n"
        f"ðŸš¨ FAILURE REPORTED:\n"
        f"ðŸ“… Timestamp: {timestamp}\n"
        f"ðŸ”Œ Component: {component}\n"
        f"ðŸ“ Context: {context}\n"
        f"ðŸ” Root Cause: {type(err).__name__} - {str(err)}\n"
        f"ðŸ”¥ Severity: {severity}\n"
        f"ðŸ©¹ Recovery Status: {recovery_status}\n"
        f"ðŸ’¡ Recommended Action: {recommended_action}\n"
        f"=========================================================================="
    )
    logging.error(msg)

def generate_gemini_caption(title: str, price: int, mrp: int, discount: float, final_url: str, is_verified_low: bool, deal_score: float, platform: str, comparison: str, price_stats: dict = None,
                            bank_offers: list = None, coupon_detail: str = "", review_grade: str = "N/A",
                            effective_cashback: str = "", upi_offer: str = "", offline_compare: str = "") -> str:
    settings = load_settings()
    api_key = os.environ.get("GEMINI_API_KEY") or settings.get("gemini_api_key")
    if not api_key or "YOUR_GEMINI" in api_key or api_key.strip() == "":
        return None
        
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
        
        prompt = (
            f"You are a professional, high-energy, witty shopping deal alert bot. Write a Telegram post in HTML formatting for this deal:\n\n"
            f"Product: {title}\n"
            f"Retailer: {platform.upper()}\n"
            f"Loot Price: Rs. {price:,}\n"
            f"Original MRP: Rs. {mrp:,}\n"
            f"Discount: {discount:.0f}% OFF\n"
            f"Verified 90-Day Low? {'Yes' if is_verified_low else 'No'}\n"
            f"Deal Score: {deal_score:.0f}/100\n"
            f"Affiliate Buy Link: {final_url}\n"
        )
        
        if coupon_detail:
            prompt += f"Coupon available: {coupon_detail}\n"
        if bank_offers:
            prompt += f"Bank Offers: {', '.join(bank_offers)}\n"
        if review_grade and review_grade != "N/A":
            prompt += f"Product Quality/Review Trust Grade: {review_grade}\n"
        if effective_cashback:
            prompt += f"Effective Price Calculation: {effective_cashback}\n"
        if upi_offer:
            prompt += f"UPI / RuPay specific offers: {upi_offer}\n"
        if offline_compare:
            prompt += f"Offline Price Comparison info: {offline_compare}\n"
            
        if price_stats:
            prompt += (
                f"\nLocal tracked historical price trends for this product (over past {price_stats['points_count']} price checks):\n"
                f"- Lowest tracked price: Rs. {price_stats['lowest']:,}\n"
                f"- Highest tracked price: Rs. {price_stats['highest']:,}\n"
                f"- Average tracked price: Rs. {int(price_stats['average']):,}\n"
            )
            
        if comparison:
            prompt += f"\nPrice Comparison on other platforms:\n{comparison}\n"
            
        prompt += (
            "\nFormatting Rules:\n"
            "- Use bold <b>...</b>, italics <i>...</i>, strike <s>...</s> for MRP, and code <code>...</code> for prices.\n"
            "- Include exact buy link in this HTML format: <a href='{final_url}'>ðŸ‘‰ CLICK HERE TO BUY NOW</a>\n"
            "- Keep it exciting, short, and use engaging shopping/warning emojis.\n"
            "- Write in clean, valid HTML tags that Telegram supports (only <b>, <i>, <s>, <u>, <code>, <pre>, <a>).\n"
            "- Return ONLY the post text (no markdown ```html wrappers, no extra explanation text)."
        )
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        res = requests.post(url, json=payload, headers={"x-goog-api-key": api_key}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            return text
    except Exception as e:
        logging.error(f"Gemini API caption failed: {e}")
    return None

def send_discord_webhook(webhook_url: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, deal_score: float = 0.0) -> bool:
    try:
        is_amazon = "amazon" in final_url.lower()
        embed = {
            "title": title[:250],
            "url": final_url,
            "color": 16750848 if is_amazon else 114686,
            "fields": [
                {"name": "Price", "value": f"â‚¹{price:,}", "inline": True},
                {"name": "MRP", "value": f"â‚¹{mrp:,}", "inline": True},
                {"name": "Discount", "value": f"{discount:.1f}% OFF", "inline": True},
                {"name": "Deal Score", "value": f"{deal_score:.1f}/100", "inline": True}
            ],
            "footer": {
                "text": "Loot Raiders Deal Alert â€¢ Curated by Yogesh Padwal"
            }
        }
        if is_verified_low:
            embed["description"] = "ðŸ”¥ **VERIFIED ALL-TIME LOW PRICE!**"
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

def send_whatsapp_alert(title: str, price: int, mrp: int, discount: float, final_url: str, is_verified_low: bool, deal_score: float) -> bool:
    settings = load_settings()
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.environ.get("TWILIO_WHATSAPP_FROM")
    to_whatsapp = os.environ.get("WHATSAPP_TO")
    
    if not (sid and auth_token and from_whatsapp and to_whatsapp):
        return False
        
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        
        message_body = (
            f"ðŸŠðŸ’£ *Loot Raiders Deal Alert!* ðŸ’£*ðŸŠ\n\n"
            f"ðŸ›ï¸ *{title[:60]}...*\n\n"
            f"ðŸ”¥ *Loot Price:* â‚¹{price:,} (MRP: ~â‚¹{mrp:,}~)\n"
            f"ðŸ“‰ *Discount:* {discount:.0f}% OFF\n"
            f"ðŸ’Ž *Deal Score:* {deal_score:.0f}/100\n\n"
            f"ðŸ‘‰ *Buy Link:* {final_url}"
        )
        
        payload = {
            "From": from_whatsapp if from_whatsapp.startswith("whatsapp:") else f"whatsapp:{from_whatsapp}",
            "To": to_whatsapp if to_whatsapp.startswith("whatsapp:") else f"whatsapp:{to_whatsapp}",
            "Body": message_body
        }
        
        res = requests.post(url, data=payload, auth=(sid, auth_token), timeout=10)
        if res.status_code in [200, 201]:
            logging.info("WhatsApp (Twilio) alert successfully dispatched.")
            return True
        else:
            logging.warning(f"WhatsApp alert dispatch failed: {res.status_code} - {res.text}")
    except Exception as e:
        logging.error(f"WhatsApp alert dispatch exception: {e}")
    return False

def send_email_alert(title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, deal_score: float) -> bool:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    
    settings = load_settings()
    smtp_server = settings.get("smtp_server")
    smtp_port = settings.get("smtp_port")
    smtp_user = settings.get("smtp_username")
    smtp_pass = settings.get("smtp_password")
    smtp_from = settings.get("smtp_from")
    smtp_to = settings.get("smtp_to")
    sendgrid_api_key = settings.get("sendgrid_api_key")
    
    if not sendgrid_api_key and (not smtp_server or not smtp_user or not smtp_pass or not smtp_from or not smtp_to):
        # Not configured, skip silently
        return False
        
    try:
        invite_link = settings.get("telegram_invite_link", "https://t.me/LootRaidersDeals")
        
        # Build beautiful HTML body
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; margin: 0; padding: 20px; background-color: #f8fafc; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }}
                .header {{ background: linear-gradient(135deg, #f97316, #ea580c); padding: 24px; text-align: center; color: white; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; }}
                .content {{ padding: 24px; }}
                .product-title {{ font-size: 18px; font-weight: 700; color: #1e293b; margin-bottom: 16px; line-height: 1.4; }}
                .price-box {{ display: flex; gap: 20px; background: #f1f5f9; padding: 16px; border-radius: 8px; margin-bottom: 20px; align-items: center; justify-content: space-around; }}
                .stat {{ text-align: center; }}
                .stat-lbl {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-bottom: 4px; }}
                .stat-val {{ font-size: 20px; font-weight: 800; }}
                .text-orange {{ color: #ea580c; }}
                .text-green {{ color: #16a34a; }}
                .text-strike {{ text-decoration: line-through; color: #94a3b8; }}
                .badge {{ background: #fee2e2; color: #dc2626; padding: 6px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700; display: inline-block; margin-bottom: 16px; }}
                .product-img {{ max-width: 100%; height: auto; border-radius: 8px; margin-bottom: 20px; display: block; border: 1px solid #e2e8f0; }}
                .btn-cta {{ display: block; background: #ea580c; color: white !important; text-decoration: none; text-align: center; padding: 14px 24px; border-radius: 8px; font-weight: 700; font-size: 16px; transition: background 0.2s; margin-bottom: 20px; }}
                .footer {{ background: #f1f5f9; padding: 20px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
                .footer a {{ color: #ea580c; text-decoration: none; font-weight: 600; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ðŸš€ Project Loot Raiders ðŸš€</h1>
                </div>
                <div class="content">
                    {f'<div class="badge">ðŸ”¥ VERIFIED ALL-TIME LOW PRICE</div>' if is_verified_low else ''}
                    <div class="product-title">{title}</div>
                    
                    {f'<img class="product-img" src="{img_url}" alt="Product Image" />' if img_url and 'base64' not in img_url else ''}
                    
                    <div class="price-box">
                        <div class="stat">
                            <div class="stat-lbl">Loot Price</div>
                            <div class="stat-val text-green">â‚¹{price:,}</div>
                        </div>
                        <div class="stat">
                            <div class="stat-lbl">Original MRP</div>
                            <div class="stat-val text-strike">â‚¹{mrp:,}</div>
                        </div>
                        <div class="stat">
                            <div class="stat-lbl">Discount</div>
                            <div class="stat-val text-orange">{discount:.0f}% OFF</div>
                        </div>
                    </div>
                    
                    <a class="btn-cta" href="{final_url}" target="_blank">GRAB THIS DEAL NOW â†’</a>
                </div>
                <div class="footer">
                    <p>You received this alert because you subscribed to Project Loot Raiders deal updates.</p>
                    <p>ðŸ“¢ <b>Want more deals?</b> <a href="{invite_link}" target="_blank">Join our Telegram Channel</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # 1. Try SendGrid REST API if configured
        if sendgrid_api_key and sendgrid_api_key.strip() != "" and "YOUR_SENDGRID" not in sendgrid_api_key:
            try:
                targets = [t.strip() for t in smtp_to.split(",") if t.strip()]
                personalizations = [{"to": [{"email": target}]} for target in targets]
                payload = {
                    "personalizations": personalizations,
                    "from": {
                        "email": smtp_from if smtp_from else "alerts@lootraiders.com",
                        "name": "Project Loot Raiders"
                    },
                    "subject": f"ðŸ”¥ LOOT ALERT: {discount:.0f}% OFF - {title[:50]}... (Rs. {price:,})",
                    "content": [
                        {
                            "type": "text/html",
                            "value": html_body
                        }
                    ]
                }
                headers = {
                    "Authorization": f"Bearer {sendgrid_api_key}",
                    "Content-Type": "application/json"
                }
                res = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers, timeout=15)
                if res.status_code in [200, 201, 202]:
                    logging.info(f"SendGrid API email alert successfully sent to {len(targets)} recipient(s).")
                    return True
                else:
                    logging.warning(f"SendGrid API email dispatch returned status {res.status_code}: {res.text}. Trying SMTP fallback.")
            except Exception as sg_err:
                logging.error(f"SendGrid API email alert failed: {sg_err}. Trying SMTP fallback.")
        
        # 2. SMTP fallback
        if smtp_server and smtp_user and smtp_pass and smtp_from and smtp_to:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"ðŸ”¥ LOOT ALERT: {discount:.0f}% OFF - {title[:50]}... (Rs. {price:,})"
            msg['From'] = smtp_from
            msg['To'] = smtp_to
            msg.attach(MIMEText(html_body, 'html'))
            
            # Connect to server
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            
            # Send mail
            targets = [t.strip() for t in smtp_to.split(",") if t.strip()]
            server.sendmail(smtp_from, targets, msg.as_string())
            server.quit()
            
            logging.info(f"Email alert successfully sent via SMTP to {len(targets)} recipient(s).")
            return True
            
        return False
    except Exception as e:
        logging.error(f"Email alert dispatch failed: {e}")
        return False

def send_telegram_alert(bot_token: str, chat_id: str, platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, deal_score: float, unique_id: str,
                        bank_offers: list = None, coupon_detail: str = "", review_grade: str = "N/A", auto_cart_url: str = None, include_invite_link: bool = True) -> bool:
    settings = load_settings()
    invite_link = settings.get("telegram_invite_link", "https://t.me/LootRaidersDeals").strip()
    cloaker_domain = settings.get("cloaker_domain", "").strip()
    if cloaker_domain:
        if not cloaker_domain.startswith("http"):
            cloaker_domain = "https://" + cloaker_domain
        buy_url = f"{cloaker_domain.rstrip('/')}/go/{unique_id}"
    else:
        buy_url = final_url
        
    is_amazon = "amazon" in platform.lower()
    from deal_engine.scorer import check_if_glitch
    is_glitch = check_if_glitch(price, mrp, discount, unique_id)
    
    # 1. Premium Headers
    if is_glitch:
        header = (
            "ðŸš¨ðŸš¨ <b>[ LOOT GLITCH ALERT ]</b> ðŸš¨ðŸš¨\n"
            "ðŸ”¥ <b>PRICE ERROR DETECTED</b> ðŸ”¥\n"
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"
        )
        badge = "âš ï¸ <b>HURRY! Prices will rise or sell out in seconds!</b>\nâš ï¸ <i>Forward to friends immediately!</i>\n"
    else:
        badge_title = f"{platform.upper()} LOOT"
        if "amazon" in platform.lower():
            icon = "ðŸŠ"
        elif "flipkart" in platform.lower():
            icon = "ðŸ’£"
        elif "myntra" in platform.lower():
            icon = "ðŸ‘—"
        elif "meesho" in platform.lower():
            icon = "ðŸ›ï¸"
        else:
            icon = "âœ¨"
            
        header = (
            f"<b>{icon} [ {badge_title} DEAL ] {icon}</b>\n"
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"
        )
        badge = "ðŸ”¥ <b>[ VERIFIED ALL-TIME LOW PRICE ]</b>\n" if is_verified_low else ""
        
    clean_title = title.split('\n')[0].strip()
    truncated_title = clean_title[:107] + "..." if len(clean_title) > 110 else clean_title
    
    # Query database for price comparisons on other platforms
    comparison_text = ""
    db = SessionLocal()
    try:
        words = [w.strip() for w in re.split(r'[^a-zA-Z0-9]', clean_title) if len(w) > 2]
        if len(words) >= 2:
            search_term = "%" + "%".join(words[:3]) + "%"
            matches = db.query(Product).filter(
                Product.title.like(search_term),
                Product.id != unique_id
            ).all()
            
            comparison_list = []
            seen_platforms = set()
            for match in matches:
                lp = db.query(PriceHistory).filter_by(product_id=match.id).order_by(PriceHistory.timestamp.desc()).first()
                if lp and match.platform != platform and match.platform not in seen_platforms:
                    comparison_list.append(f"  â€¢ {match.platform.upper()}: â‚¹{lp.price:,}")
                    seen_platforms.add(match.platform)
                    
            if comparison_list:
                comparison_text = "\n\nðŸ“Š <b>Multi-Retailer Comparison:</b>\n" + "\n".join(comparison_list)
    except Exception as db_err:
        logging.error(f"Error querying comparisons in notifier: {db_err}")
    finally:
        db.close()
        
    savings = mrp - price
    rating_score = deal_score / 10.0
    stars = "â˜…" * int(round(rating_score / 2)) + "â˜†" * (5 - int(round(rating_score / 2)))
    
    # Calculate price stats from local database
    price_stats = None
    db = SessionLocal()
    try:
        hist_prices = db.query(PriceHistory.price).filter_by(product_id=unique_id).all()
        if hist_prices:
            prices_list = [p[0] for p in hist_prices]
            price_stats = {
                "lowest": min(prices_list),
                "highest": max(prices_list),
                "average": sum(prices_list) / len(prices_list),
                "points_count": len(prices_list)
            }
    except Exception as e:
        logging.error(f"Error querying price history stats: {e}")
    finally:
        db.close()
        
    # 1.5 Calculate Effective Prices (Feature 7: SuperCoin & Pay Cashback)
    effective_cashback_text = ""
    effective_cashback_prompt = ""
    if "amazon" in platform.lower():
        effective_price = int(price * 0.95)
        effective_cashback_text = f"ðŸª™ <b>Effective Price:</b>  <code>â‚¹{effective_price:,}</code> (with Amazon Pay Card 5% Cashback)\n"
        effective_cashback_prompt = f"Effective Price (with 5% Amazon Pay Card Cashback): Rs. {effective_price}"
    elif "flipkart" in platform.lower():
        effective_price = int(price * 0.95)
        effective_cashback_text = f"ðŸª™ <b>Effective Price:</b>  <code>â‚¹{effective_price:,}</code> (with Flipkart Axis Card / SuperCoins)\n"
        effective_cashback_prompt = f"Effective Price (with Flipkart Axis Card or SuperCoins): Rs. {effective_price}"
        
    # 1.6 UPI / RuPay Offer Matcher (Feature 8)
    upi_matcher_text = ""
    upi_matcher_prompt = ""
    if bank_offers:
        for offer in bank_offers:
            if any(x in offer.lower() for x in ["rupay", "upi", "phonepe", "gpay", "paytm"]):
                upi_matcher_text = f"ðŸ“± <b>UPI / RuPay Offer:</b> Extra UPI app discount detected at checkout!\n"
                upi_matcher_prompt = "UPI / RuPay specific offers: Extra instant cashback is available for UPI payments."
                break
                
    # 1.7 Online vs. Offline Price Comparison (Feature 26)
    offline_retail_price = int(min(mrp, price * 1.25))
    offline_savings = max(0, offline_retail_price - price)
    offline_comparison_text = ""
    offline_comparison_prompt = ""
    if offline_savings > 100:
        offline_comparison_text = f"ðŸ¬ <b>Offline Store Match:</b> Typical price <code>â‚¹{offline_retail_price:,}</code> in retail stores (Save <code>â‚¹{offline_savings:,}</code>!)\n"
        offline_comparison_prompt = f"Offline retail comparison: Typical offline price is Rs. {offline_retail_price} (User saves Rs. {offline_savings} compared to local retail store)."

    # Attempt Gemini generation
    caption = generate_gemini_caption(truncated_title, price, mrp, discount, buy_url, is_verified_low, deal_score, platform, comparison_text, price_stats,
                                      bank_offers=bank_offers, coupon_detail=coupon_detail, review_grade=review_grade,
                                      effective_cashback=effective_cashback_prompt, upi_offer=upi_matcher_prompt, offline_compare=offline_comparison_prompt)
    
    if caption:
        # Prepend the official branded header so the platform is ALWAYS clear!
        caption = f"{header}\n\n{caption}"
    else:
        verification_text = "Verified All-Time Low" if is_verified_low else "Verified Price Drop"
        
        # Build extra promotional/meta fields
        promo_fields = ""
        if coupon_detail:
            promo_fields += f"ðŸ·ï¸ <b>Coupon:</b>        <code>{coupon_detail}</code>\n"
        if bank_offers:
            promo_fields += f"ðŸ’³ <b>Bank Offer:</b>    <code>{', '.join(bank_offers)}</code>\n"
        if review_grade and review_grade != "N/A":
            promo_fields += f"â­ <b>Review Trust:</b>  <code>Grade {review_grade}</code>\n"
        if promo_fields:
            promo_fields = f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n{promo_fields}"
            
        caption = (
            f"{header}\n"
            f"ðŸ›ï¸ <b>{truncated_title}</b>\n\n"
            f"{badge}"
            f"ðŸ’µ <b>Loot Price:</b>  <code>â‚¹{price:,}</code>\n"
            f"âŒ <b>Original MRP:</b> <s>â‚¹{mrp:,}</s>\n"
            f"ðŸ“‰ <b>Discount:</b>     <b>{discount:.0f}% OFF</b>\n"
            f"ðŸ’° <b>Total Savings:</b> <code>â‚¹{savings:,}</code>\n\n"
            f"{effective_cashback_text}"
            f"{upi_matcher_text}"
            f"{offline_comparison_text}"
            f"{promo_fields}"
            f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
            f"ðŸ’Ž <b>Loot Score:</b>   <code>{rating_score:.1f}/10.0</code> ({stars})\n"
            f"ðŸ›¡ï¸ <b>Verification:</b> <code>{verification_text}</code>"
            f"{comparison_text}\n\n"
            f"ðŸš€ <i>Price drops don't last! Grab it before stock ends!</i>\n"
            f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
            + (f"ðŸ“¢ <b>Join <a href='{invite_link}'>@LootRaidersDeals</a> for more verified loot!</b>" if include_invite_link else "")
        )
        
    # Guardrail: If caption exceeds 1000 chars, Telegram photo API fails.
    # Trim caption to a clean, high-impact format if it's too long.
    if len(caption) > 1000:
        verification_text = "Verified All-Time Low" if is_verified_low else "Verified Price Drop"
        promo_info = ""
        if coupon_detail:
            promo_info += f" | Coupon: {coupon_detail}"
        caption = (
            f"{header}\n\n"
            f"ðŸ›ï¸ <b>{truncated_title}</b>\n\n"
            f"ðŸ’Ž <b>Loot Price:</b> <code>â‚¹{price:,}</code> (<s>â‚¹{mrp:,}</s>)\n"
            f"ðŸ”¥ <b>Discount:</b> <b>{discount:.0f}% OFF</b>{promo_info}\n"
            f"ðŸ›¡ï¸ <b>Verification:</b> <code>{verification_text}</code>"
            + (f"\n\nðŸ“¢ <b>Join <a href='{invite_link}'>@LootRaidersDeals</a> for more!</b>" if include_invite_link else "")
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

    # 3. Build Inline Buy Button markup (Feature 3: Verification/Expiration Buttons)
    from knowledge_base.models import DealVote
    db = SessionLocal()
    vote_verify_count = 0
    vote_expire_count = 0
    try:
        vote_verify_count = db.query(DealVote).filter_by(product_id=unique_id, vote_type="verify").count()
        vote_expire_count = db.query(DealVote).filter_by(product_id=unique_id, vote_type="expire").count()
    except Exception as db_err:
        logging.error(f"Error querying votes for inline keyboard: {db_err}")
    finally:
        db.close()

    import json
    
    # Safety: Telegram requires absolute URLs for inline keyboard buttons
    if buy_url and not buy_url.startswith("http"):
        logging.warning(f"[Notifier] Fixing relative buy_url for {unique_id}: {buy_url[:80]}")
        if "flipkart" in platform.lower():
            buy_url = f"https://www.flipkart.com{buy_url}" if buy_url.startswith("/") else f"https://www.flipkart.com/{buy_url}"
        elif "amazon" in platform.lower():
            buy_url = f"https://www.amazon.in{buy_url}" if buy_url.startswith("/") else f"https://www.amazon.in/{buy_url}"
        else:
            buy_url = f"https://{buy_url}"
    if auto_cart_url and not auto_cart_url.startswith("http"):
        auto_cart_url = None  # Drop invalid auto-cart URL rather than crash
    
    row_1 = [
        {
            "text": "🛍️ BUY NOW 🛍️",
            "url": buy_url
        }
    ]
    if auto_cart_url:
        row_1.append({
            "text": "🛒 AUTO-CART 🛒",
            "url": auto_cart_url
        })
        
    reply_markup = {
        "inline_keyboard": [
            row_1,
            [
                {
                    "text": f"ðŸ”¥ Verified ({vote_verify_count})",
                    "callback_data": f"vote:verify:{unique_id}"
                },
                {
                    "text": f"âŒ Expired ({vote_expire_count})",
                    "callback_data": f"vote:expire:{unique_id}"
                }
            ]
        ]
    }
    reply_markup_json = json.dumps(reply_markup)

    # 4. Upload raw product image or dynamic image card to Telegram
    photo_sent = False
    
    # Try sending raw image first if it's a valid remote URL
    if img_url and img_url.startswith("http") and not img_url.startswith("data:image"):
        try:
            endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            payload = {
                "chat_id": chat_id,
                "photo": img_url,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": reply_markup_json
            }
            res = requests.post(endpoint, json=payload, timeout=25)
            if res.status_code == 200:
                logging.info(f"Telegram raw product image uploaded successfully -> {truncated_title[:20]}...")
                photo_sent = True
                save_telegram_message_info(unique_id, res, caption)
            else:
                logging.warning(f"Telegram photo send for raw URL returned {res.status_code}: {res.text}. Falling back to local card.")
        except Exception as raw_send_err:
            logging.error(f"Failed to send raw product image URL: {raw_send_err}. Falling back to local card.")

    # Fallback to local PIL card if raw image send was not successful
    if not photo_sent and local_card_path and os.path.exists(local_card_path):
        try:
            endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(local_card_path, "rb") as f:
                files = {"photo": f}
                payload = {
                    "chat_id": chat_id, 
                    "caption": caption, 
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup_json
                }
                res = requests.post(endpoint, data=payload, files=files, timeout=25)
                if res.status_code == 200:
                    logging.info(f"Telegram verification card uploaded successfully -> {truncated_title[:20]}...")
                    photo_sent = True
                    save_telegram_message_info(unique_id, res, caption)
                else:
                    logging.warning(f"Telegram Photo method returned {res.status_code}: {res.text}")
        except Exception as upload_err:
            logging.error(f"Failed to upload photo card: {upload_err}")
        finally:
            try: os.remove(local_card_path)
            except Exception: pass
    elif local_card_path:
        # Cleanup local card path if we already successfully sent raw image URL
        try: os.remove(local_card_path)
        except Exception: pass
    if photo_sent:
        return True
        
    logging.error(f"Telegram photo card failed to send for {truncated_title[:20]}... Skipping text-only fallback per product rules.")
    return False

def save_telegram_message_info(unique_id: str, res, caption: str):
    """
    Saves the Telegram channel message ID and original caption to the database.
    """
    try:
        data = res.json()
        message_id = data.get("result", {}).get("message_id")
        if message_id:
            from database.db_session import SessionLocal
            from knowledge_base.models import Product
            db = SessionLocal()
            try:
                prod = db.query(Product).filter_by(id=unique_id).first()
                if prod:
                    prod.telegram_message_id = message_id
                    prod.telegram_caption = caption
                    db.commit()
            except Exception as db_err:
                db.rollback()
                logging.error(f"Error saving telegram message info to DB: {db_err}")
            finally:
                db.close()
    except Exception as e:
        logging.error(f"Failed to parse telegram response: {e}")

def update_telegram_message(product_id: str):
    """
    Dynamically recalculates the hotness gauge and vote counts for a deal,
    and updates the corresponding Telegram channel message in real-time.
    If the deal reaches the expiration threshold, it marks the post as expired.
    """
    from database.db_session import SessionLocal
    from knowledge_base.models import Product, ClickLog, DealVote, PriceHistory
    from config.settings import load_settings
    import requests
    import json
    
    settings = load_settings()
    bot_token = settings.get("telegram_bot_token")
    channel_id = settings.get("telegram_chat_id")
    
    if not bot_token or not channel_id or "YOUR_TELEGRAM" in bot_token:
        return
        
    db = SessionLocal()
    try:
        product = db.query(Product).filter_by(id=product_id).first()
        if not product or not product.telegram_message_id or not product.telegram_caption:
            return
            
        message_id = product.telegram_message_id
        original_caption = product.telegram_caption
        buy_url = product.url
        
        # Query recent clicks count (last 15 minutes)
        import time
        recent_clicks = db.query(ClickLog).filter(
            ClickLog.product_id == product_id,
            ClickLog.timestamp >= time.time() - 900
        ).count()
        
        # Query verified and expired votes count
        verifies = db.query(DealVote).filter_by(product_id=product_id, vote_type="verify").count()
        expires = db.query(DealVote).filter_by(product_id=product_id, vote_type="expire").count()
        
        # Check if deal should expire (Threshold: 3 net expired votes)
        is_expired = (expires - verifies) >= 3
        
        if is_expired:
            new_caption = f"âŒ <b>[ DEAL EXPIRED / SOLD OUT ]</b> âŒ\n\n<s>{original_caption}</s>"
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "âŒ EXPIRED / SOLD OUT âŒ",
                            "url": buy_url
                        }
                    ]
                ]
            }
        else:
            hotness_text = ""
            if recent_clicks > 0:
                hotness = min(10.0, 5.0 + (recent_clicks * 0.5))
                fires = "ðŸ”¥" * min(3, max(1, int(hotness / 3)))
                hotness_text = f"\n\nâš¡ <b>{fires} Hotness: {hotness:.1f}/10</b> - <i>{recent_clicks} clicks in last 15m</i>"
                
            new_caption = f"{original_caption}{hotness_text}"
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "ðŸ›ï¸ CLICK HERE TO BUY NOW ðŸ›ï¸",
                            "url": buy_url
                        }
                    ],
                    [
                        {
                            "text": f"ðŸ”¥ Verified ({verifies})",
                            "callback_data": f"vote:verify:{product_id}"
                        },
                        {
                            "text": f"âŒ Expired ({expires})",
                            "callback_data": f"vote:expire:{product_id}"
                        }
                    ]
                ]
            }
            
        endpoint = f"https://api.telegram.org/bot{bot_token}/editMessageCaption"
        payload = {
            "chat_id": channel_id,
            "message_id": message_id,
            "caption": new_caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(reply_markup)
        }
        res = requests.post(endpoint, json=payload, timeout=15)
        if res.status_code == 200:
            logging.info(f"Telegram channel message {message_id} dynamically updated for {product_id}.")
        else:
            logging.warning(f"Failed to update Telegram channel message {message_id}: {res.text}")
            
    except Exception as e:
        logging.error(f"Error in update_telegram_message: {e}")
    finally:
        db.close()

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
            "ðŸŠðŸ’£ <b>LOOT RAIDERS DAILY DIGEST</b> ðŸ’£ðŸŠ\n"
            f"ðŸ“… <b>Date:</b> {today_str}\n"
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
            "Here are the top 5 highest-rated loot deals of the day:\n\n"
        )
        
        for idx, (p, lp) in enumerate(top_5, 1):
            is_amazon = "amazon" in p.platform.lower()
            badge = "ðŸŠ" if is_amazon else "ðŸ’£"
            clean_title = p.title.split('\n')[0].strip()
            truncated_title = clean_title[:45] + "..." if len(clean_title) > 48 else clean_title
            
            digest_copy += (
                f"<b>{idx}ï¸âƒ£ {badge} {truncated_title}</b>\n"
                f"ðŸ’° <b>Deal Price:</b> <code>â‚¹{lp.price:,}</code> (<s>â‚¹{lp.mrp:,}</s>)\n"
                f"ðŸ“‰ <b>Discount:</b> {lp.discount:.0f}% OFF  ðŸ”¥ <b>Score:</b> <code>{lp.deal_score:.0f}/100</code>\n"
                f"ðŸ‘‰ <b><a href='{p.url}'>GRAB THIS LOOT DEAL</a></b>\n\n"
            )
            
        digest_copy += (
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
            "âš¡ <b>Don't miss a single price drop! Join @LootRaidersDeals!</b>"
        )
        
        # Send digest
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": digest_copy, "parse_mode": "HTML"}
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            logging.info("Daily Loot Digest broadcast sent successfully!")
            settings["last_digest_date"] = today_str
            save_settings(settings)
            
    except Exception as e:
        logging.error(f"Failed to generate daily digest: {e}")
    finally:
        db.close()

def check_and_send_presale_alerts():
    """
    Checks if a mega-sale is going live in the next 5 minutes and broadcasts a checklist (Feature 30).
    """
    now = datetime.now()
    settings = load_settings()
    
    UPCOMING_SALES = [
        {
            "name": "Amazon Great Indian Festival Sale 2026",
            "date_str": "2026-10-15 00:00:00",
            "platform": "amazon",
            "checklist": [
                "1. Make sure your SBI Credit Card is added to your account for the 10% instant discount.",
                "2. Pre-save your delivery addresses to avoid checkout delays.",
                "3. Add your favorite watchlisted items to cart now so they are ready.",
                "4. Keep Loot Raiders channel unmuted! We will post price errors in real-time."
            ]
        },
        {
            "name": "Flipkart Big Billion Days Sale 2026",
            "date_str": "2026-10-15 00:00:00",
            "platform": "flipkart",
            "checklist": [
                "1. Make sure your HDFC Bank cards are saved for the 10% instant discount.",
                "2. Convert your SuperCoins to discount vouchers beforehand.",
                "3. Add products to cart and uncheck unnecessary items.",
                "4. Ensure your Internet connection is stable for flash deals."
            ]
        },
        {
            "name": "Amazon Prime Day Sale 2026",
            "date_str": "2026-07-20 00:00:00",
            "platform": "amazon",
            "checklist": [
                "1. Ensure your Prime membership is active.",
                "2. Keep ICICI Amazon Pay Card ready for unlimited 5% cashback.",
                "3. Keep checking Loot Raiders for lightning deal price drops.",
                "4. Setup 1-Click checkout on the Amazon app."
            ]
        }
    ]
    
    sent_alerts = settings.get("sent_presale_alerts", [])
    
    for sale in UPCOMING_SALES:
        sale_name = sale["name"]
        if sale_name in sent_alerts:
            continue
            
        try:
            sale_time = datetime.strptime(sale["date_str"], "%Y-%m-%d %H:%M:%S")
            time_diff = (sale_time - now).total_seconds()
            
            # Send alert if we are between 0 and 5 minutes before the sale goes live
            if 0 <= time_diff <= 300:
                bot_token = settings.get("telegram_bot_token")
                chat_id = settings.get("telegram_chat_id")
                if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "":
                    continue
                    
                icon = "ðŸŠ" if sale["platform"] == "amazon" else "ðŸ’£"
                checklist_text = "\n".join(sale["checklist"])
                
                alert_text = (
                    f"â°ðŸš¨ <b>[ MEGA SALE ALERT - 5 MINS TO GO ]</b> ðŸš¨â°\n"
                    f"{icon} <b>{sale_name} is starting in 5 minutes!</b> {icon}\n"
                    f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
                    f"Here is your checklist to grab price errors and lightning deals:\n\n"
                    f"{checklist_text}\n"
                    f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
                    f"âš¡ <i>Keep your notifications on Loud! We are scanning at 1-second intervals!</i>"
                )
                
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": alert_text,
                    "parse_mode": "HTML"
                }
                res = requests.post(url, json=payload, timeout=10)
                if res.status_code == 200:
                    logging.info(f"Presale alert broadcasted successfully: {sale_name}")
                    sent_alerts.append(sale_name)
                    settings["sent_presale_alerts"] = sent_alerts
                    save_settings(settings)
                else:
                    logging.warning(f"Failed to send presale alert: {res.text}")
        except Exception as err:
            logging.error(f"Error checking presale alert for {sale_name}: {err}")

def track_channel_growth():
    """
    Retrieves the Telegram channel's current subscriber count and logs it in the database.
    """
    settings = load_settings()
    bot_token = settings.get("telegram_bot_token")
    channel_id = settings.get("telegram_chat_id")
    
    if not bot_token or not channel_id or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "":
        return
        
    # Check last check time from settings to avoid rate limits / spamming
    # We only log once every 4 hours
    last_check = settings.get("last_growth_check_time", 0)
    if time.time() - last_check < 14400: # 4 hours
        return
        
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getChatMemberCount?chat_id={channel_id}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            count = data.get("result", 0)
            if count > 0:
                from database.db_session import SessionLocal
                from knowledge_base.models import ChannelGrowthLog
                db = SessionLocal()
                try:
                    log_entry = ChannelGrowthLog(subscribers=count, timestamp=time.time())
                    db.add(log_entry)
                    db.commit()
                    logging.info(f"Telegram subscriber growth tracked: {count} subscribers.")
                    
                    settings["last_growth_check_time"] = time.time()
                    save_settings(settings)
                except Exception as db_err:
                    logging.error(f"Error saving growth log: {db_err}")
                finally:
                    db.close()
    except Exception as e:
        logging.error(f"Failed to fetch Telegram subscriber count: {e}")

def notifier_worker():
    logging.info("Background Alert Dispatch Worker Activated.")
    while True:
        # Check and send Daily digests
        send_daily_digest_if_time()
        
        # Track Telegram channel growth
        try:
            track_channel_growth()
        except Exception as e:
            logging.error(f"Error tracking channel growth: {e}")
        
        # Check and send Mega-Sale checklist alerts (Feature 30)
        try:
            check_and_send_presale_alerts()
        except Exception as e:
            logging.error(f"Error checking presale alerts: {e}")
            
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
        bank_offers = job.get("bank_offers", [])
        coupon_detail = job.get("coupon_detail", "")
        review_grade = job.get("review_grade", "N/A")
        auto_cart_url = job.get("auto_cart_url")
        retries = job.get("retries", 0)
        
        settings = load_settings()
        bot_token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")
        discord_webhook = settings.get("discord_webhook_url")
        
        has_telegram = (bot_token and chat_id and "YOUR_TELEGRAM" not in bot_token and bot_token.strip() != "")
        has_discord = (discord_webhook and discord_webhook.strip() != "")
        
        smtp_server = settings.get("smtp_server")
        smtp_user = settings.get("smtp_username")
        smtp_pass = settings.get("smtp_password")
        smtp_from = settings.get("smtp_from")
        smtp_to = settings.get("smtp_to")
        has_email = bool(smtp_server and smtp_user and smtp_pass and smtp_from and smtp_to)
        
        telegram_ok = True
        discord_ok = True
        email_ok = True
        
        # A. Dispatch personal direct message alerts first
        try:
            check_and_dispatch_personal_alerts(unique_id, platform, title, price, mrp, discount, img_url, final_url, bank_offers)
        except Exception as alerts_err:
            log_failure(
                component="Personal Alerts Dispatcher",
                context=f"Failed to match and alert personal alert subscribers for deal '{title[:30]}'",
                err=alerts_err,
                severity="WARNING",
                recovery_status="Ignored",
                recommended_action="Check database connection or query integrity."
            )
        
        # B. Dispatch channel updates
        if has_telegram:
            # Enforce compulsory product image rule
            if not img_url or img_url.strip() == "" or "base64" in img_url:
                logging.warning(f"Skipping Telegram channel broadcast for '{title[:30]}' due to missing product image.")
                notification_queue.task_done()
                continue
                
            try:
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
                    unique_id=unique_id,
                    bank_offers=bank_offers,
                    coupon_detail=coupon_detail,
                    review_grade=review_grade,
                    auto_cart_url=auto_cart_url
                )
            except Exception as tg_err:
                log_failure(
                    component="Telegram Channel Notifier",
                    context=f"Failed to broadcast deal '{title[:30]}' to channel {chat_id}",
                    err=tg_err,
                    severity="ERROR",
                    recovery_status="Retrying" if retries < 3 else "Failed",
                    recommended_action="Validate Telegram Bot token and chat ID, or check for Telegram API blockages."
                )
                telegram_ok = False
            
        if has_discord:
            try:
                discord_ok = send_discord_webhook(discord_webhook, title, price, mrp, discount, img_url, final_url, is_verified_low, deal_score)
            except Exception as disc_err:
                log_failure(
                    component="Discord Webhook Notifier",
                    context=f"Failed to dispatch webhook alert for deal '{title[:30]}'",
                    err=disc_err,
                    severity="ERROR",
                    recovery_status="Retrying" if retries < 3 else "Failed",
                    recommended_action="Check validity of the Discord Webhook URL."
                )
                discord_ok = False
            
        # C. Dispatch WhatsApp alerts (Optional, conditional on Twilio settings in .env)
        try:
            send_whatsapp_alert(title, price, mrp, discount, final_url, is_verified_low, deal_score)
        except Exception as wa_err:
            log_failure(
                component="WhatsApp Notifier",
                context=f"Failed to send Twilio alert for deal '{title[:30]}'",
                err=wa_err,
                severity="WARNING",
                recovery_status="Ignored",
                recommended_action="Verify Twilio Account SID, Auth Token, and phone numbers in local environment."
            )
            
        # D. Dispatch Email alerts (Optional, conditional on SMTP settings)
        if has_email:
            try:
                email_ok = send_email_alert(title, price, mrp, discount, img_url, final_url, is_verified_low, deal_score)
            except Exception as mail_err:
                log_failure(
                    component="Email Alert Notifier",
                    context=f"Failed to dispatch deal '{title[:30]}' to recipient list",
                    err=mail_err,
                    severity="ERROR",
                    recovery_status="Retrying" if retries < 3 else "Failed",
                    recommended_action="Check SMTP Server address, port, and credentials in Settings Panel."
                )
                email_ok = False
            
        # Retry with exponential backoff on failure
        if (has_telegram and not telegram_ok) or (has_discord and not discord_ok) or (has_email and not email_ok):
            if retries < 3:
                job["retries"] = retries + 1
                backoff = (2 ** retries) * 5
                logging.warning(f"Notification broadcast failed. Retrying job in {backoff} seconds...")
                threading.Timer(backoff, lambda: notification_queue.put(job)).start()
            else:
                log_failure(
                    component="Broadcaster Queue Scheduler",
                    context=f"Broadcast completely failed after 3 attempts: '{title[:50]}'",
                    err=Exception("Maximum retry limit exceeded"),
                    severity="CRITICAL",
                    recovery_status="Discarded",
                    recommended_action="Examine underlying service outages for Telegram, Discord, or SMTP server."
                )
                
        notification_queue.task_done()
        # Spacer delay to avoid Telegram 429 rate limit
        time.sleep(3.5)

def enqueue_alert(platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, deal_score: float, unique_id: str,
                  bank_offers: list = None, coupon_detail: str = "", review_grade: str = "N/A", auto_cart_url: str = None):
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
        "bank_offers": bank_offers or [],
        "coupon_detail": coupon_detail,
        "review_grade": review_grade,
        "auto_cart_url": auto_cart_url,
        "retries": 0
    }
    notification_queue.put(job)

def start_notifier():
    t = threading.Thread(target=notifier_worker, daemon=True)
    t.start()
