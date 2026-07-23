import re
import time
import logging
import json
import os
import requests
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from plugins.base_plugin import BaseRetailerPlugin
from utils.parser import calculate_true_discount

def clean_and_truncate_html(html_content: str, max_chars: int = 10000) -> str:
    # Remove script and style blocks
    html_content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', html_content, flags=re.IGNORECASE)
    # Remove svg blocks
    html_content = re.sub(r'<svg\b[^<]*(?:(?!<\/svg>)<[^<]*)*<\/svg>', '', html_content, flags=re.IGNORECASE)
    # Remove comments
    html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
    # Compress whitespaces
    html_content = re.sub(r'\s+', ' ', html_content)
    return html_content[:max_chars]

def auto_heal_with_dom_analysis(driver, platform_id: str, config: dict, settings: dict) -> bool:
    """
    DOM-based self-healing selector recovery. Scans the page for common
    e-commerce product card patterns by trying known structural selectors
    and scoring candidates. No external API required.
    """
    logging.info(f"[Generic Plugin - {platform_id}] Attempting DOM-based self-healing selector recovery...")
    try:
        from selenium.webdriver.common.by import By
        
        # Common product card patterns used by major Indian e-commerce sites
        CARD_CANDIDATES = [
            # Generic product card patterns
            "[data-id]", "[data-product-id]", "[data-pid]",
            "div[class*='product']", "div[class*='Product']",
            "div[class*='card']", "div[class*='Card']",
            "div[class*='item']", "div[class*='Item']",
            "li[class*='product']", "li[class*='Product']",
            "div[class*='deal']", "div[class*='Deal']",
            "div[class*='offer']", "div[class*='Offer']",
            "article", "section[class*='product']",
            # Platform-specific patterns
            "div[class*='Listing']", "div[class*='listing']",
            "div[class*='grid'] > div", "ul[class*='product'] > li",
            "div[class*='result'] > div", "div[class*='search'] > div",
        ]
        
        best_selector = None
        best_count = 0
        
        for selector in CARD_CANDIDATES:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                count = len(elements)
                
                # Valid card containers should have multiple elements (3-100 range)
                if 3 <= count <= 100 and count > best_count:
                    # Validate: each card should contain at least a link and some text
                    sample = elements[0]
                    has_link = len(sample.find_elements(By.TAG_NAME, "a")) > 0
                    has_text = len(sample.text.strip()) > 10
                    has_img = len(sample.find_elements(By.TAG_NAME, "img")) > 0
                    
                    if has_link and has_text:
                        best_selector = selector
                        best_count = count
                        logging.info(f"[DOM Healer] Candidate: {selector} -> {count} cards (link={has_link}, text={has_text}, img={has_img})")
            except Exception:
                pass
        
        if best_selector and best_count >= 3:
            logging.info(f"[Generic Plugin - {platform_id}] DOM auto-heal found: {best_selector} ({best_count} cards)")
            from database.operations import update_selector_in_db_and_json
            update_selector_in_db_and_json(platform_id, card_selector=best_selector)
            config['card_selector'] = best_selector
            return True
        else:
            logging.warning(f"[Generic Plugin - {platform_id}] DOM auto-heal could not find suitable card selectors.")
            
    except Exception as e:
        logging.error(f"[Generic Plugin - {platform_id}] DOM auto-heal selector recovery failed: {e}")
    return False

class GenericRetailerPlugin(BaseRetailerPlugin):
    def __init__(self, platform_id: str):
        self._platform_id = platform_id

    @property
    def retailer_id(self) -> str:
        return self._platform_id

    def extract_deals(self, driver, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        if "ajio" in self._platform_id.lower():
            return self._extract_ajio_deals(config, settings)
            
        deals = []
        try:
            if not self.load_page_with_retries(driver, config['url'], delay=5.0):
                logging.error(f"[Generic Plugin - {self._platform_id}] Failed to load target URL: {config['url']}")
                return []
                
            # Detect anti-bot protection/Access Denied pages
            title_text = driver.title or ""
            if "access denied" in title_text.lower() or "just a moment" in title_text.lower() or "attention required" in title_text.lower():
                logging.error(f"[Generic Plugin - {self._platform_id}] Blocked by anti-bot protection (Title: '{title_text}') for URL: {config['url']}. Recovery Action: Enable proxies or rotate user-agents.")
                return []
            
            # Simulated human scrolling
            for scroll in range(1, 4):
                driver.execute_script(f"window.scrollTo(0, {scroll * 600});")
                time.sleep(1.5)
                
            cards = driver.find_elements(By.CSS_SELECTOR, config['card_selector'])
            logging.info(f"[Generic Plugin - {self._platform_id}] Found {len(cards)} elements using card selector: {config['card_selector']}")
            
            if len(cards) == 0:
                FALLBACKS = {
                    "amazon": [
                        "div[data-component-type='s-search-result']",
                        "div[data-testid='product-card']",
                        "div.s-result-item",
                        "li.a-carousel-card"
                    ],
                    "flipkart": [
                        "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
                        "div._1AtVbE",
                        "div[data-id]"
                    ],
                    "myntra": [
                        "li.product-base",
                        "div.product-base",
                        "div[class*='product-tuple']"
                    ],
                    "ajio": [
                        "div.item",
                        "div.ganjo-product-grid",
                        "div.preview"
                    ],
                    "meesho": [
                        "a[href*='/p/']",
                        "div[class*='ProductList']"
                    ],
                    "tatacliq": [
                        "a.ProductModule__base",
                        "[class*='ProductModule__base']",
                        "div.ProductModule__base"
                    ],
                    "jiomart": [
                        "div.productContainer",
                        "div.productCard__productCard",
                        "li.j-grid-item"
                    ]
                }
                
                # Check platform match
                matching_platform = None
                for key in FALLBACKS.keys():
                    if key in self._platform_id.lower():
                        matching_platform = key
                        break
                        
                if matching_platform:
                    logging.info(f"[Generic Plugin - {self._platform_id}] Main card selector failed. Activating self-healing fallbacks...")
                    for fallback in FALLBACKS[matching_platform]:
                        if fallback == config['card_selector']:
                            continue
                        try:
                            fallback_cards = driver.find_elements(By.CSS_SELECTOR, fallback)
                            if len(fallback_cards) > 0:
                                logging.info(f"[Generic Plugin - {self._platform_id}] Auto-healed! Found {len(fallback_cards)} elements using fallback card selector: {fallback}")
                                from database.operations import update_selector_in_db_and_json
                                update_selector_in_db_and_json(self._platform_id, card_selector=fallback)
                                config['card_selector'] = fallback
                                cards = fallback_cards
                                break
                        except Exception as fb_err:
                            pass
                            
                # DOM-based Selector Recovery fallback (no API required)
                if len(cards) == 0:
                    healed = auto_heal_with_dom_analysis(driver, self._platform_id, config, settings)
                    if healed:
                        logging.info(f"[Generic Plugin - {self._platform_id}] DOM auto-heal successful. Rescanning with corrected selectors...")
                        cards = driver.find_elements(By.CSS_SELECTOR, config['card_selector'])
            
            js_script = """
            const cardSel = arguments[0];
            const titleSel = arguments[1];
            const cards = document.querySelectorAll(cardSel);
            const results = [];
            for (let i = 0; i < cards.length; i++) {
                const card = cards[i];
                const text = card.innerText || "";
                
                // Links
                const links = [];
                const linkEls = card.getElementsByTagName("a");
                for (let j = 0; j < linkEls.length; j++) {
                    links.push({
                        href: linkEls[j].href || "",
                        tagName: "a"
                    });
                }
                
                // Title
                let title = "";
                if (titleSel) {
                    const titleEl = card.querySelector(titleSel);
                    if (titleEl) {
                        title = titleEl.getAttribute("title") || titleEl.getAttribute("alt") || titleEl.textContent || "";
                    }
                }
                
                // Images
                const imgs = [];
                const imgEls = card.getElementsByTagName("img");
                for (let j = 0; j < imgEls.length; j++) {
                    const img = imgEls[j];
                    imgs.push({
                        src: img.getAttribute("src") || "",
                        dataSrc: img.getAttribute("data-src") || "",
                        srcset: img.getAttribute("srcset") || "",
                        dataLazySrc: img.getAttribute("data-lazy-src") || "",
                        dataOriginal: img.getAttribute("data-original") || "",
                        alt: img.getAttribute("alt") || "",
                        className: img.className || ""
                    });
                }
                
                // Sources
                const sources = [];
                const sourceEls = card.getElementsByTagName("source");
                for (let j = 0; j < sourceEls.length; j++) {
                    sources.push({
                        srcset: sourceEls[j].getAttribute("srcset") || sourceEls[j].getAttribute("data-srcset") || ""
                    });
                }
                
                results.push({
                    text: text,
                    links: links,
                    title: title,
                    imgs: imgs,
                    sources: sources,
                    tagName: card.tagName.toLowerCase(),
                    href: card.getAttribute("href") || "",
                    dataProductSlug: card.getAttribute("data-product-slug") || "",
                    dataId: card.getAttribute("data-id") || "",
                    parentDataProductSlug: (card.parentElement ? card.parentElement.getAttribute("data-product-slug") : "") || ""
                });
            }
            return results;
            """
            
            card_data_list = driver.execute_script(js_script, config['card_selector'], config.get('title_selector'))
            
            if not card_data_list:
                logging.warning(f"[Generic Plugin - {self._platform_id}] JS extraction returned no data for URL: {config['url']}")
                return deals
                
            for card in card_data_list:
                try:
                    # 1. Extract Target Link URL
                    links = card["links"]
                    raw_url = None
                    if links:
                        # Scan all links for product patterns
                        for l in links:
                            href = l["href"]
                            if href and ("javascript" not in href) and len(href) > 15:
                                # Exclude search, category, or browse pages
                                if "/search" not in href and "/s/" not in href and "/c/" not in href and "/pr?" not in href and "/all-" not in href:
                                    raw_url = href
                                    break
                        if not raw_url:
                            first_href = links[0]["href"]
                            if first_href and "/search" not in first_href and "/s/" not in first_href and "/c/" not in first_href and "/pr?" not in first_href and "/all-" not in first_href:
                                raw_url = first_href
                            
                    if not raw_url:
                        # Check if the card itself is an a tag or wrapped in/ancestor of one
                        if card["tagName"] == "a":
                            raw_url = card["href"]
                        else:
                            if card["href"]:
                                raw_url = card["href"]
                            
                    if not raw_url:
                        # Fallback: check data-product-slug attribute
                        slug = card["dataProductSlug"]
                        if not slug:
                            slug = card["parentDataProductSlug"]
                        
                        if slug:
                            prod_id = card["dataId"]
                            if not prod_id:
                                match_num = re.findall(r'\d+$', slug)
                                if match_num:
                                    prod_id = match_num[0]
                                    
                            vertical = "groceries"
                            clean_slug = re.sub(r'-[a-z0-9]{6}-\d+$', '', slug)
                            raw_url = f"/p/{vertical}/{clean_slug}/{prod_id}"
                            
                    if not raw_url:
                        continue
                        
                    # Convert to absolute URL if relative
                    if not raw_url.startswith("http"):
                        from urllib.parse import urljoin
                        raw_url = urljoin(config['url'], raw_url)
                        
                    # Extract unique ID from URL path or fallback
                    prod_id = None
                    match_id = re.search(r'/p/([a-zA-Z0-9_-]+)', raw_url)
                    if match_id:
                        prod_id = match_id.group(1)
                    else:
                        match_num = re.findall(r'\b\d{6,15}\b', raw_url)
                        if match_num:
                            prod_id = match_num[0]
                            
                    if not prod_id:
                        prod_id = str(abs(hash(raw_url)))
                        
                    # 2. Extract Title
                    title = card["title"]
                    if not title and card["text"]:
                        # Fallback: Parse first line of text
                        lines = [l.strip() for l in card["text"].split("\n") if l.strip()]
                        for l in lines:
                            if (len(l) > 12 
                                and not l.startswith("₹") 
                                and not l.startswith("â‚¹") 
                                and "OFF" not in l 
                                and "%" not in l):
                                title = l
                                break
                                
                    if not title or len(title) < 5:
                        continue
                        
                    title = re.sub(r'\s+', ' ', title).strip()
                    
                    # 3. Extract Image
                    img_url = None
                    img_elements = card["imgs"]
                    for img_element in img_elements:
                        candidate_url = None
                        for attr in ["src", "dataSrc", "srcset", "dataLazySrc", "dataOriginal"]:
                            val = img_element.get(attr)
                            if val:
                                val = val.strip()
                                if val.startswith("http") or val.startswith("data:image") or val.startswith("//"):
                                    if val.startswith("//"):
                                        val = "https:" + val
                                    if attr == "srcset":
                                        val = val.split()[0]
                                    candidate_url = val
                                    break
                        
                        if candidate_url:
                            lower_url = candidate_url.lower()
                            alt_text = (img_element.get("alt") or "").lower()
                            class_text = (img_element.get("className") or "").lower()
                            
                            if any(x in lower_url for x in ["star", "rating", "icon", "logo", "arrow", "placeholder", "loading", "gif", "svg"]):
                                continue
                            if any(x in alt_text for x in ["star", "rating", "icon", "logo", "arrow"]):
                                continue
                            if any(x in class_text for x in ["star", "rating", "icon", "logo", "arrow"]):
                                continue
                                
                            img_url = candidate_url
                            break
                            
                    if not img_url:
                        sources = card["sources"]
                        for s in sources:
                            val = s["srcset"]
                            if val:
                                url_candidate = val.split(",")[0].split()[0].strip()
                                if url_candidate.startswith("http") or url_candidate.startswith("//"):
                                    if url_candidate.startswith("//"):
                                        url_candidate = "https:" + url_candidate
                                    
                                    lower_cand = url_candidate.lower()
                                    if any(x in lower_cand for x in ["star", "rating", "icon", "logo", "arrow", "placeholder", "loading", "gif", "svg"]):
                                        continue
                                    img_url = url_candidate
                                    break
                                    
                    # 4. Extract pricing and discount
                    price, mrp, true_discount = calculate_true_discount(card["text"])
                    min_discount = settings.get("min_discount", 30.0)
                    if price and mrp and (min_discount <= true_discount <= 98.0):
                        from utils.parser import extract_rating_and_reviews, detect_bank_offers
                        rating, reviews = extract_rating_and_reviews(card["text"])
                        has_bank_offer = detect_bank_offers(card["text"])
                        deals.append({
                            "id": f"{self._platform_id}_{prod_id}",
                            "title": title,
                            "price": price,
                            "mrp": mrp,
                            "discount": true_discount,
                            "image_url": img_url,
                            "url": raw_url,
                            "is_lightning": False,
                            "rating": rating,
                            "reviews": reviews,
                            "has_bank_offer": has_bank_offer
                        })
                except Exception as card_err:
                    logging.warning(f"[Generic Plugin - {self._platform_id}] Skipped card parsing on URL: {config['url']}. Error: {card_err}")
                    continue
        except Exception as e:
            logging.error(f"Error in Generic Scraper for {self._platform_id}: {e}")
            
        return deals

    def _extract_ajio_deals(self, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        import threading
        deals = []
        def worker():
            nonlocal deals
            try:
                deals = self._extract_ajio_deals_sync(config, settings)
            except Exception as e:
                logging.error(f"[Ajio Scraper] Inner thread error: {e}", exc_info=True)
                
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        return deals

    def _extract_ajio_deals_sync(self, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        deals = []
        try:
            from curl_cffi import requests
            import urllib.parse
            parsed_url = urllib.parse.urlparse(config.get('url', ''))
            query_term = "offers"
            
            qs = urllib.parse.parse_qs(parsed_url.query)
            if 'text' in qs:
                query_term = qs['text'][0]
            elif parsed_url.path.startswith("/s/"):
                term = parsed_url.path.replace("/s/", "").replace("-", " ")
                if term:
                    query_term = term
            
            api_url = f"https://www.ajio.com/api/search?fields=SITE&currentPage=0&pageSize=45&format=json&query={urllib.parse.quote(query_term)}"
            logging.info(f"[Ajio Scraper] Fetching JSON API via curl_cffi: {api_url}")
            
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.ajio.com",
                "Referer": config.get('url', 'https://www.ajio.com/')
            }
            
            r = requests.get(api_url, headers=headers, impersonate="chrome", timeout=20)
            if r.status_code != 200:
                logging.error(f"[Ajio Scraper] API call failed with status: {r.status_code}")
                return []
                
            data = r.json()
            products = data.get("products", [])
            logging.info(f"[Ajio Scraper] Successfully parsed {len(products)} products from API!")
            
            for p in products:
                try:
                    code = p.get("code")
                    if not code:
                        continue
                    
                    title = p.get("name", "")
                    price_val = p.get("price", {}).get("value")
                    mrp_val = p.get("wasPriceData", {}).get("value") or price_val
                    
                    if not price_val:
                        continue
                        
                    price = int(price_val)
                    mrp = int(mrp_val)
                    
                    discount_str = p.get("discountPercent", "0")
                    discount = 0.0
                    if discount_str:
                        discount_str = discount_str.replace("% off", "").strip()
                        try:
                            discount = float(discount_str)
                        except Exception:
                            pass
                            
                    if mrp > price and not discount:
                        discount = ((mrp - price) / mrp) * 100
                        
                    img_url = p.get("fnlColorVariantData", {}).get("outfitPictureURL")
                    if not img_url and p.get("images"):
                        for img in p["images"]:
                            if img.get("url"):
                                img_url = img["url"]
                                break
                                
                    prod_url = p.get("url", "")
                    if prod_url and not prod_url.startswith("http"):
                        prod_url = "https://www.ajio.com" + prod_url
                        
                    min_discount = settings.get("min_discount", 30.0)
                    if min_discount <= discount <= 98.0:
                        deals.append({
                            "id": f"{self._platform_id}_{code}",
                            "title": title,
                            "price": price,
                            "mrp": mrp,
                            "discount": discount,
                            "image_url": img_url,
                            "url": prod_url,
                            "is_lightning": False
                        })
                except Exception as card_err:
                    logging.warning(f"[Ajio Scraper] Error parsing API product: {card_err}")
                    continue
        except Exception as e:
            logging.error(f"[Ajio Scraper] Error fetching Ajio deals: {e}", exc_info=True)
            
        return deals
