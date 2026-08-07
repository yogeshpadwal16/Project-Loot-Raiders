import scrapling
from typing import List, Optional, Dict, Any
from .interfaces import BaseScraperAdapter
from .models import ScrapedResponse, ScrapedElement
from .exceptions import ScraperFetchError, ScraperParseError

class ScraplingScraperAdapter(BaseScraperAdapter):
    """Concrete scraper adapter implementing Scrapling library integrations."""

    def fetch(self, url: str, mode: str = "fast", **kwargs) -> ScrapedResponse:
        try:
            # Map request based on specified fetch tier
            if mode == "fast":
                fetcher = scrapling.Fetcher()
                res = fetcher.get(url, **kwargs)
            elif mode == "stealth":
                fetcher = scrapling.StealthyFetcher()
                res = fetcher.fetch(url, **kwargs)
            elif mode == "dynamic":
                fetcher = scrapling.DynamicFetcher()
                res = fetcher.fetch(url, **kwargs)
            else:
                raise ValueError(f"Unknown scraping execution mode: {mode}")

            # Standardize output responses
            status_code = getattr(res, "status", 200)
            content = getattr(res, "html_content", "") or getattr(res, "text", "") or ""
            headers = getattr(res, "headers", {}) or {}
            cookies = getattr(res, "cookies", {}) or {}

            return ScrapedResponse(
                url=url,
                status_code=status_code,
                content=content,
                headers=dict(headers),
                cookies=dict(cookies)
            )
        except Exception as e:
            raise ScraperFetchError(f"Scrapling failed to fetch URL {url} in mode {mode}: {e}") from e

    def _normalize_element(self, el) -> ScrapedElement:
        try:
            tag_name = getattr(el, "tag", "") or ""
            if hasattr(el, "get_all_text") and callable(el.get_all_text):
                text = el.get_all_text() or ""
            else:
                text = getattr(el, "text", "") or ""
                
            attrib = getattr(el, "attrib", {}) or {}
            raw_html = getattr(el, "html_content", "") or ""
            return ScrapedElement(
                tag_name=tag_name,
                text=text.strip(),
                attributes=dict(attrib),
                raw_html=raw_html
            )
        except Exception as e:
            raise ScraperParseError(f"Element normalization failed: {e}") from e

    def select(self, response: ScrapedResponse, css_selector: str, adaptive: bool = False, auto_save: bool = False, **kwargs) -> Optional[ScrapedElement]:
        try:
            sel = scrapling.Selector(content=response.content, url=response.url, adaptive=adaptive)
            elements = sel.css(css_selector, adaptive=adaptive, auto_save=auto_save, **kwargs)
            if elements:
                return self._normalize_element(elements[0])
            return None
        except Exception as e:
            raise ScraperParseError(f"Failed to locate css selector '{css_selector}': {e}") from e

    def select_all(self, response: ScrapedResponse, css_selector: str, **kwargs) -> List[ScrapedElement]:
        try:
            sel = scrapling.Selector(content=response.content, url=response.url)
            elements = sel.css(css_selector, **kwargs)
            return [self._normalize_element(el) for el in elements]
        except Exception as e:
            raise ScraperParseError(f"Failed to locate all css selectors '{css_selector}': {e}") from e
