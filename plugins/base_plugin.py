from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseRetailerPlugin(ABC):
    @property
    @abstractmethod
    def retailer_id(self) -> str:
        """
        Returns the unique platform identifier (e.g., 'amazon_master_lightning_deals').
        """
        pass
        
    @abstractmethod
    def extract_deals(self, driver, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Takes a selenium driver session and configuration options.
        Navigates, scrolls, crawls elements, and returns a list of standardized deal dictionaries.
        
        Returned dict items schema:
          - 'id': str (uniquely generated product ID like ASIN or Flipkart PID)
          - 'title': str
          - 'price': int
          - 'mrp': int
          - 'discount': float
          - 'image_url': str
          - 'url': str
          - 'is_lightning': bool
        """
        pass

    def load_page_with_retries(self, driver, url: str, max_retries: int = 3, delay: float = 3.0) -> bool:
        """
        Loads the specified URL in selenium with automatic retries and backoff.
        """
        import time
        import logging
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"[{self.retailer_id.upper()} Plugin] Loading URL (Attempt {attempt}/{max_retries}): {url}")
                driver.get(url)
                time.sleep(delay)
                return True
            except Exception as e:
                logging.warning(f"[{self.retailer_id.upper()} Plugin] Failed to load page (Attempt {attempt}): {e}")
                if attempt < max_retries:
                    time.sleep(delay * attempt)
        return False
