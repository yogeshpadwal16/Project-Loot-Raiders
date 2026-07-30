import logging
import re
import requests

logger = logging.getLogger("loot_raiders.engagement")


def extract_tap_to_copy_coupons(coupon_text: str) -> list[str]:
    """
    Parses coupon/promo code details and formats them as HTML code snippets
    for tap-to-copy functionality on Telegram (using <code>code</code> tag).
    """
    if not coupon_text:
        return []

    # Simple regex looking for uppercase alphanumeric codes of length 4-12
    # e.g., "GET50", "DISCOUNT200", "SAVE10"
    codes = re.findall(r'\b[A-Z0-9]{4,12}\b', coupon_text)
    
    # Filter out common false positives
    false_positives = ["HTML", "JSON", "HTTP", "HTTPS", "OFFER", "DEAL", "FREE", "SALE", "SAVE", "UPTO"]
    filtered_codes = [code for code in codes if code not in false_positives]
    
    return list(set(filtered_codes))


def format_booster_comment(coupon_text: str) -> str | None:
    """
    Generates a discussion group booster comment showing tap-to-copy codes.
    """
    codes = extract_tap_to_copy_coupons(coupon_text)
    if not codes:
        return None

    lines = ["🔥 <b>Tap-to-Copy Promo Codes for this Deal:</b>\n"]
    for code in codes:
        lines.append(f"  • Click to Copy: <code>{code}</code>")
    lines.append("\n⚡ <i>Paste this code at checkout to save extra!</i>")
    return "\n".join(lines)


def auto_post_discussion_comment(bot_token: str, reply_to_msg_id: int, chat_id: str, coupon_text: str):
    """Posts tap-to-copy coupon codes as a reply comment in the channel thread."""
    comment = format_booster_comment(coupon_text)
    if not comment or not bot_token or "YOUR_TELEGRAM" in bot_token:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "reply_to_message_id": reply_to_msg_id,
        "text": comment,
        "parse_mode": "HTML"
    }

    try:
        res = requests.post(url, json=payload, timeout=8)
        if res.status_code == 200:
            logger.info(f"[Engagement] Auto-posted copy code comment to post {reply_to_msg_id}")
    except Exception as e:
        logger.error(f"[Engagement] Failed to post coupon comment: {e}")
