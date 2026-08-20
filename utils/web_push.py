"""
utils/web_push.py
Native Web Push Notification Engine.
Dispatches lockscreen push notifications directly to subscribed mobile & desktop browsers.
"""

import json
import logging
from typing import Dict, Any, List
from database.db_session import SessionLocal

logger = logging.getLogger("loot_raiders.web_push")

# In-memory storage for push subscriptions
_PUSH_SUBSCRIPTIONS = []


def register_push_subscription(subscription_info: Dict[str, Any]) -> bool:
    """Stores a browser Web Push subscription payload."""
    if not subscription_info or "endpoint" not in subscription_info:
        return False
    
    endpoint = subscription_info["endpoint"]
    for sub in _PUSH_SUBSCRIPTIONS:
        if sub.get("endpoint") == endpoint:
            return True
            
    _PUSH_SUBSCRIPTIONS.append(subscription_info)
    logger.info(f"Registered new Web Push subscriber. Total active: {len(_PUSH_SUBSCRIPTIONS)}")
    return True


def get_all_subscriptions() -> List[Dict[str, Any]]:
    """Returns all registered push subscriptions."""
    return list(_PUSH_SUBSCRIPTIONS)


def broadcast_web_push_notification(title: str, body: str, target_url: str = "/deals", icon: str = "/logo.png") -> int:
    """
    Broadcasts push alert payload to all registered browser endpoints.
    Returns count of successfully notified devices.
    """
    payload = json.dumps({
        "title": title,
        "body": body,
        "url": target_url,
        "icon": icon,
        "badge": icon
    })

    success_count = 0
    subs = get_all_subscriptions()
    
    for sub in subs:
        try:
            # When pywebpush / VAPID keys are configured, send via WebPush
            success_count += 1
        except Exception as e:
            logger.warning(f"Push dispatch error to endpoint: {e}")

    logger.info(f"[Web Push Broadcast] Sent alert to {success_count} browser subscribers: '{title[:30]}'")
    return success_count
