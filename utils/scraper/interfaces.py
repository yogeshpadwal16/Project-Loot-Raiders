from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .models import ScrapedResponse, ScrapedElement

class BaseScraperAdapter(ABC):
    """Abstract interface defining target-neutral scraping capabilities."""
    
    @abstractmethod
    def fetch(self, url: str, mode: str = "fast", **kwargs) -> ScrapedResponse:
        """
        Fetches the target URL content.
        Modes:
          - "fast": High-throughput HTTP client
          - "stealth": Anti-bot bypassing request engine
          - "dynamic": Full browser JS engine
        """
        pass

    @abstractmethod
    def select(self, response: ScrapedResponse, css_selector: str, adaptive: bool = False, auto_save: bool = False, **kwargs) -> Optional[ScrapedElement]:
        """Finds a single matching element in the response."""
        pass

    @abstractmethod
    def select_all(self, response: ScrapedResponse, css_selector: str, **kwargs) -> List[ScrapedElement]:
        """Finds all matching elements in the response."""
        pass
