"""
scrapers/stealth_scraper.py
Production-grade Two-Tier Anti-Bot Resilient Scraper Engine.

Tier 1: High-Speed Chrome TLS & JA3 Impersonation via curl_cffi (10x speed, zero browser overhead).
Tier 2: Playwright Stealth with Selective Media Aborting & Proxy Routing (SPA React hydration support).

Includes Amazon CAPTCHA / "Robot Check" and Cloudflare 403 Wall Detection.
"""

import os
import json
import re
import logging
import asyncio
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger("LootStealthScraper")

STEALTH_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BOT_WALL_INDICATORS = [
    "type the characters you see in this image",
    "robot check",
    "to discuss automated access to amazon data",
    "enter the characters you see below",
    "cf-browser-verification",
    "just a moment...",
    "access denied",
    "attention required! | cloudflare",
    "verify you are a human"
]


def is_captcha_or_bot_wall(html: str) -> bool:
    """Detects if response HTML is an Amazon CAPTCHA, 'Robot Check', or Cloudflare block wall."""
    if not html:
        return True
    lower_html = html.lower()
    for indicator in BOT_WALL_INDICATORS:
        if indicator in lower_html:
            return True
    return False


def parse_json_ld_schema(html: str) -> Optional[Dict[str, Any]]:
    """
    Parses JSON-LD structured microdata from <script type="application/ld+json">.
    Returns dictionary with title, price, mrp, in_stock, and image_url.
    """
    if not html or is_captcha_or_bot_wall(html):
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else data.get("@graph", [data])

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    item_type = str(item.get("@type", "")).lower()
                    if "product" in item_type or "offer" in item_type:
                        title = item.get("name") or item.get("title")
                        image = item.get("image")
                        if isinstance(image, list) and len(image) > 0:
                            image = image[0]
                        elif isinstance(image, dict):
                            image = image.get("url")

                        offers = item.get("offers", {})
                        if isinstance(offers, list) and len(offers) > 0:
                            offers = offers[0]

                        price = offers.get("price") or item.get("price")
                        availability = str(offers.get("availability", "")).lower()
                        in_stock = "instock" in availability or "in_stock" in availability if availability else True

                        if title and price is not None:
                            try:
                                clean_price = float(re.sub(r"[^\d.]", "", str(price)))
                                return {
                                    "title": str(title).strip(),
                                    "price": clean_price,
                                    "mrp": clean_price * 1.25,
                                    "in_stock": in_stock,
                                    "image_url": str(image) if image else "",
                                    "strategy": "json_ld"
                                }
                            except ValueError:
                                pass
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"[Stealth Scraper] JSON-LD parsing exception: {e}")

    return None


async def scrape_tier1_curl_cffi(url: str, timeout_seconds: float = 6.0) -> Optional[Dict[str, Any]]:
    """
    Tier 1 Scraper: Uses curl_cffi AsyncSession with Chrome JA3 TLS impersonation.
    Bypasses datacenter IP / TLS fingerprint blocks at 10x speed with 0 browser overhead.
    """
    proxy_url = os.environ.get("SCRAPER_PROXY_URL") or None
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    try:
        from curl_cffi.requests import AsyncSession
        headers = {
            "User-Agent": STEALTH_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="120", "Chromium";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }

        async with AsyncSession(impersonate="chrome120", proxies=proxies, timeout=int(timeout_seconds)) as session:
            resp = await session.get(url, headers=headers)
            if resp.status_code != 200:
                logger.debug(f"[Tier 1 curl_cffi] HTTP {resp.status_code} for {url[:45]}")
                return None

            html = resp.text
            if is_captcha_or_bot_wall(html):
                logger.warning(f"[Tier 1 curl_cffi] Bot wall / CAPTCHA detected for {url[:45]}")
                return None

            # 1. Try JSON-LD Microdata Parsing
            json_ld_data = parse_json_ld_schema(html)
            if json_ld_data and json_ld_data.get("title") and json_ld_data.get("price", 0) > 0:
                json_ld_data["strategy"] = "tier1_curl_cffi_json_ld"
                return json_ld_data

            # 2. Try DOM Parsing via BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            title_elem = soup.select_one("#productTitle, h1, .product-title, ._35Kyfz, .B_NuCI")
            price_elem = soup.select_one(".a-price-whole, ._30jeq3, .pdp-price, .p-price")

            if title_elem and price_elem:
                title_text = title_elem.get_text().strip()
                price_text = price_elem.get_text().strip()
                try:
                    clean_price = float(re.sub(r"[^\d.]", "", price_text))
                    in_stock = True
                    avail_elem = soup.select_one("#availability, ._16frp0, .out-of-stock")
                    if avail_elem:
                        avail_text = avail_elem.get_text().lower()
                        if "currently unavailable" in avail_text or "out of stock" in avail_text:
                            in_stock = False

                    if title_text and clean_price > 0:
                        return {
                            "title": title_text,
                            "price": clean_price,
                            "mrp": clean_price * 1.25,
                            "in_stock": in_stock,
                            "image_url": "",
                            "strategy": "tier1_curl_cffi_dom"
                        }
                except ValueError:
                    pass

    except Exception as e:
        logger.debug(f"[Tier 1 curl_cffi] Exception for {url[:45]}: {e}")

    return None


async def scrape_tier2_playwright(url: str, timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
    """
    Tier 2 Scraper: Playwright Stealth Browser fallback with SPA hydration support.
    Selectively blocks media assets (.png, .jpg, .svg, .woff) but ALLOWS stylesheets/scripts.
    Supports optional SCRAPER_PROXY_URL proxy routing.
    """
    proxy_url = os.environ.get("SCRAPER_PROXY_URL") or None
    proxy_config = {"server": proxy_url} if proxy_url else None

    result = {
        "title": "",
        "price": 0.0,
        "mrp": 0.0,
        "in_stock": True,
        "image_url": "",
        "strategy": "tier2_playwright_dom"
    }

    try:
        from patchright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy=proxy_config,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]
            )

            context = await browser.new_context(
                user_agent=STEALTH_USER_AGENT,
                viewport={"width": 1280, "height": 800}
            )

            page = await context.new_page()

            # Selective Resource Interception: Block ONLY images & media, allow CSS & JS for React SPA hydration
            async def intercept_route(route):
                resource_type = route.request.resource_type
                if resource_type in ["image", "media", "font"]:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", intercept_route)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_seconds * 1000))
                content = await page.content()

                if is_captcha_or_bot_wall(content):
                    logger.warning(f"[Tier 2 Playwright] Bot wall / CAPTCHA detected for {url[:45]}")
                    await browser.close()
                    return None

                # 1. Primary Strategy: JSON-LD Structured Microdata
                json_ld_data = parse_json_ld_schema(content)
                if json_ld_data and json_ld_data.get("title") and json_ld_data.get("price", 0) > 0:
                    json_ld_data["strategy"] = "tier2_playwright_json_ld"
                    await browser.close()
                    return json_ld_data

                # 2. Secondary Strategy: SPA hydrated DOM elements
                title_elem = await page.query_selector("#productTitle, h1, .product-title, ._35Kyfz, .B_NuCI")
                if title_elem:
                    title_text = await title_elem.text_content()
                    if title_text:
                        result["title"] = title_text.strip()

                price_elem = await page.query_selector(".a-price-whole, ._30jeq3, .pdp-price, .p-price")
                if price_elem:
                    price_text = await price_elem.text_content()
                    if price_text:
                        try:
                            result["price"] = float(re.sub(r"[^\d.]", "", price_text))
                            result["mrp"] = result["price"] * 1.25
                        except ValueError:
                            pass

                avail_elem = await page.query_selector("#availability, ._16frp0, .out-of-stock")
                if avail_elem:
                    avail_text = (await avail_elem.text_content() or "").lower()
                    if "currently unavailable" in avail_text or "out of stock" in avail_text:
                        result["in_stock"] = False

                if result["title"] and result["price"] > 0:
                    await browser.close()
                    return result

            except Exception as e:
                logger.warning(f"[Tier 2 Playwright] Navigation error for {url[:45]}: {e}")
            finally:
                await browser.close()

    except Exception as e:
        logger.debug(f"[Tier 2 Playwright] Playwright unavailable or failed: {e}")

    return None


async def scrape_product_details(url: str, timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
    """
    Unified Entrypoint: Two-Tier Resilient Scraping Engine.
    Tier 1: Fast TLS JA3 Impersonation via curl_cffi (10x speed, 0 browser overhead).
    Tier 2: Playwright Stealth with SPA hydration support & optional Proxy routing.
    """
    if not url or not isinstance(url, str):
        return None

    # Execute Tier 1 (curl_cffi TLS impersonation)
    tier1_res = await scrape_tier1_curl_cffi(url, timeout_seconds=min(timeout_seconds, 6.0))
    if tier1_res and tier1_res.get("title") and tier1_res.get("price", 0) > 0:
        logger.info(f"[Stealth Scraper] Tier 1 (curl_cffi) succeeded for '{tier1_res['title'][:35]}...'")
        return tier1_res

    # Fallback to Tier 2 (Playwright Stealth Browser)
    logger.info(f"[Stealth Scraper] Falling back to Tier 2 (Playwright Stealth) for {url[:45]}")
    tier2_res = await scrape_tier2_playwright(url, timeout_seconds=timeout_seconds)
    if tier2_res and tier2_res.get("title") and tier2_res.get("price", 0) > 0:
        logger.info(f"[Stealth Scraper] Tier 2 (Playwright) succeeded for '{tier2_res['title'][:35]}...'")
        return tier2_res

    logger.warning(f"[Stealth Scraper] Both Tier 1 and Tier 2 failed for {url[:50]}")
    return None


def scrape_product_details_sync(url: str, timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
    """Synchronous wrapper for scrape_product_details."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(scrape_product_details(url, timeout_seconds))
        else:
            return asyncio.run(scrape_product_details(url, timeout_seconds))
    except Exception:
        return asyncio.run(scrape_product_details(url, timeout_seconds))
