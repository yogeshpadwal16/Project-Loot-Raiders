import hashlib

TEMPLATE_VARIANTS = ["CARD_BLOCKQUOTE", "COMPACT_LIST"]


def select_ab_template(deal_id) -> tuple[str, str]:
    """
    Selects A/B variant template name and tracking tag deterministically.
    Ensures same product (ASIN/PID) consistently routes to the same layout.
    """
    if isinstance(deal_id, str):
        # Convert string ASIN/PID code into deterministic positive integer
        deal_id = int(hashlib.md5(deal_id.encode()).hexdigest()[:8], 16)

    variant = TEMPLATE_VARIANTS[deal_id % len(TEMPLATE_VARIANTS)]
    tracking_tag = f"ab_variant_{variant.lower()}"
    return variant, tracking_tag
