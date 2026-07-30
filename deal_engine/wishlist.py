import logging
import re
import requests
from database.db_session import SessionLocal
from knowledge_base.models import WishlistItem

logger = logging.getLogger("loot_raiders.wishlist")

MAX_KEYWORDS_PER_USER = 10


def add_keyword_alert(user_id: int, keyword: str, target_price: int) -> str:
    """
    Adds a keyword-based price alert for a user.
    If the keyword already exists, updates its target price.
    Returns a user-facing HTML response string.
    """
    keyword = keyword.lower().strip()
    if not keyword or len(keyword) < 2:
        return "❌ Keyword must be at least 2 characters."
    if target_price <= 0:
        return "❌ Target price must be a positive number."

    session = SessionLocal()
    try:
        # Duplicate guard: update existing entry instead of creating a new one
        existing = session.query(WishlistItem).filter_by(
            user_id=user_id, keyword=keyword
        ).first()
        if existing:
            existing.target_price = target_price
            session.commit()
            return f"🔄 Updated <b>{keyword}</b> target to ₹{target_price:,}."

        # Per-user limit
        count = session.query(WishlistItem).filter_by(user_id=user_id).count()
        if count >= MAX_KEYWORDS_PER_USER:
            return (
                f"❌ You've hit the limit of {MAX_KEYWORDS_PER_USER} keyword alerts.\n"
                f"Remove one with /kwremove first."
            )

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
        return "❌ Failed to set alert. Please try again."
    finally:
        session.close()


def remove_keyword_alert(user_id: int, keyword: str) -> str:
    """Removes a keyword alert. Returns a user-facing HTML response string."""
    keyword = keyword.lower().strip()
    if not keyword:
        return "❌ Please specify a keyword to remove.\nUsage: /kwremove <keyword>"

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
        return "❌ Failed to remove alert. Please try again."
    finally:
        session.close()


def list_keyword_alerts(user_id: int) -> str:
    """Lists all keyword alerts for a user. Returns a user-facing HTML response string."""
    session = SessionLocal()
    try:
        items = session.query(WishlistItem).filter_by(user_id=user_id).all()
        if not items:
            return (
                "📭 You have no keyword alerts set.\n\n"
                "Use /kwtrack <b>&lt;keyword&gt;</b> <b>&lt;max_price&gt;</b> to add one!\n"
                "Example: <code>/kwtrack iphone 15 45000</code>"
            )

        lines = ["📋 <b>Your Keyword Alerts:</b>\n"]
        for i, item in enumerate(items, 1):
            lines.append(f"  {i}. <b>{item.keyword}</b> — under ₹{item.target_price:,}")
        lines.append(f"\n📊 {len(items)}/{MAX_KEYWORDS_PER_USER} slots used")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to list keyword alerts: {e}")
        return "❌ Failed to load your alerts."
    finally:
        session.close()


def check_deal_against_keyword_alerts(bot_token: str, deal: dict):
    """
    Matches incoming deals against user keyword wishlists and dispatches DMs.

    Uses word-boundary matching to prevent partial hits
    (e.g. 'phone' won't match 'earphone' or 'microphone').
    Filters at the DB level by target_price >= deal price to minimise rows loaded.
    """
    if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "":
        return

    title = deal.get("title", "")
    title_lower = title.lower()
    price = deal.get("price", 0)

    if not title_lower or price <= 0:
        return

    session = SessionLocal()
    try:
        # DB-level filter: only fetch rows where the target price is at or above the deal price
        candidates = session.query(WishlistItem).filter(
            WishlistItem.target_price >= price
        ).all()

        for item in candidates:
            # Word-boundary regex avoids partial keyword matches
            pattern = r'\b' + re.escape(item.keyword) + r'\b'
            if not re.search(pattern, title_lower):
                continue

            dm_text = (
                f"🎯 <b>Keyword Alert Match!</b>\n\n"
                f"🔑 Keyword: <b>{item.keyword}</b>\n"
                f"📦 Product: <b>{title[:80]}</b>\n\n"
                f"💰 Price: <b>₹{price:,}</b> (Target: under ₹{item.target_price:,})\n"
                f"📉 Discount: <b>{deal.get('discount', 0):.0f}% OFF</b>\n\n"
                f"👉 <a href='{deal.get('url', '')}'>GRAB THIS DEAL NOW</a>"
            )
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": item.user_id,
                        "text": dm_text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": False,
                    },
                    timeout=10,
                )
                logger.info(
                    f"[WISHLIST] Keyword alert sent to user {item.user_id} "
                    f"for '{item.keyword}' (deal: ₹{price:,})"
                )
            except Exception as send_err:
                logger.error(
                    f"[WISHLIST] Failed DM to user {item.user_id}: {send_err}"
                )
    except Exception as e:
        logger.error(f"[WISHLIST] Deal matching error: {e}")
    finally:
        session.close()
