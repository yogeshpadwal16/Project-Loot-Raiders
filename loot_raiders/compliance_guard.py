# ASCI compliance disclosure injector
# Appends legal indicators like #ad #affiliate to avoid regulatory penalties

DISCLOSURE_TEXT = "⚠️ <b>ASCI Disclosure:</b> <i>As an affiliate, we may earn commissions from qualifying purchases made via our links. #ad #affiliate</i>"


def get_compliance_disclosure() -> str:
    """Returns ASCI mandatory affiliate link disclosure HTML block."""
    return DISCLOSURE_TEXT


def inject_disclosure_to_text(text: str) -> str:
    """Appends compliance footer message to any raw deal caption."""
    return f"{text}\n\n{DISCLOSURE_TEXT}"


def check_quality_firewall(price, product_title: str, image_url: str) -> bool:
    """
    Quality firewall validation check. Drops posts with invalid price, dummy titles, or generic logo images.
    """
    import logging

    # 1. DROP the post instantly if price <= 0 or price is None
    if price is None or price <= 0:
        logging.warning("[REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)]")
        return False

    # 2. DROP the post instantly if product_title is "Product Deal", "Title", "Deal", or under 5 characters
    title_clean = (product_title or "").strip()
    if title_clean in ["Product Deal", "Title", "Deal"] or len(title_clean) < 5:
        logging.warning("[REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)]")
        return False

    # 3. DROP the post instantly if image_url is missing or a generic store logo
    if not image_url:
        logging.warning("[REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)]")
        return False
    img_lower = str(image_url).lower()
    if "amazon-logo" in img_lower or "logo" in img_lower or "default" in img_lower:
        logging.warning("[REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)]")
        return False

    return True

