"""
Priority 2 — Product & Deal Classification Engine.
Generates advisory signals for product category, brand confidence, accessory probability,
and deal quality likelihood.
"""

import logging
import re
import time
from typing import Any, Dict

from loot_brain.hf_ai.config import hf_ai_config
from loot_brain.hf_ai.inference.engine import hf_engine
from loot_brain.hf_ai.types import ClassificationResult

logger = logging.getLogger(__name__)

BRAND_DICTIONARY = {
    "samsung": "Samsung", "apple": "Apple", "iphone": "Apple", "macbook": "Apple", "ipad": "Apple",
    "sony": "Sony", "lg": "LG", "asus": "ASUS", "puma": "Puma", "nike": "Nike",
    "jbl": "JBL", "boat": "boAt", "noise": "Noise", "realme": "Realme", "oneplus": "OnePlus",
    "xiaomi": "Xiaomi", "redmi": "Redmi", "hp": "HP", "dell": "Dell", "lenovo": "Lenovo"
}

CATEGORY_MAP = {
    "smartphone": ["phone", "smartphone", "iphone", "galaxy", "android"],
    "laptop": ["laptop", "macbook", "notebook", "chromebook", "vivobook"],
    "audio": ["earbuds", "headphones", "speaker", "earphones", "soundbar", "airpods"],
    "television": ["tv", "television", "led tv", "smart tv", "oled"],
    "footwear": ["shoes", "sneakers", "running shoes", "footwear", "sandals"],
}


class DealClassifier:
    """
    Product & Deal Classifier Engine exporting structured advisory signals.
    """

    def classify_deal(self, title: str, price: float = 0.0, mrp: float = 0.0, platform: str = "Amazon") -> ClassificationResult:
        """
        Classifies product title into category, brand, accessory likelihood, and deal quality score.
        """
        if not title:
            return ClassificationResult()

        def _fallback_classify(**kwargs) -> ClassificationResult:
            return ClassificationResult()

        def _inference_classify(**kwargs) -> ClassificationResult:
            start_time = time.time()
            title_lower = title.lower()

            # 1. Brand Detection
            detected_brand = "unknown"
            brand_conf = 0.0
            for b_key, b_val in BRAND_DICTIONARY.items():
                if re.search(r"\b" + b_key + r"\b", title_lower):
                    detected_brand = b_val
                    brand_conf = 0.95
                    break

            # 2. Category Detection
            detected_cat = "general"
            cat_conf = 0.50
            for cat_key, keywords in CATEGORY_MAP.items():
                if any(re.search(r"\b" + kw + r"\b", title_lower) for kw in keywords):
                    detected_cat = cat_key
                    cat_conf = 0.90
                    break

            # 3. Accessory Detection
            accessory_kws = ["case", "cover", "tempered glass", "screen protector", "pouch", "strap", "holder", "stand"]
            is_acc = any(kw in title_lower for kw in accessory_kws)
            acc_prob = 0.95 if is_acc else 0.05

            # 4. Deal Quality Probability Calculation
            discount = ((mrp - price) / mrp) * 100.0 if mrp > price else 0.0
            quality_prob = min(0.99, max(0.10, (discount / 100.0) * 1.1))

            duration = (time.time() - start_time) * 1000

            return ClassificationResult(
                category=detected_cat,
                category_confidence=cat_conf,
                brand=detected_brand,
                brand_confidence=brand_conf,
                is_accessory=is_acc,
                accessory_probability=acc_prob,
                deal_quality_probability=round(quality_prob, 4),
                latency_ms=round(duration, 2),
            )

        return hf_engine.run_safe_inference(
            task_name="classify_deal",
            inference_func=_inference_classify,
            fallback_func=_fallback_classify,
            kwargs={"title": title, "price": price, "mrp": mrp, "platform": platform},
        )
