from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass(frozen=True)
class ScrapedElement:
    """Represents a normalized HTML element parsed from the document."""
    tag_name: str
    text: str
    attributes: Dict[str, str] = field(default_factory=dict)
    raw_html: str = ""

@dataclass(frozen=True)
class ScrapedResponse:
    """Normalized response payload returned by any scraper adapter."""
    url: str
    status_code: int
    content: str
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
