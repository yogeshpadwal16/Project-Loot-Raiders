import logging

logger = logging.getLogger("loot_raiders.router")

CHANNEL_MAP = {
    "TECH": "@LootRaidersTech",
    "FASHION": "@LootRaidersFashion",
    "HOME": "@LootRaidersHome",
    "DEFAULT": "@LootRaidersDeals",
}

TECH_KEYWORDS = ["laptop", "phone", "smartphone", "tv", "audio", "earbuds", "ssd", "gpu", "monitor", "microphone", "mic", "headphone"]
FASHION_KEYWORDS = ["shirt", "shoes", "jeans", "dress", "saree", "watch", "sneakers", "tshirt", "kurta", "jacket"]
HOME_KEYWORDS = ["trolley", "storage", "cooker", "bedsheet", "curtain", "furniture", "sofa", "chair", "table", "rack"]


def resolve_target_channel(product_title: str, category: str = "") -> str:
    """Determines target Telegram channel based on product keywords and category."""
    title_lower = (product_title or "").lower()
    category_upper = (category or "").upper()

    if any(kw in title_lower for kw in TECH_KEYWORDS) or category_upper == "ELECTRONICS":
        return CHANNEL_MAP["TECH"]

    if any(kw in title_lower for kw in FASHION_KEYWORDS) or category_upper == "CLOTHING":
        return CHANNEL_MAP["FASHION"]

    if any(kw in title_lower for kw in HOME_KEYWORDS) or category_upper == "HOME":
        return CHANNEL_MAP["HOME"]

    return CHANNEL_MAP["DEFAULT"]


def resolve_target_channel_id(product_title: str, settings: dict, category: str = "") -> str:
    """
    Resolves the target channel ID/handle.
    Falls back to settings["telegram_chat_id"] if resolved to DEFAULT or mapping is not set.
    """
    default_chat = settings.get("telegram_chat_id") or CHANNEL_MAP["DEFAULT"]
    
    if not settings.get("dynamic_routing_enabled", False):
        return default_chat

    resolved = resolve_target_channel(product_title, category)
    if resolved == CHANNEL_MAP["DEFAULT"]:
        return default_chat

    # Return resolved channel handle
    return resolved
