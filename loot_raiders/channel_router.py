import os

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
    """Determines target Telegram channel handle based on keywords or category."""
    title_lower = (product_title or "").lower()
    category_upper = (category or "").upper()

    if any(kw in title_lower for kw in TECH_KEYWORDS) or category_upper == "ELECTRONICS":
        return CHANNEL_MAP["TECH"]

    if any(kw in title_lower for kw in FASHION_KEYWORDS) or category_upper == "CLOTHING":
        return CHANNEL_MAP["FASHION"]

    if any(kw in title_lower for kw in HOME_KEYWORDS) or category_upper == "HOME":
        return CHANNEL_MAP["HOME"]

    return CHANNEL_MAP["DEFAULT"]


def resolve_target_channel_id(product_title: str, default_chat_id: str = None) -> str:
    """
    Resolves target channel handle, falling back to configured environment settings.
    """
    resolved = resolve_target_channel(product_title)
    if resolved == CHANNEL_MAP["DEFAULT"]:
        # Fallback to general environment configurations if general fallback is provided
        return default_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "@LootRaidersDeals")
    return resolved
