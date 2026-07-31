import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("loot_raiders.media_scraper")

class MediaScraper:
    def __init__(self, timeout_seconds: float = 4.0):
        self.timeout = timeout_seconds
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

    async def scrape_opengraph_data(self, url: str) -> dict:
        """
        Scrapes the target URL to extract OpenGraph metadata (image, title, description).
        Enforces a strict 4.0 second timeout limit to prevent blocking.
        """
        result = {
            "image_url": None,
            "title": None,
            "description": None,
            "success": False
        }
        
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return result

        logger.info(f"Scraping OG metadata for URL: {url} (Timeout: {self.timeout}s)")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                resp = await client.get(url)
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    
                    # 1. Extract image
                    og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                    if og_image and og_image.get("content"):
                        result["image_url"] = og_image.get("content").strip()
                        
                    # 2. Extract title
                    og_title = soup.find("meta", property="og:title") or soup.find("title")
                    if og_title:
                        # meta tags have 'content', title tag has text content
                        content = og_title.get("content") or og_title.text
                        if content:
                            result["title"] = content.strip()
                            
                    # 3. Extract description
                    og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
                    if og_desc and og_desc.get("content"):
                        result["description"] = og_desc.get("content").strip()
                        
                    result["success"] = True
                    logger.info("Successfully scraped OG metadata.")
                else:
                    logger.warning(f"Failed to scrape URL (Status {resp.status_code}): {url}")
        except httpx.TimeoutException:
            logger.warning(f"Timeout occurred ({self.timeout}s limit reached) scraping URL: {url}")
        except Exception as e:
            logger.error(f"Error scraping OG metadata from {url}: {e}")
            
        return result
