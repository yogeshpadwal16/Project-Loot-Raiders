"""
deal_engine/syndication.py
Multi-Platform Deal Syndication Engine.
Dispatches high-scored loot deals to WhatsApp Channels, WhatsApp Business API, and Twitter/X.
"""

import logging
import requests
import json
from typing import Dict, Any, Optional

logger = logging.getLogger("SyndicationEngine")


def broadcast_to_whatsapp_channel(deal: Dict[str, Any], settings: Dict[str, Any]) -> bool:
    """
    Syndicates deal alert to WhatsApp Channel / Broadcast via WhatsApp Cloud API / Webhook.
    """
    token = settings.get("whatsapp_api_token") or settings.get("whatsapp_cloud_token")
    phone_number_id = settings.get("whatsapp_phone_number_id")
    recipient = settings.get("whatsapp_broadcast_target") # Channel ID or broadcast list
    
    # Check if configured
    if not (token and phone_number_id and recipient and "YOUR_" not in str(token)):
        return False

    title = deal.get("title", "Loot Deal")
    price = deal.get("price", 0)
    mrp = deal.get("mrp", price)
    discount = deal.get("discount", 0.0)
    url = deal.get("affiliate_url") or deal.get("final_url") or deal.get("url", "")
    is_loot = deal.get("is_loot", False)

    header_icon = "🚨 *LOOT GLITCH ALERT* 🚨" if is_loot else "🔥 *LOOT DEAL ALERT* 🔥"
    disc_text = f" ({discount:.0f}% OFF)" if discount > 0 else ""
    mrp_text = f" ~₹{mrp:,}~" if mrp > price > 0 else ""

    caption = (
        f"{header_icon}\n\n"
        f"🛍️ *{title[:80]}*\n\n"
        f"💰 *Deal Price:* ₹{price:,}{mrp_text}{disc_text}\n\n"
        f"👉 *Buy Now:* {url}\n\n"
        f"⚡ _Join our Telegram @LootRaidersDeals for 1-second price drops!_"
    )

    endpoint = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    img_url = deal.get("image_url")
    if img_url and str(img_url).startswith("http"):
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "image",
            "image": {
                "link": img_url,
                "caption": caption
            }
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": caption}
        }

    try:
        res = requests.post(endpoint, json=payload, headers=headers, timeout=12)
        if res.status_code in [200, 201, 202]:
            logger.info(f"[WhatsApp Syndication] Dispatched '{title[:30]}' to WhatsApp channel.")
            return True
        else:
            logger.warning(f"[WhatsApp Syndication] Dispatch failed ({res.status_code}): {res.text}")
    except Exception as e:
        logger.error(f"[WhatsApp Syndication] Error dispatching to WhatsApp: {e}")

    return False


def broadcast_to_twitter_x(deal: Dict[str, Any], settings: Dict[str, Any]) -> bool:
    """
    Syndicates deal alert as a rich tweet on Twitter/X via Twitter API v2.
    """
    api_key = settings.get("twitter_api_key")
    api_secret = settings.get("twitter_api_secret")
    access_token = settings.get("twitter_access_token")
    access_token_secret = settings.get("twitter_access_token_secret")
    bearer_token = settings.get("twitter_bearer_token")

    if not (api_key and access_token and "YOUR_" not in str(api_key)):
        return False

    title = deal.get("title", "Loot Deal")
    price = deal.get("price", 0)
    mrp = deal.get("mrp", price)
    discount = deal.get("discount", 0.0)
    url = deal.get("affiliate_url") or deal.get("final_url") or deal.get("url", "")
    is_loot = deal.get("is_loot", False)

    loot_tag = "🚨 #LootDeal #PriceGlitch" if is_loot else "🔥 #Deals #Discounts"
    disc_tag = f"{discount:.0f}% OFF" if discount > 0 else "Deal"

    tweet_text = (
        f"{loot_tag} | {disc_tag}!\n\n"
        f"🛍️ {title[:120]}\n\n"
        f"💵 Deal Price: ₹{price:,} (MRP: ₹{mrp:,})\n\n"
        f"🛒 Grab Deal: {url}\n\n"
        f"#Amazon #Flipkart #LootRaiders #Sale"
    )

    try:
        from requests_oauthlib import OAuth1
        auth = OAuth1(api_key, api_secret, access_token, access_token_secret)
        endpoint = "https://api.twitter.com/2/tweets"
        res = requests.post(endpoint, json={"text": tweet_text}, auth=auth, timeout=15)
        if res.status_code in [200, 201]:
            logger.info(f"[Twitter Syndication] Tweeted '{title[:30]}' successfully.")
            return True
        else:
            logger.warning(f"[Twitter Syndication] Tweet failed ({res.status_code}): {res.text}")
    except Exception as e:
        logger.error(f"[Twitter Syndication] Error tweeting deal: {e}")

    return False


def syndicate_deal_to_all_channels(deal: Dict[str, Any], settings: Dict[str, Any]):
    """
    Executes non-blocking multi-platform syndication across all configured social feeds.
    """
    try:
        broadcast_to_whatsapp_channel(deal, settings)
    except Exception as wa_err:
        logger.error(f"WhatsApp syndication failure: {wa_err}")

    try:
        broadcast_to_twitter_x(deal, settings)
    except Exception as tw_err:
        logger.error(f"Twitter syndication failure: {tw_err}")
