import re
import logging

logger = logging.getLogger("loot_raiders.bank_offers")

_PCT_RE = re.compile(r"(\d+)\s*%\s*(?:off|discount|instant|cashback)", re.IGNORECASE)
_CAP_RE = re.compile(r"up\s*to\s*₹?\s*([\d,]+)", re.IGNORECASE)
_FLAT_RE = re.compile(r"(?:flat|get)\s*₹?\s*([\d,]+)\s*(?:off|discount|cashback)", re.IGNORECASE)


def calculate_effective_bank_price(deal_price: int, raw_offer_text: str) -> tuple[int, str]:
    """
    Parses bank offer text and calculates effective price under % or flat caps.
    """
    if not raw_offer_text or deal_price <= 0:
        return deal_price, ""

    # Try percentage-based discount first
    pct_match = _PCT_RE.search(raw_offer_text)
    if pct_match:
        pct = int(pct_match.group(1))
        if pct <= 0 or pct > 50:
            return deal_price, raw_offer_text

        calculated_discount = int(deal_price * (pct / 100))

        cap_match = _CAP_RE.search(raw_offer_text)
        if cap_match:
            max_cap = int(cap_match.group(1).replace(",", ""))
            discount = min(calculated_discount, max_cap)
        else:
            discount = calculated_discount

        effective_price = max(1, deal_price - discount)
        offer_summary = f"{pct}% Bank Discount (Save ₹{discount:,})"
        return effective_price, offer_summary

    # Try flat discount
    flat_match = _FLAT_RE.search(raw_offer_text)
    if flat_match:
        flat_off = int(flat_match.group(1).replace(",", ""))
        if flat_off <= 0 or flat_off >= deal_price:
            return deal_price, raw_offer_text

        effective_price = deal_price - flat_off
        offer_summary = f"Flat ₹{flat_off:,} Bank Discount"
        return effective_price, offer_summary

    return deal_price, raw_offer_text


def get_best_bank_effective_price(deal_price: int, bank_offers: list[str]) -> tuple[int, str]:
    """Evaluates multiple bank offers to resolve the lowest effective price."""
    if not bank_offers:
        return deal_price, ""

    best_price = deal_price
    best_summary = ""

    for offer_text in bank_offers:
        eff_price, summary = calculate_effective_bank_price(deal_price, offer_text)
        if eff_price < best_price:
            best_price = eff_price
            best_summary = summary

    return best_price, best_summary
