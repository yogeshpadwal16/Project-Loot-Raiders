import re

def build_html_caption(deal: dict, ab_variant: str = "CARD_BLOCKQUOTE", tracking_tag: str = "") -> str:
    """
    Formats the caption according to the Option 1 Clean Telegram caption template.
    """
    title = deal.get("title", "")
    price = deal.get("price", 0)
    mrp = deal.get("mrp", 0)
    platform = deal.get("platform", "GENERIC").upper()

    # Determine store name
    store_name = platform.strip().upper()
    
    # Store emoji mapping
    platform_emojis = {
        "amazon": "🟠", "flipkart": "🔵", "myntra": "💗",
        "ajio": "🟤", "meesho": "🟣", "tatacliq": "🔴", "jiomart": "🟢"
    }
    store_emoji = platform_emojis.get(store_name.lower().split("_")[0], "✨")
    
    # Truncate title to max 120 chars
    clean_title = title.split('\n')[0].strip()
    # Normalize spaces
    clean_title = re.sub(r'\s+', ' ', clean_title)
    if len(clean_title) > 120:
        product_title = clean_title[:117] + "..."
    else:
        product_title = clean_title

    # Price logic calculations
    price_val = int(price) if price else 0
    mrp_val = int(mrp) if mrp else 0
    
    savings = max(0, mrp_val - price_val)
    if mrp_val > 0:
        discount_pct = round(((mrp_val - price_val) / mrp_val) * 100)
    else:
        discount_pct = 0

    caption_lines = []
    caption_lines.append(f"{store_emoji} <b>{store_name} DEAL</b>\n")
    caption_lines.append(f"<b>{product_title}</b>\n")
    caption_lines.append(f" <b>Deal Price:</b> ₹{price_val:,}")
    
    # If MRP is missing or <= price, suppress MRP, Discount, and Savings cleanly
    if mrp_val > price_val:
        caption_lines.append(f" <b>MRP:</b> <s>₹{mrp_val:,}</s>")
        caption_lines.append(f" <b>Discount:</b> {discount_pct}% OFF")
        caption_lines.append(f" <b>You Save:</b> ₹{savings:,}")
        
    caption_lines.append("\n <i>Verified Lowest Price | Limited Stock</i>\n")
    caption_lines.append(" <i>Join @LootRaidersDeals for live price drop alerts!</i>")
    
    caption = "\n".join(caption_lines)
    
    # Ensure total caption is under 850 characters
    if len(caption) > 850:
        caption = caption[:847] + "..."
        
    return caption

def build_inline_buttons(deal: dict) -> list:
    """Formats mock Telegram inline keyboard markup payload."""
    buy_url = deal.get("url", "")
    return [
        [
            {"text": "🛍️ BUY NOW", "url": buy_url}
        ]
    ]
