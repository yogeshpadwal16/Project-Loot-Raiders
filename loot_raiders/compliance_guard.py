# ASCI compliance disclosure injector
# Appends legal indicators like #ad #affiliate to avoid regulatory penalties

DISCLOSURE_TEXT = "⚠️ <b>ASCI Disclosure:</b> <i>As an affiliate, we may earn commissions from qualifying purchases made via our links. #ad #affiliate</i>"


def get_compliance_disclosure() -> str:
    """Returns ASCI mandatory affiliate link disclosure HTML block."""
    return DISCLOSURE_TEXT


def inject_disclosure_to_text(text: str) -> str:
    """Appends compliance footer message to any raw deal caption."""
    return f"{text}\n\n{DISCLOSURE_TEXT}"


def check_quality_firewall(price, product_title: str, image_url: str = None, is_mirror: bool = False) -> bool:
    """
    Quality firewall validation check.
    Guarantees that invalid prices or empty payloads are caught.
    For mirrored competitor deals, bypasses strict CDN restrictions so 100% of competitor deals pass.
    Allows deals missing raw CDN images to proceed because PIL image generator will build a product deal card image.
    """
    import logging

    # 1. DROP the post if price <= 0 or price is None
    if price is None or price <= 0:
        logging.warning("[REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)]")
        return False

    # 2. DROP the post if product_title is completely missing or generic default
    title_clean = (product_title or "").strip()
    if title_clean in ["Product Deal", "Title", "Deal"] or len(title_clean) < 3:
        logging.warning("[REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)]")
        return False

    # If it's a mirrored deal, approve it immediately (as long as price > 0 and title is valid)
    if is_mirror:
        return True

    # 3. Check for obvious non-image placeholder/logo keywords if image_url is provided
    if image_url:
        img_lower = str(image_url).lower()
        banned_keywords = ["amazon-logo", "store_logo", "logo_brand", "logo_store", "placeholder", "banner", "fallback", "avatar", "sprite"]
        if any(x in img_lower for x in banned_keywords):
            logging.warning("[REJECTED: NO REAL PRODUCT IMAGE]")
            return False

    # If image_url is missing, return True so notifier.py generates a PIL deal card image!
    return True
