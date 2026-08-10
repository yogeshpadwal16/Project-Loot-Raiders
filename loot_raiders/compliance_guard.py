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
    STRICT PRE-FLIGHT GUARDRAIL CHECK.
    Rejects anti-bot scraping errors, suspicious default prices (<= ₹1), missing authentic images, and blacklisted domains.
    """
    import logging

    title_clean = (product_title or "").strip()
    title_lower = title_clean.lower()

    # 1. ANTI-BOT & SCRAPING ERROR BLACKLIST
    blacklist_titles = [
        "site maintenance", "recaptcha", "captcha", "cloudflare",
        "just a moment", "access denied", "403 forbidden", "502 bad gateway",
        "amazon.in", "flipkart", "myntra"
    ]
    for b in blacklist_titles:
        if b in title_lower or title_clean.lower() == b:
            logging.warning(f"[GUARDRAIL REJECT: ANTI-BOT/SCRAPING ERROR] Title: '{product_title}' contained '{b}'")
            return False

    if len(title_clean) < 3 or title_clean in ["Product Deal", "Title", "Deal", "Amazon.in"]:
        logging.warning(f"[GUARDRAIL REJECT: INVALID TITLE] [REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)] Title: '{product_title}'")
        return False

    # 2. SUSPICIOUS PRICE FILTER (Price <= ₹1 or None is treated as scraping failure)
    if price is None or price <= 1:
        logging.warning(f"[GUARDRAIL REJECT: SUSPICIOUS PRICE] [REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)] Price: {price} for title '{product_title}'")
        return False

    # 3. AUTHENTIC IMAGE VERIFICATION
    if not image_url or not str(image_url).startswith("http"):
        logging.warning(f"[GUARDRAIL REJECT: MISSING ORIGINAL PRODUCT IMAGE] Title: '{product_title}'")
        return False

    img_lower = str(image_url).lower()
    banned_img_keywords = ["amazon-logo", "store_logo", "logo_brand", "logo_store", "placeholder", "banner", "fallback", "avatar", "sprite", "unsplash"]
    if any(x in img_lower for x in banned_img_keywords):
        logging.warning(f"[GUARDRAIL REJECT: PLACEHOLDER/GENERIC IMAGE] [REJECTED: NO REAL PRODUCT IMAGE] Image URL: {image_url}")
        return False

    # 4. BLACKLISTED DOMAIN CHECK (esakal.com)
    if "esakal.com" in title_lower or "esakal.com" in img_lower:
        logging.warning("[GUARDRAIL REJECT: BLACKLISTED DOMAIN esakal.com DETECTED]")
        return False

    return True
