import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("loot_raiders.media_scraper")

DEFAULT_BANNER = "https://lootraiders.com/assets/default_banner.jpg"
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
})


def fetch_opengraph_image(product_url: str, timeout: float = 4.0) -> str:
    """
    Scrapes <meta property="og:image"> or twitter:image with a hard timeout
    to prevent blocking ingestion pipelines.
    """
    if not product_url or not product_url.startswith("http"):
        return DEFAULT_BANNER

    try:
        res = _session.get(product_url, timeout=timeout, allow_redirects=True)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            tag = (
                soup.find("meta", property="og:image")
                or soup.find("meta", attrs={"name": "og:image"})
                or soup.find("meta", attrs={"name": "twitter:image"})
            )
            if tag and tag.get("content"):
                img_url = tag["content"].strip()
                if img_url and not img_url.startswith("data:"):
                    logger.info(f"[OG_SCRAPER] Recovered image URL: {img_url[:80]}")
                    return img_url
    except Exception as e:
        logger.warning(f"[OG_SCRAPER_TIMEOUT] Failed or timed out fetching {product_url}: {e}")

    return DEFAULT_BANNER
