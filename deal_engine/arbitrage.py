import logging
from typing import Optional
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory
from utils.deduplicator import clean_title_for_fuzzy

logger = logging.getLogger("loot_raiders.arbitrage")

# Minimum similarity score (0-100) to consider two titles as the same product
MATCH_THRESHOLD = 80.0

# Maximum number of recent products to scan for cross-platform matches
SCAN_LIMIT = 500


class ArbitrageRadar:
    """
    Finds the same product listed on competing platforms at a different price.

    Uses RapidFuzz token_sort_ratio for title matching (consistent with the
    deduplicator) and queries the local SQLite product database — no external
    vector DB dependency required.
    """

    def __init__(self):
        try:
            from rapidfuzz import fuzz
            self._fuzz = fuzz
        except ImportError:
            self._fuzz = None

    def find_cross_store_comparisons(
        self,
        product_title: str,
        current_price: int,
        current_platform: str,
    ) -> list[dict]:
        """
        Returns a list of cross-platform price comparisons, sorted cheapest-first.

        Each dict: {"platform": str, "price": int, "product_id": str, "diff": int}
        Only includes products on *rival* platforms (excludes current_platform).
        """
        if not product_title or current_price <= 0:
            return []

        cleaned_title = clean_title_for_fuzzy(product_title)
        if not cleaned_title:
            return []

        current_plat_lower = current_platform.lower()
        comparisons = []
        seen_platforms = set()

        db = SessionLocal()
        try:
            recent = (
                db.query(Product)
                .order_by(Product.created_at.desc())
                .limit(SCAN_LIMIT)
                .all()
            )

            for product in recent:
                plat = (product.platform or "").lower()
                if plat == current_plat_lower or plat in seen_platforms:
                    continue

                candidate_clean = clean_title_for_fuzzy(product.title)
                if not candidate_clean:
                    continue

                score = self._similarity(cleaned_title, candidate_clean)
                if score < MATCH_THRESHOLD:
                    continue

                # Fetch latest price for this match
                latest = (
                    db.query(PriceHistory)
                    .filter_by(product_id=product.id)
                    .order_by(PriceHistory.timestamp.desc())
                    .first()
                )
                if not latest or latest.price <= 0:
                    continue

                seen_platforms.add(plat)
                comparisons.append({
                    "platform": plat,
                    "price": latest.price,
                    "product_id": product.id,
                    "diff": latest.price - current_price,
                })

        except Exception as e:
            logger.error(f"[ARBITRAGE] Cross-store search failed: {e}")
        finally:
            db.close()

        # Sort: cheapest rival first
        comparisons.sort(key=lambda c: c["price"])
        return comparisons

    def format_comparison_text(
        self,
        product_title: str,
        current_price: int,
        current_platform: str,
    ) -> Optional[str]:
        """
        Returns a formatted HTML string for the Telegram caption, or None if
        no cross-platform matches were found.
        """
        comparisons = self.find_cross_store_comparisons(
            product_title, current_price, current_platform
        )
        if not comparisons:
            return None

        lines = []
        has_arbitrage = False

        for comp in comparisons:
            plat_display = comp["platform"].title()
            rival_price = comp["price"]
            diff = comp["diff"]

            if diff > 0:
                # Rival is MORE expensive → user saves money here
                lines.append(
                    f"  • {plat_display}: ₹{rival_price:,} "
                    f"(<b>Save ₹{diff:,} here!</b>)"
                )
                has_arbitrage = True
            elif diff < 0:
                # Rival is cheaper → inform the user
                lines.append(
                    f"  • {plat_display}: ₹{rival_price:,} "
                    f"(₹{abs(diff):,} cheaper)"
                )
            else:
                lines.append(f"  • {plat_display}: ₹{rival_price:,} (same)")

        if not lines:
            return None

        header = "🔀 <b>Arbitrage Alert!</b>" if has_arbitrage else "📊 <b>Multi-Retailer Comparison:</b>"
        return f"\n\n{header}\n" + "\n".join(lines)

    def _similarity(self, a: str, b: str) -> float:
        """Returns similarity score 0-100 using RapidFuzz (fast) or difflib (fallback)."""
        if self._fuzz:
            return self._fuzz.token_sort_ratio(a, b)
        import difflib
        return difflib.SequenceMatcher(None, a, b).ratio() * 100


# Module-level singleton to avoid repeated rapidfuzz import checks
_radar = ArbitrageRadar()


def get_cross_store_comparison(
    product_title: str, current_price: int, current_platform: str
) -> Optional[str]:
    """Convenience wrapper returning formatted HTML comparison text or None."""
    return _radar.format_comparison_text(product_title, current_price, current_platform)
