def build_html_caption(deal: dict, ab_variant: str = "CARD_BLOCKQUOTE", tracking_tag: str = "") -> str:
    """
    Renders a premium HTML caption for Telegram deal broadcasts based on the A/B testing layout.
    """
    title = deal.get("title", "")
    price = deal.get("price", 0)
    mrp = deal.get("mrp", price)
    discount = deal.get("discount", 0.0)
    url = deal.get("url", "")
    platform = deal.get("platform", "GENERIC").upper()
    is_verified_low = deal.get("is_verified_low", False)
    deal_score = deal.get("deal_score", 50.0)
    bank_summary = deal.get("bank_summary", "")
    eff_price = deal.get("effective_price", price)

    savings = mrp - price
    truncated_title = title.split('\n')[0].strip()
    if len(truncated_title) > 90:
        truncated_title = truncated_title[:87] + "..."

    # Inject compliance guard disclosure (Part of compliance rules)
    from compliance_guard import get_compliance_disclosure
    disclosure = get_compliance_disclosure()

    # Track conversions with URL fragments
    cta_url = f"{url}#{tracking_tag}" if tracking_tag else url

    if ab_variant == "CARD_BLOCKQUOTE":
        card = []
        card.append(f"🛍️ <b>{truncated_title}</b>")
        card.append("")
        if is_verified_low:
            card.append("🔥 <b>[ VERIFIED ALL-TIME LOW PRICE ]</b>")
        card.append(f"💵 <b>Loot Price:</b>  <code>₹{price:,}</code>")
        card.append(f"❌ <b>Original MRP:</b> <s>₹{mrp:,}</s>")
        card.append(f"📉 <b>Discount:</b>     <b>{discount:.0f}% OFF</b>")
        card.append(f"💰 <b>You Save:</b>     <code>₹{savings:,}</code>")
        
        if bank_summary and eff_price < price:
            card.append(f"💳 <b>Bank Benefit:</b> <code>₹{eff_price:,}</code> ({bank_summary})")

        card_content = "\n".join(card)
        caption = (
            f"🚨 <b>{platform} LOOT ALERT</b> 🚨\n\n"
            f"<blockquote>{card_content}</blockquote>\n\n"
            f"💎 <b>Loot Score:</b> {deal_score}/100\n"
            f"⚡ <i>Price error / glitch risk is active. Grab quick!</i>\n\n"
            f"<a href='{cta_url}'>🛒 GRAB THIS DEAL NOW</a>\n\n"
            f"{disclosure}\n"
            f"#{tracking_tag}"
        )
    else:  # COMPACT_LIST
        meta = []
        if is_verified_low:
            meta.append("🔥 Verified Low")
        meta.append(f"Score: {deal_score:.0f}")

        offers = []
        if bank_summary and eff_price < price:
            offers.append(f"💳 Bank: ₹{eff_price:,} ({bank_summary})")

        caption = (
            f"💥 <b>{platform} DROP:</b> {truncated_title}\n"
            f"💵 <b>Loot: ₹{price:,}</b> (<s>₹{mrp:,}</s>) | 📉 <b>{discount:.0f}% OFF</b>\n"
            f"📊 {' | '.join(meta)}\n\n"
            f"{f'{chr(10)}'.join(offers) + f'{chr(10)}' if offers else ''}"
            f"🛒 <a href='{cta_url}'>BUY NOW BEFORE IT'S GONE</a>\n\n"
            f"{disclosure}\n"
            f"#{tracking_tag}"
        )

    return caption


def build_inline_buttons(deal: dict) -> list:
    """Formats mock Telegram inline keyboard markup payload."""
    buy_url = deal.get("url", "")
    return [
        [
            {"text": "🛍️ BUY NOW", "url": buy_url}
        ]
    ]
