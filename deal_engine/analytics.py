"""
deal_engine/analytics.py
Real-time Click Analytics, Telegram Attribution, Anti-Gaming Deduplication, and Deal Heatmap.
Phase 6C Extreme Production-Safe Implementation.
"""

import os
import sys
import time
import hashlib
import logging
import threading
from typing import Dict, Any, List, Optional
from collections import defaultdict

# Database imports
from database.db_session import SessionLocal
from knowledge_base.models import ClickLog, Product, PriceHistory

# Thread-safe in-memory anti-gaming and deduplication store
_LOCK = threading.Lock()
_RECENT_CLICKS: Dict[str, float] = {}  # key: f"{ip_hash}:{product_id}" -> timestamp
_HEATMAP_CACHE: Dict[str, Any] = {
    "data": None,
    "last_computed": 0.0,
    "ttl_seconds": 5.0
}

# Known web crawlers, search spiders, and link preview bots
BOT_USER_AGENT_KEYWORDS = [
    "telegrambot", "twitterbot", "facebookexternalhit", "whatsapp", "discordbot",
    "slackbot", "googlebot", "bingbot", "yandex", "duckduckbot", "baiduspider",
    "ahrefsbot", "semrushbot", "curl", "wget", "python-requests", "python-urllib",
    "scrapling", "playwright", "headlesschrome", "puppeteer", "aiohttp", "httpx"
]

# Salt for privacy-safe IP hashing
_IP_SALT = "loot_raiders_analytics_salt_2026"


def hash_ip(ip: str) -> str:
    """Generates a privacy-preserving one-way hash of an IP address."""
    if not ip or ip == "Unknown":
        return "anonymous_ip"
    return hashlib.sha256(f"{ip}:{_IP_SALT}".encode("utf-8")).hexdigest()[:16]


def is_bot_user_agent(user_agent: Optional[str]) -> bool:
    """Detects whether a request originates from an automated bot, preview generator, or crawler."""
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(keyword in ua_lower for keyword in BOT_USER_AGENT_KEYWORDS)


def is_qualified_click(product_id: str, client_ip: str, user_agent: Optional[str], cooldown_seconds: float = 60.0) -> bool:
    """
    Evaluates whether a click is a genuine, qualified customer click vs a bot or rapid refresh.
    - Rejects known preview bots and scrapers.
    - Deduplicates repeated clicks from the same IP on the same product within cooldown_seconds.
    """
    if not product_id:
        return False

    # 1. Filter known bot user agents
    if is_bot_user_agent(user_agent):
        return False

    now = time.time()
    ip_h = hash_ip(client_ip)
    key = f"{ip_h}:{product_id}"

    with _LOCK:
        # Prune old cache entries if cache size grows large
        if len(_RECENT_CLICKS) > 5000:
            cutoff = now - 3600.0
            expired_keys = [k for k, v in _RECENT_CLICKS.items() if v < cutoff]
            for k in expired_keys:
                del _RECENT_CLICKS[k]

        last_time = _RECENT_CLICKS.get(key, 0.0)
        if now - last_time < cooldown_seconds:
            # Rapid repeated click from same client IP on same product
            return False

        # Register qualified click timestamp
        _RECENT_CLICKS[key] = now
        return True


def record_deal_click(
    product_id: str,
    title: str,
    client_ip: str,
    user_agent: Optional[str],
    cta: str = "buy",
    src: str = "telegram"
) -> bool:
    """
    Records a click event non-blockingly and determines qualification status.
    Returns True if successfully recorded to SQLite, False on error.
    Guaranteed never to raise unhandled exceptions.
    """
    try:
        now = time.time()
        qualified = is_qualified_click(product_id, client_ip, user_agent)
        
        # User field format: "src:cta" or "src:cta:bot"
        user_tag = f"{src}:{cta}"
        if not qualified:
            user_tag += ":duplicate" if not is_bot_user_agent(user_agent) else ":bot"

        db = SessionLocal()
        try:
            click = ClickLog(
                product_id=product_id,
                title=title or "Deal",
                ip=client_ip,
                user=user_tag,
                user_agent=user_agent or "Unknown",
                timestamp=now
            )
            db.add(click)
            db.commit()
            return True
        finally:
            db.close()
    except Exception as e:
        logging.error(f"[Analytics] Error recording deal click for '{product_id}': {e}")
        return False


def get_deal_heatmap_analytics(lookback_hours: int = 24) -> Dict[str, Any]:
    """
    Computes real-time deal heatmap, retailer click share, and CTA distribution.
    Uses in-memory caching with 5s TTL to prevent database lock contention.
    Never exposes raw customer IP addresses.
    """
    global _HEATMAP_CACHE
    now = time.time()

    # Fast in-memory cache return
    if _HEATMAP_CACHE["data"] is not None and (now - _HEATMAP_CACHE["last_computed"] < _HEATMAP_CACHE["ttl_seconds"]):
        return _HEATMAP_CACHE["data"]

    cutoff = now - (lookback_hours * 3600)
    v_cutoff_15m = now - 900  # 15 minutes velocity

    db = SessionLocal()
    try:
        # Fetch click logs in lookback window
        clicks = db.query(ClickLog).filter(ClickLog.timestamp >= cutoff).all()
        
        total_raw_clicks = len(clicks)
        total_qualified_clicks = 0
        bot_clicks_filtered = 0
        velocity_15m = 0

        clicks_by_retailer: Dict[str, int] = defaultdict(int)
        clicks_by_cta: Dict[str, int] = defaultdict(int)
        clicks_by_hour: Dict[str, int] = defaultdict(int)
        prod_clicks: Dict[str, Dict[str, int]] = defaultdict(lambda: {"raw": 0, "qualified": 0, "velocity_15m": 0})

        for c in clicks:
            # Check qualification from user tag
            tag = (c.user or "").lower()
            is_bot = ":bot" in tag
            is_dup = ":duplicate" in tag
            is_qual = not (is_bot or is_dup)

            if is_bot:
                bot_clicks_filtered += 1
            if is_qual:
                total_qualified_clicks += 1

            if c.timestamp >= v_cutoff_15m and is_qual:
                velocity_15m += 1

            # Parse CTA and Source
            clean_tag = tag.replace(":bot", "").replace(":duplicate", "")
            parts = clean_tag.split(":")
            cta_name = parts[1] if len(parts) > 1 else "buy"
            clicks_by_cta[cta_name] += 1

            # Parse Hour
            hr_str = time.strftime("%Y-%m-%d %H:00", time.localtime(c.timestamp))
            clicks_by_hour[hr_str] += 1

            # Product level stats
            pid = c.product_id
            if pid:
                prod_clicks[pid]["raw"] += 1
                if is_qual:
                    prod_clicks[pid]["qualified"] += 1
                if c.timestamp >= v_cutoff_15m and is_qual:
                    prod_clicks[pid]["velocity_15m"] += 1

        # Fetch product metadata in batch for top products
        top_pids = sorted(prod_clicks.keys(), key=lambda k: prod_clicks[k]["qualified"], reverse=True)[:10]
        prod_models = {p.id: p for p in db.query(Product).filter(Product.id.in_(top_pids)).all()} if top_pids else {}

        top_deals = []
        for pid in top_pids:
            p_obj = prod_models.get(pid)
            stats = prod_clicks[pid]
            plat = p_obj.platform if p_obj else "unknown"
            clicks_by_retailer[plat] += stats["raw"]

            # Calculate heat score (0 to 100)
            heat = min(100.0, (stats["qualified"] * 2.5) + (stats["velocity_15m"] * 8.0))

            top_deals.append({
                "product_id": pid,
                "title": (p_obj.title[:55] + "...") if p_obj and p_obj.title else "Deal",
                "platform": plat,
                "raw_clicks": stats["raw"],
                "qualified_clicks": stats["qualified"],
                "recent_velocity": stats["velocity_15m"],
                "heat_score": round(heat, 1)
            })

        # Calculate Amazon vs Flipkart percentage
        amz_clicks = sum(clicks_by_retailer[k] for k in clicks_by_retailer if "amazon" in k.lower())
        fk_clicks = sum(clicks_by_retailer[k] for k in clicks_by_retailer if "flipkart" in k.lower())
        tot_amz_fk = max(1, amz_clicks + fk_clicks)

        heatmap_payload = {
            "status": "success",
            "lookback_hours": lookback_hours,
            "total_raw_clicks": total_raw_clicks,
            "total_qualified_clicks": total_qualified_clicks,
            "bot_clicks_filtered": bot_clicks_filtered,
            "recent_click_velocity_15m": velocity_15m,
            "clicks_by_cta": dict(clicks_by_cta),
            "clicks_by_retailer": dict(clicks_by_retailer),
            "top_deals_heatmap": top_deals,
            "amazon_vs_flipkart_distribution": {
                "amazon_pct": round((amz_clicks / tot_amz_fk) * 100, 1),
                "flipkart_pct": round((fk_clicks / tot_amz_fk) * 100, 1)
            },
            "timestamp": now
        }

        _HEATMAP_CACHE["data"] = heatmap_payload
        _HEATMAP_CACHE["last_computed"] = now
        return heatmap_payload
    except Exception as err:
        logging.error(f"[Analytics] Heatmap calculation error: {err}")
        return {
            "status": "error",
            "message": str(err),
            "total_raw_clicks": 0,
            "total_qualified_clicks": 0,
            "top_deals_heatmap": []
        }
    finally:
        db.close()
