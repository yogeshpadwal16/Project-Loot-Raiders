# deal_engine/mirroring/deduplicator.py
from typing import Optional, Tuple
from utils.deduplicator import find_duplicate_deal, clean_title_for_fuzzy

class IntelligentDeduplicator:
    @staticmethod
    def find_duplicate(
        title: str,
        current_price: int,
        time_window_hours: int = 24,
        platform: str = "",
        url: str = "",
        text: str = ""
    ) -> Tuple[bool, Optional[str]]:
        """
        Forwards duplicate detection to the centralized, thread-safe, multi-signal deduplicator.
        """
        return find_duplicate_deal(
            title=title,
            price=current_price,
            platform=platform,
            url=url,
            text=text,
            time_window_hours=time_window_hours
        )
