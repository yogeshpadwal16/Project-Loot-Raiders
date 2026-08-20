import asyncio
from scrapers.stealth_scraper import (
    parse_json_ld_schema,
    scrape_product_details,
    scrape_product_details_sync
)

def extract_json_ld_microdata(html: str) -> dict:
    """Synchronous proxy to json-ld parsing."""
    return parse_json_ld_schema(html)

def scrape_product_live(url: str, timeout: float = 10.0) -> dict:
    """Synchronous proxy to scraper details search."""
    return scrape_product_details_sync(url, timeout_seconds=timeout)

async def scrape_product_live_async(url: str, timeout: float = 10.0) -> dict:
    """Asynchronous proxy to scraper details search."""
    return await scrape_product_details(url, timeout_seconds=timeout)
