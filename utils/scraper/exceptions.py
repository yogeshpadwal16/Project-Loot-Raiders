class ScraperError(Exception):
    """Base exception for all scraping operations."""
    pass

class ScraperFetchError(ScraperError):
    """Raised when fetching a page fails due to network, proxy, or anti-bot issues."""
    pass

class ScraperParseError(ScraperError):
    """Raised when parsing or locating elements inside the response fails."""
    pass
