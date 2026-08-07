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
        logging.warning("[REJECTED: NO REAL PRODUCT IMAGE]")
        return False
        
    img_lower = str(image_url).lower()
    banned_keywords = ["brand-logo", "store-logo", "header-logo", "footer-logo", "logo-brand", "logo-store", "amazon-logo", "store_logo", "logo_brand", "logo_store", "amazon.jpg", "placeholder", "default", "banner", "fallback", "avatar", "sprite"]
    is_logo = False
    if any(x in img_lower for x in banned_keywords):
        is_logo = True
    else:
        url_path = img_lower.split('?')[0]
        if url_path.endswith(('/logo.png', '/logo.jpg', '/logo.jpeg', '/logo.gif', '/logo.svg', '/logo.webp')):
            is_logo = True
            
    if is_logo:
        logging.warning("[REJECTED: NO REAL PRODUCT IMAGE]")
        return False

    # Strict check for E-commerce CDNs
    if "amazon" in img_lower:
        if "images/i/" not in img_lower:
            logging.warning("[REJECTED: NO REAL PRODUCT IMAGE]")
            return False
    elif "flipkart" in img_lower:
        if "rukminim" not in img_lower:
            logging.warning("[REJECTED: NO REAL PRODUCT IMAGE]")
            return False
    elif "myntra" in img_lower:
        if "myntassets" not in img_lower:
            logging.warning("[REJECTED: NO REAL PRODUCT IMAGE]")
            return False

    return True

