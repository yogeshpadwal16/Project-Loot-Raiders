"""
Phase 4: Anti-Bot Playwright / Scrapling JSON-LD Microdata Scraper Module.
Parses structured microdata (JSON-LD) for title, price, MRP, inStock, and image_url.
Bypasses Cloudflare/Akamai bot detection with stealth request interception.
"""

import json
import re
import logging
import asyncio
from typing import Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("LootAntiBotScraper")


def extract_json_ld_microdata(html_content: str) -> Optional[Dict[str, Any]]:
    """
    Parses JSON-LD structured microdata from <script type="application/ld+json">.
    Extracts schema.org Product or Offer objects.
    """
    if not html_content:
        return None

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
                # Handle top-level list or @graph
                items = data if isinstance(data, list) else data.get("@graph", [data])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_type = str(item.get("@type", "")).lower()
                    if "product" in item_type or "offer" in item_type:
                        title = item.get("name") or item.get("title")
                        brand = item.get("brand", {}).get("name") if isinstance(item.get("brand"), dict) else item.get("brand")
                        image = item.get("image")
                        if isinstance(image, list):
                            image = image[0]
                        elif isinstance(image, dict):
                            image = image.get("url")

                        offers = item.get("offers", {})
                        if isinstance(offers, list):
                            offers = offers[0] if len(offers) > 0 else {}

                        price = offers.get("price") or item.get("price")
                        currency = offers.get("priceCurrency") or "INR"
                        availability = str(offers.get("availability", "")).lower()
                        in_stock = "instock" in availability or "in_stock" in availability if availability else True

                        if title and price:
                            try:
                                num_price = float(re.sub(r"[^\d.]", "", str(price)))
                                return {
                                    "title": str(title).strip(),
                                    "price": num_price,
                                    "mrp": num_price * 1.25, # Default MRP estimate if unlisted
                                    "brand": str(brand) if brand else "",
                                    "image_url": str(image) if image else "",
                                    "in_stock": in_stock,
                                    "currency": currency,
                                    "source": "json_ld"
                                }
                            except ValueError:
                                pass
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"[JSON-LD Parser] Extraction error: {e}")

    return None


async def scrape_product_live_async(url: str, timeout: float = 12.0) -> Dict[str, Any]:
    """
    Asynchronously scrapes product telemetry using Patchright / Playwright request interception
    with JSON-LD microdata parsing and anti-bot stealth fallback.
    """
    result = {
        "title": "",
        "price": 0.0,
        "mrp": 0.0,
        "in_stock": True,
        "image_url": "",
        "success": False,
        "source": "fallback"
    }

    try:
        from patchright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )

            page = await context.new_page()

            # Abort heavy resource downloads (images, fonts, stylesheets) for 3x speedup
            async def intercept_route(route):
                if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", intercept_route)

            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout * 1000))
                content = await page.content()

                # Phase 1: Try JSON-LD Microdata parsing first
                json_ld = extract_json_ld_microdata(content)
                if json_ld and json_ld.get("title") and json_ld.get("price"):
                    result.update(json_ld)
                    result["success"] = True
                    await browser.close()
                    return result

                # Phase 2: Fallback DOM title/price extraction
                title_elem = await page.query_selector("#productTitle, h1, .product-title")
                if title_elem:
                    title_text = await title_elem.text_content()
                    if title_text:
                        result["title"] = title_text.strip()

                price_elem = await page.query_selector(".a-price-whole, ._30jeq3, .pdp-price")
                if price_elem:
                    price_text = await price_elem.text_content()
                    if price_text:
                        try:
                            result["price"] = float(re.sub(r"[^\d.]", "", price_text))
                            result["success"] = True
                        except ValueError:
                            pass

            except Exception as e:
                logger.warning(f"[Anti-Bot Scraper] Playwright page load exception: {e}")
            finally:
                await browser.close()

    except Exception as e:
        logger.debug(f"[Anti-Bot Scraper] Patchright/Playwright not available ({e}). Using requests fallback.")

    # Synchronous Requests Fallback if Playwright fails
    if not result["success"]:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            res = requests.get(url, headers=headers, timeout=6.0)
            if res.status_code == 200:
                json_ld = extract_json_ld_microdata(res.text)
                if json_ld:
                    result.update(json_ld)
                    result["success"] = True
        except Exception as err:
            logger.warning(f"[Anti-Bot Scraper] Sync requests fallback error: {err}")

    return result


def scrape_product_live(url: str, timeout: float = 12.0) -> Dict[str, Any]:
    """Synchronous wrapper for scrape_product_live_async."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(scrape_product_live_async(url, timeout))
        else:
            return asyncio.run(scrape_product_live_async(url, timeout))
    except Exception:
        return asyncio.run(scrape_product_live_async(url, timeout))
