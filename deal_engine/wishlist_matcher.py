"""
deal_engine/wishlist_matcher.py
Multi-Item Custom Wishlist & Real-Time Target Price Matcher.
Monitors all incoming scraped and mirrored deals against user wishlist alerts.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from database.db_session import SessionLocal

logger = logging.getLogger("loot_raiders.wishlist_matcher")

# In-memory storage for user wishlists
_USER_WISHLISTS = {}


def add_user_wishlist_target(user_id: str, keyword: str, max_target_price: float, channel: str = "telegram") -> bool:
    """Adds a custom search keyword and max target price alert for a user."""
    if not user_id or not keyword or max_target_price <= 0:
        return False

    if user_id not in _USER_WISHLISTS:
        _USER_WISHLISTS[user_id] = []

    _USER_WISHLISTS[user_id].append({
        "keyword": keyword.strip().lower(),
        "max_price": float(max_target_price),
        "channel": channel
    })
    logger.info(f"Added wishlist target for user {user_id}: '{keyword}' <= ₹{int(max_target_price):,}")
    return True


def get_user_wishlists(user_id: str) -> List[Dict[str, Any]]:
    """Returns all active wishlist alerts for a user."""
    return _USER_WISHLISTS.get(user_id, [])


def match_deal_against_all_wishlists(title: str, current_price: float, buy_url: str) -> List[Dict[str, Any]]:
    """
    Evaluates an incoming deal against all saved user wishlists.
    Returns list of matched users who should receive instant price drop DMs.
    """
    if not title or current_price <= 0:
        return []

    title_lower = title.lower()
    matches = []

    for user_id, alerts in _USER_WISHLISTS.items():
        for alert in alerts:
            kw = alert["keyword"]
            max_p = alert["max_price"]

            # Check if all words in keyword appear in product title
            keywords_matched = all(word in title_lower for word in kw.split())
            if keywords_matched and current_price <= max_p:
                matches.append({
                    "user_id": user_id,
                    "keyword": kw,
                    "target_price": int(max_p),
                    "current_price": int(current_price),
                    "savings_vs_target": int(max_p - current_price),
                    "channel": alert.get("channel", "telegram"),
                    "title": title,
                    "buy_url": buy_url
                })

    return matches
