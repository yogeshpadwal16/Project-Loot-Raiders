"""
utils/bank_offers.py
Multi-Bank Offer Parser & Bottom-Line Effective Price Calculator for Indian E-Commerce.
Calculates instant card discounts (HDFC, SBI, ICICI, Axis, Kotak, OneCard, Amazon Pay, Flipkart Axis).
"""

import re
from typing import List, Dict, Tuple, Optional


# Bank discount rules & regex matchers for Indian banks
BANK_RULES = [
    {
        "bank": "HDFC Bank",
        "keywords": ["hdfc", "hdfc bank", "millennia"],
        "default_pct": 10.0,
        "max_cap": 1500,
        "min_spend": 3000
    },
    {
        "bank": "SBI Card",
        "keywords": ["sbi", "state bank", "simplyclick"],
        "default_pct": 10.0,
        "max_cap": 1500,
        "min_spend": 2500
    },
    {
        "bank": "ICICI Bank",
        "keywords": ["icici", "icici bank", "amazon pay icici"],
        "default_pct": 10.0,
        "max_cap": 1250,
        "min_spend": 2500
    },
    {
        "bank": "Axis Bank",
        "keywords": ["axis", "axis bank", "flipkart axis", "neo"],
        "default_pct": 10.0,
        "max_cap": 1250,
        "min_spend": 2500
    },
    {
        "bank": "Kotak Bank",
        "keywords": ["kotak", "kotak mahindra", "811"],
        "default_pct": 10.0,
        "max_cap": 1000,
        "min_spend": 2000
    },
    {
        "bank": "OneCard",
        "keywords": ["onecard", "one card"],
        "default_pct": 10.0,
        "max_cap": 750,
        "min_spend": 1500
    },
    {
        "bank": "Federal Bank",
        "keywords": ["federal", "federal bank"],
        "default_pct": 10.0,
        "max_cap": 1000,
        "min_spend": 2000
    },
    {
        "bank": "Bank of Baroda",
        "keywords": ["bob", "bank of baroda"],
        "default_pct": 10.0,
        "max_cap": 1000,
        "min_spend": 2000
    }
]


def extract_discount_from_offer_text(offer_text: str, current_price: float) -> Tuple[float, str]:
    """
    Parses flat discount (e.g. 'Flat ₹1,500 off') or percentage discount (e.g. '10% Instant Discount up to ₹1,500').
    Returns (discount_amount, summary_description).
    """
    if not offer_text:
        return 0.0, ""

    text = offer_text.lower()

    # 1. Flat discount match: "flat ₹500 off" or "flat rs 500 off" or "flat 500 off"
    flat_match = re.search(r'flat\s*(?:rs\.?|₹)?\s*([\d,]+)\s*(?:off|discount)', text)
    if flat_match:
        flat_val = float(flat_match.group(1).replace(',', ''))
        return flat_val, f"Flat ₹{flat_val:,.0f} Off"

    # 2. Percentage match: "10% instant discount up to ₹1,500"
    pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:instant\s+discount|off|cashback)', text)
    cap_match = re.search(r'(?:up\s+to|upto|max(?:imum)?)\s*(?:rs\.?|₹)?\s*([\d,]+)', text)

    if pct_match:
        pct = float(pct_match.group(1))
        calculated_discount = (pct / 100.0) * current_price
        
        if cap_match:
            cap_val = float(cap_match.group(1).replace(',', ''))
            final_discount = min(calculated_discount, cap_val)
            return final_discount, f"{pct:.0f}% Off (Up to ₹{cap_val:,.0f})"
        else:
            return calculated_discount, f"{pct:.0f}% Off"

    return 0.0, ""


def get_best_bank_effective_price(current_price: float, raw_offers: List[str]) -> Tuple[int, str]:
    """
    Calculates the lowest effective price achievable through bank offers and credit cards.
    Returns: (effective_price, offer_summary_text)
    """
    if not current_price or current_price <= 0:
        return 0, ""

    best_discount = 0.0
    best_summary = ""

    # Parse scraped raw offer strings
    if raw_offers and isinstance(raw_offers, list):
        for offer in raw_offers:
            if not isinstance(offer, str):
                continue
            disc, desc = extract_discount_from_offer_text(offer, current_price)
            if disc > best_discount:
                best_discount = disc
                # Identify bank name in offer
                matched_bank = ""
                for rule in BANK_RULES:
                    if any(k in offer.lower() for k in rule["keywords"]):
                        matched_bank = rule["bank"]
                        break
                bank_label = f"with {matched_bank} " if matched_bank else ""
                best_summary = f"{bank_label}{desc}".strip()

    # Fallback to co-branded 5% Cashback (Amazon Pay ICICI / Flipkart Axis)
    if best_discount <= 0 and current_price >= 200:
        cashback = current_price * 0.05
        best_discount = cashback
        best_summary = "with Co-branded Card 5% Unlimited Cashback"

    effective_price = max(1, int(current_price - best_discount))
    return effective_price, best_summary


def format_bank_offer_bulletin(current_price: float, raw_offers: List[str]) -> Optional[str]:
    """
    Generates a high-converting HTML bulletin snippet for Telegram / Web deal cards.
    """
    eff_price, summary = get_best_bank_effective_price(current_price, raw_offers)
    if summary and eff_price < current_price:
        savings = int(current_price - eff_price)
        return f"🪙 <b>Effective Price:</b> <code>₹{eff_price:,}</code> ({summary} • Save ₹{savings:,})"
    return None
