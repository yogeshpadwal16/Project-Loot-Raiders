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
