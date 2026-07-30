import logging
from database import SessionLocal, Product, PriceHistory

logger = logging.getLogger("loot_raiders.arbitrage")


class ArbitrageRadar:
    """
    Checks competing platforms to detect arbitrage savings.
    Uses ChromaDB for vector-based title lookup when available, and
    falls back to SQLite fuzzy matching.
    """
    def __init__(self, chroma_client=None):
        self.client = chroma_client
        self.collection = None
        if chroma_client:
            try:
                self.collection = chroma_client.get_or_create_collection("product_titles")
            except Exception as e:
                logger.warning(f"Failed to get ChromaDB collection: {e}")

        try:
            from rapidfuzz import fuzz
            self._fuzz = fuzz
        except ImportError:
            self._fuzz = None

    def find_cross_store_comparison(self, product_title: str, current_price: int, current_platform: str) -> str | None:
        """
        Queries ChromaDB or SQLite for the same/similar product on competitor platforms
        to find arbitrage alerts.
        """
        # Try ChromaDB query first
        if self.collection:
            try:
                results = self.collection.query(
                    query_texts=[product_title],
                    n_results=3
                )
                if results and results.get("metadatas") and results["metadatas"][0]:
                    for meta in results["metadatas"][0]:
                        comp_platform = meta.get("platform", "").upper()
                        comp_price = int(meta.get("deal_price", 0))
                        
                        if comp_platform != current_platform.upper() and comp_price > current_price:
                            diff = comp_price - current_price
                            return f"🔀 <b>Arbitrage Alert:</b> Costs ₹{comp_price:,} on {comp_platform.title()} (Save ₹{diff:,} here!)"
            except Exception as e:
                logger.warning(f"ChromaDB search failed: {e}. Falling back to SQLite match.")

        # Fallback to local database search
        db = SessionLocal()
        try:
            # Simple keyword matching using clean list of tokens
            from utils.deduplicator import clean_title_for_fuzzy
            cleaned_title = clean_title_for_fuzzy(product_title) if 'clean_title_for_fuzzy' in globals() else product_title.lower()
            if not cleaned_title:
                return None

            recent_products = db.query(Product).order_by(Product.created_at.desc()).limit(150).all()
            for prod in recent_products:
                if (prod.platform or "").lower() == current_platform.lower():
                    continue

                # Fuzzy string comparison
                similarity = self._similarity(cleaned_title, (prod.title or "").lower())
                if similarity >= 80.0:
                    latest = db.query(PriceHistory).filter_by(product_id=prod.id).order_by(PriceHistory.timestamp.desc()).first()
                    if latest and latest.price > current_price:
                        diff = latest.price - current_price
                        return f"🔀 <b>Arbitrage Alert:</b> Costs ₹{latest.price:,} on {prod.platform.title()} (Save ₹{diff:,} here!)"
        except Exception as e:
            logger.error(f"SQLite fallback arbitrage radar failed: {e}")
        finally:
            db.close()

        return None

    def _similarity(self, a: str, b: str) -> float:
        if self._fuzz:
            return self._fuzz.token_sort_ratio(a, b)
        import difflib
        return difflib.SequenceMatcher(None, a, b).ratio() * 100
