# ASCI compliance disclosure injector
# Appends legal indicators like #ad #affiliate to avoid regulatory penalties

DISCLOSURE_TEXT = "⚠️ <b>ASCI Disclosure:</b> <i>As an affiliate, we may earn commissions from qualifying purchases made via our links. #ad #affiliate</i>"


def get_compliance_disclosure() -> str:
    """Returns ASCI mandatory affiliate link disclosure HTML block."""
    return DISCLOSURE_TEXT


def inject_disclosure_to_text(text: str) -> str:
    """Appends compliance footer message to any raw deal caption."""
    return f"{text}\n\n{DISCLOSURE_TEXT}"


def clean_retailer_title_artifacts(title: str) -> str:
    """Strips retailer metadata suffixes like 'Online from Flipkart.com' or 'at Amazon.in'."""
    import re
    if not title:
        return ""
    cleaned = title.strip()
    cleaned = re.sub(r'(?i)\s*(?:online\s+from\s+flipkart\.com|online\s+at\s+flipkart\.com|online\s+at\s+amazon\.in|:\s*amazon\.in|at\s+amazon\.in|from\s+amazon\.in|:\s*flipkart\.com|\s*-\s*flipkart\.com|\s*-\s*amazon\.in)\s*$', '', cleaned)
    return cleaned.strip()


def check_quality_firewall(price, product_title: str, image_url: str = None, is_mirror: bool = False) -> bool:
    """
    STRICT PRE-FLIGHT GUARDRAIL CHECK.
    Rejects anti-bot scraping errors, suspicious default prices (<= ₹1), missing authentic images, and blacklisted domains.
    """
    import logging

    title_clean = (product_title or "").strip()
    title_lower = title_clean.lower()

    # 1. ANTI-BOT & SCRAPING ERROR EXACT TITLES & BOT PHRASES
    exact_bot_titles = [
        "amazon.in", "amazon", "flipkart", "flipkart.com", "myntra", "myntra.com",
        "online shopping site in india", "robot check", "page not found", "access denied",
        "site maintenance", "recaptcha", "captcha", "cloudflare", "just a moment...",
        "just a moment", "403 forbidden", "502 bad gateway", "503 service unavailable",
        "500 internal server error", "attention required! | cloudflare", "challenge validation",
        "product deal", "title", "deal"
    ]
    if title_lower in exact_bot_titles or title_clean in ["Product Deal", "Title", "Deal", "Amazon.in"]:
        logging.warning(f"[GUARDRAIL REJECT: INVALID TITLE] [REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)] Title: '{product_title}'")
        return False

    error_phrases = [
        "site maintenance", "recaptcha", "captcha", "cloudflare",
        "just a moment...", "access denied", "403 forbidden", "502 bad gateway",
        "503 service unavailable", "attention required! | cloudflare", "robot check"
    ]
    for b in error_phrases:
        if b in title_lower:
            logging.warning(f"[GUARDRAIL REJECT: ANTI-BOT/SCRAPING ERROR] Title: '{product_title}' contained '{b}'")
            return False

    if len(title_clean) < 3:
        logging.warning(f"[GUARDRAIL REJECT: INVALID TITLE] [REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)] Title: '{product_title}'")
        return False

    # 2. SUSPICIOUS PRICE FILTER (Price <= ₹1 or None is treated as scraping failure)
    if price is None or price <= 1:
        logging.warning(f"[GUARDRAIL REJECT: SUSPICIOUS PRICE] [REJECTED: INVALID PAYLOAD (Price: 0 / Generic Title)] Price: {price} for title '{product_title}'")
        return False

    # 3. AUTHENTIC IMAGE VERIFICATION
    if not image_url or not str(image_url).startswith("http"):
        if is_mirror:
            # Allow text fallback for mirrored deals
            pass
        else:
            logging.warning(f"[GUARDRAIL REJECT: MISSING ORIGINAL PRODUCT IMAGE] Title: '{product_title}'")
            return False

    if image_url and str(image_url).startswith("http"):
        img_lower = str(image_url).lower()
        banned_img_keywords = ["amazon-logo", "store_logo", "logo_brand", "logo_store", "placeholder", "banner", "fallback", "avatar", "sprite", "unsplash"]
        if any(x in img_lower for x in banned_img_keywords):
            logging.warning(f"[GUARDRAIL REJECT: PLACEHOLDER/GENERIC IMAGE] [REJECTED: NO REAL PRODUCT IMAGE] Image URL: {image_url}")
            return False

    # 4. BLACKLISTED DOMAIN CHECK (esakal.com)
    if "esakal.com" in title_lower or (image_url and "esakal.com" in str(image_url).lower()):
        logging.warning("[GUARDRAIL REJECT: BLACKLISTED DOMAIN esakal.com DETECTED]")
        return False

    return True
