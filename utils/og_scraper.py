import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("loot_raiders.og_scraper")

DEFAULT_BANNER = "https://lootraiders.com/assets/default_banner.jpg"

# Reuse a persistent session for connection pooling across repeated calls
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
})


def fetch_opengraph_image(product_url: str, timeout: float = 4.0) -> str:
    """
    Scrapes <meta property="og:image"> from a product URL.

    Uses a hard timeout (default 4s) to prevent queue blocking.
    Falls back to DEFAULT_BANNER if no image is found.
    """
    if not product_url or not product_url.startswith("http"):
        return DEFAULT_BANNER

    try:
        response = _session.get(
            product_url,
            timeout=timeout,
            allow_redirects=True,
        )
        if response.status_code != 200:
            logger.warning(
                f"[OG_SCRAPER] HTTP {response.status_code} for {product_url}"
            )
            return DEFAULT_BANNER

        soup = BeautifulSoup(response.text, "html.parser")

        # Try standard og:image, then fallback to twitter:image
        og_tag = (
            soup.find("meta", property="og:image")
            or soup.find("meta", attrs={"name": "og:image"})
            or soup.find("meta", attrs={"name": "twitter:image"})
        )

        if og_tag and og_tag.get("content"):
            image_url = og_tag["content"].strip()
            if image_url and not image_url.startswith("data:"):
                logger.info(f"[OG_SCRAPER] Found image: {image_url[:120]}")
                return image_url

    except requests.Timeout:
        logger.warning(f"[OG_SCRAPER] Timed out ({timeout}s) for {product_url}")
    except Exception as e:
        logger.warning(f"[OG_SCRAPER] Failed fetching {product_url}: {e}")

    return DEFAULT_BANNER
