import logging
import re
import requests
from database import SessionLocal, WishlistItem

logger = logging.getLogger("loot_raiders.wishlist")

MAX_KEYWORDS_PER_USER = 10


def add_keyword_alert(user_id: int, keyword: str, target_price: int) -> str:
    """Saves or updates a keyword tracking alert."""
    keyword = keyword.lower().strip()
    if not keyword or len(keyword) < 2:
        return "❌ Keyword must be at least 2 characters."
    if target_price <= 0:
        return "❌ Target price must be a positive number."

    session = SessionLocal()
    try:
        existing = session.query(WishlistItem).filter_by(
            user_id=user_id, keyword=keyword
        ).first()
        if existing:
            existing.target_price = target_price
            session.commit()
            return f"🔄 Updated <b>{keyword}</b> target price to ₹{target_price:,}."

        count = session.query(WishlistItem).filter_by(user_id=user_id).count()
        if count >= MAX_KEYWORDS_PER_USER:
            return f"❌ Limit reached: {MAX_KEYWORDS_PER_USER} keywords."

        item = WishlistItem(
            user_id=user_id,
            keyword=keyword,
            target_price=target_price,
        )
        session.add(item)
        session.commit()
        return f"✅ Now tracking <b>{keyword}</b> for drops under ₹{target_price:,}!"
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to add keyword alert: {e}")
        return "❌ Failed to set alert."
    finally:
        session.close()


def remove_keyword_alert(user_id: int, keyword: str) -> str:
    """Removes a keyword tracking alert."""
    keyword = keyword.lower().strip()
    session = SessionLocal()
    try:
        item = session.query(WishlistItem).filter_by(
            user_id=user_id, keyword=keyword
        ).first()
        if not item:
            return f"❌ No alert found for <b>{keyword}</b>."
        session.delete(item)
        session.commit()
        return f"🗑️ Stopped tracking <b>{keyword}</b>."
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to remove keyword alert: {e}")
        return "❌ Failed to remove alert."
    finally:
        session.close()


def list_keyword_alerts(user_id: int) -> str:
    """Lists active keyword tracking alerts."""
    session = SessionLocal()
    try:
        items = session.query(WishlistItem).filter_by(user_id=user_id).all()
        if not items:
            return "📭 No active keyword alerts."
        lines = ["📋 <b>Your Keyword Alerts:</b>\n"]
        for i, item in enumerate(items, 1):
            lines.append(f"  {i}. <b>{item.keyword}</b> — under ₹{item.target_price:,}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to list keyword alerts: {e}")
        return "❌ Failed to load alerts."
    finally:
        session.close()


def check_deal_against_keyword_alerts(bot_token: str, deal: dict):
    """
    Checks if a newly scraped deal matches any keyword tracking target
    and dispatches direct message notifications.
    """
    if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "":
        return

    title = deal.get("title", "").lower()
    price = deal.get("price", 0)

    if not title or price <= 0:
        return

    session = SessionLocal()
    try:
        # Load only candidates where target price is high enough
        candidates = session.query(WishlistItem).filter(
            WishlistItem.target_price >= price
        ).all()

        for item in candidates:
            # Word-boundary check
            pattern = r'\b' + re.escape(item.keyword) + r'\b'
            if not re.search(pattern, title):
                continue

            dm_text = (
                f"🎯 <b>Price Alert Triggered!</b>\n\n"
                f"🔑 Keyword: <b>{item.keyword}</b>\n"
                f"📦 Product: <b>{deal.get('title')}</b>\n"
                f"💰 Price: <b>₹{price:,}</b> (Target: Under ₹{item.target_price:,})\n\n"
                f"👉 <a href='{deal.get('url')}'>BUY NOW on {deal.get('platform', '').upper()}</a>"
            )

            try:
                # Dispatch alert DM
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": item.user_id,
                        "text": dm_text,
                        "parse_mode": "HTML"
                    },
                    timeout=8
                )
                logger.info(f"[Wishlist] Dispatched alert to user {item.user_id} for '{item.keyword}'")
            except Exception as send_err:
                logger.error(f"[Wishlist] Failed to send alert: {send_err}")
    except Exception as e:
        logger.error(f"[Wishlist] Match sweep failed: {e}")
    finally:
        session.close()
