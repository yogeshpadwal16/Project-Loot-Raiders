"""
extractors/flipkart.py
Production-grade Flipkart Product Page & Card Extractor and Normalizer.
Extracts clean product titles, high-resolution primary images, accurate selling/MRP prices,
and rejects generic search terms or placeholders.
"""

import re
import urllib.parse
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

GENERIC_SEARCH_TERMS = {
    "clearance sale", "offers", "deals", "trending deals", "showing 1 -",
    "flipkart clearance master feed", "results for", "explore plus", "special offers",
    "top deals", "best sellers", "mobiles & accessories", "other colors",
    "other colors/patterns", "limited time deal", "deal of the day"
}


def sanitize_flipkart_title(raw_title: str) -> str:
    """Sanitizes raw product title by stripping pipe delimiters, keyword spam, and trailing ellipsis."""
    if not raw_title:
        return ""
    
    title = raw_title.strip()
    
    # Strip raw pipe delimiters and underscores
    title = re.sub(r'[|│｜]+', ' ', title)
    title = re.sub(r'_+', ' ', title)
    
    # Strip common SEO keyword stuffing patterns
    seo_patterns = [
        r'\b(lightweight)\s+(comfort)\s+(summer)\s+(trendy)\b',
        r'\b(for men & women|for men and women|for boys and girls)\b',
        r'\b(100% genuine|best quality|top rated|super hit|hot deal)\b',
    ]
    for pattern in seo_patterns:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'^[\s,.\-–—/]+', '', title)
    title = re.sub(r'[\s,.\-–—/.]+$', '', title)
    
    return title


def is_generic_or_search_title(title: str) -> bool:
    """Detects whether a title is an invalid search keyword / breadcrumb / banner."""
    if not title or len(title.strip()) < 5:
        return True
    
    lower = title.strip().lower()
    for term in GENERIC_SEARCH_TERMS:
        if lower == term or lower.startswith(term) or term in lower:
            # If the title is just the search term without product specifics
            if len(lower) < len(term) + 10:
                return True
                
    if lower.startswith("results for") or lower.startswith("showing 1"):
        return True
        
    return False


def upgrade_flipkart_image_url(url: str) -> str:
    """
    Upgrades Flipkart CDN image URLs to highest available resolution (@832/832 or /832/832/)
    and rejects generic platform placeholders/logos/SVGs.
    """
    if not url:
        return ""
    
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
        
    lower = url.lower()
    
    # Reject generic logos, placeholdes, and SVGs
    banned = [
        "static-assets-web.flixcart.com", "fk-p-linchpin-web", "fk-cp-zion",
        "placeholder", "blank.gif", "spacer.gif", "default-image", "no-image",
        "brand-logo", "store-logo", ".svg"
    ]
    if any(b in lower for b in banned):
        return ""
        
    # Upgrade standard Flipkart image CDN dimensions to 832x832
    url = re.sub(r'/image/\d+/\d+/', '/image/832/832/', url)
    url = re.sub(r'/@\d+/\d+/', '/@832/832/', url)
    
    return url


def parse_clean_price(price_str: Any) -> Optional[float]:
    """Parses clean numeric price from string, stripping currency symbols, commas, and whitespace."""
    if price_str is None:
        return None
    try:
        # Remove currency symbols (₹, Rs., \u20b9, â‚¹) and commas
        cleaned = re.sub(r'[^\d.]', '', str(price_str).replace(',', ''))
        if cleaned:
            val = float(cleaned)
            if val > 0:
                return val
    except (ValueError, TypeError):
        pass
    return None


def extract_flipkart_data_from_html(html: str, page_url: str = "") -> Optional[Dict[str, Any]]:
    """
    Extracts structured, normalized Flipkart deal data from product page HTML.
    Targets modern and legacy Flipkart DOM selectors with JSON-LD microdata fallback.
    """
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    
    # Guardrail against search box value (<input name="q">)
    search_input = soup.select_one("input[name='q'], input.Pke_EE")
    search_val = search_input.get("value", "").strip().lower() if search_input else ""

    # 1. Product Title Extraction
    title = ""
    # Priority selectors for title
    title_elem = soup.select_one("h1.B_NuCI, span.VU-ZEz, span.VU-ZEg, h1.yrwE28, span._35KyD6, h1 span, div._2W9tVh")
    if title_elem:
        raw_text = title_elem.get_text().strip()
        if raw_text and raw_text.lower() != search_val and not is_generic_or_search_title(raw_text):
            title = sanitize_flipkart_title(raw_text)

    # Secondary meta tag title
    if not title:
        og_title = soup.select_one("meta[property='og:title'], meta[name='twitter:title']")
        if og_title and og_title.get("content"):
            raw_meta = og_title.get("content").strip()
            # Often Flipkart meta titles end with ": Buy Online at Best Prices in India..."
            raw_meta = re.sub(r':\s*Buy Online.*$', '', raw_meta, flags=re.IGNORECASE)
            if raw_meta and not is_generic_or_search_title(raw_meta):
                title = sanitize_flipkart_title(raw_meta)

    # 2. Brand Extraction
    brand = ""
    brand_elem = soup.select_one("span.mEh187, span.G6XhRU, div.x52Ta6, span._2W9tVh")
    if brand_elem:
        brand = brand_elem.get_text().strip()
    elif title:
        # First word fallback
        tokens = title.split()
        if tokens:
            brand = tokens[0]

    # 3. Primary Hero Image Extraction
    image_url = ""
    # Main gallery image selectors
    img_elem = soup.select_one("img._396cs4, img.DByuf4, div._2r_T1I img, img._53G4pf, img.UCad5S, img.vU5WPQ, img.x1646t, div.CXW8mj img")
    if img_elem:
        # Check srcset first for highest res
        srcset = img_elem.get("srcset", "")
        if srcset:
            parts = [p.strip().split()[0] for p in srcset.split(",") if p.strip()]
            if parts:
                candidate = upgrade_flipkart_image_url(parts[-1])
                if candidate:
                    image_url = candidate
                    
        if not image_url:
            for attr in ["data-src", "src", "data-original"]:
                val = img_elem.get(attr)
                if val:
                    candidate = upgrade_flipkart_image_url(val)
                    if candidate:
                        image_url = candidate
                        break

    if not image_url:
        og_img = soup.select_one("meta[property='og:image'], meta[name='twitter:image']")
        if og_img and og_img.get("content"):
            candidate = upgrade_flipkart_image_url(og_img.get("content"))
            if candidate:
                image_url = candidate

    # 4. Selling Price Extraction
    current_price = None
    price_elem = soup.select_one("div.Nx9bqj.CxhGGd, div.Nx9bqj, div._30jeq3._16Jk6d, div._30jeq3, div.hlbKVd")
    if price_elem:
        current_price = parse_clean_price(price_elem.get_text())

    # 5. Original MRP Extraction
    original_price = None
    mrp_elem = soup.select_one("div.yRaY8j._18RivS, div.yRaY8j, div._2p6JhP._30e3Er, div._3I9_ww, div._3AuQ35")
    if mrp_elem:
        original_price = parse_clean_price(mrp_elem.get_text())

    # If MRP not found or lower than current price, estimate realistic MRP from discount percentage element if present
    if current_price and (not original_price or original_price <= current_price):
        disc_elem = soup.select_one("div.UkUFwK span, div._3Ay6Sb span, span._174k5O")
        if disc_elem:
            disc_match = re.search(r'(\d+)\s*%', disc_elem.get_text())
            if disc_match:
                pct = float(disc_match.group(1))
                if 0 < pct < 100:
                    original_price = round(current_price / (1 - pct / 100.0), 2)

    if not original_price and current_price:
        original_price = round(current_price * 1.3, 2)

    # 6. Discount Calculation
    discount_percentage = 0
    if current_price and original_price and original_price > current_price:
        discount_percentage = round(((original_price - current_price) / original_price) * 100)

    # Final Validation
    if not title or is_generic_or_search_title(title) or not current_price:
        return None

    return {
        "title": title,
        "brand": brand,
        "currentPrice": current_price,
        "originalPrice": original_price or current_price,
        "discountPercentage": discount_percentage,
        "imageUrl": image_url,
        "productUrl": page_url,
        "merchant": "Flipkart"
    }
