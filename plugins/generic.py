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

def clean_and_upgrade_image_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    if "amazon" in url.lower():
        url = re.sub(r'\._[a-zA-Z0-9_-]+_(?=\.[a-zA-Z]+$)', '._AC_SL1500_', url)
    elif "flipkart" in url.lower():
        url = re.sub(r'/image/\d+/\d+/', '/image/832/832/', url)
    return url

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
        if "myntra" in self._platform_id.lower():
            return self._extract_myntra_deals(config, settings)
        if "meesho" in self._platform_id.lower():
            return self._extract_meesho_deals(config, settings)
            
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
                    if "/p/" in raw_url:
                        try:
                            p_path = raw_url.split("/p/")[-1].split("?")[0].rstrip("/")
                            parts = [p for p in p_path.split("/") if p]
                            if parts:
                                prod_id = parts[-1]
                        except Exception:
                            pass
                            
                    if not prod_id:
                        match_id = re.search(r'/p/([a-zA-Z0-9_-]+)', raw_url)
                        if match_id:
                            prod_id = match_id.group(1)
                        else:
                            match_num = re.findall(r'\b\d{6,15}\b', raw_url)
                            if match_num:
                                prod_id = match_num[0]
                                
                    if not prod_id:
                        import hashlib
                        prod_id = hashlib.md5(raw_url.encode('utf-8')).hexdigest()[:16]
                        
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
                            "image_url": clean_and_upgrade_image_url(img_url),
                            "url": raw_url,
                            "is_lightning": False,
                            "rating": rating,
                            "reviews": reviews,
                            "has_bank_offer": has_bank_offer
                        })
                except Exception as card_err:
                    logging.warning(f"[Generic Plugin - {self._platform_id}] Skipped card parsing on URL: {config['url']}. Error: {card_err}")
                    continue
            
            # Fallback metadata extraction layer (OG, JSON-LD, schema, regex) if no deals found
            if not deals:
                logging.info(f"[Generic Plugin - {self._platform_id}] No deals extracted via selectors. Activating metadata fallback parser...")
                try:
                    js_meta_script = """
                    const result = {
                        title: "",
                        image_url: "",
                        url: window.location.href,
                        price: null,
                        mrp: null,
                        page_text: document.body ? document.body.innerText : ""
                    };
                    
                    // 1. OG Title
                    const ogTitle = document.querySelector('meta[property="og:title"]') || 
                                    document.querySelector('meta[name="twitter:title"]') ||
                                    document.querySelector('meta[name="title"]');
                    if (ogTitle) result.title = ogTitle.getAttribute("content");
                    if (!result.title) result.title = document.title;
                    
                    // 2. OG Image
                    const ogImage = document.querySelector('meta[property="og:image"]') || 
                                    document.querySelector('meta[name="twitter:image"]') || 
                                    document.querySelector('link[rel="image_src"]');
                    if (ogImage) result.image_url = ogImage.getAttribute("content") || ogImage.getAttribute("href");
                    
                    // 3. OG URL
                    const ogUrl = document.querySelector('meta[property="og:url"]') || 
                                  document.querySelector('link[rel="canonical"]');
                    if (ogUrl) result.url = ogUrl.getAttribute("content") || ogUrl.getAttribute("href") || result.url;
                    
                    // 3.5. Meta Price & MRP Extraction
                    const ogPrice = document.querySelector('meta[property="og:price:amount"]') || 
                                    document.querySelector('meta[property="product:price:amount"]') ||
                                    document.querySelector('meta[name="twitter:price:amount"]');
                    if (ogPrice) result.price = parseFloat(ogPrice.getAttribute("content"));

                    const ogMrp = document.querySelector('meta[property="og:price:standard_amount"]') || 
                                  document.querySelector('meta[property="product:price:standard_amount"]') ||
                                  document.querySelector('meta[name="twitter:price:standard_amount"]');
                    if (ogMrp) result.mrp = parseFloat(ogMrp.getAttribute("content"));
                    
                    // 4. JSON-LD parsing
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    const parseNode = (node) => {
                        if (!node) return;
                        if (node["@type"] === "Product" || node["@type"] === "http://schema.org/Product") {
                            if (node.name) result.title = node.name;
                            if (node.image) {
                                if (typeof node.image === "string") result.image_url = node.image;
                                else if (Array.isArray(node.image) && node.image.length > 0) result.image_url = node.image[0];
                            }
                            if (node.offers) {
                                const offers = node.offers;
                                if (Array.isArray(offers)) {
                                    const offer = offers[0];
                                    if (offer.price) result.price = parseFloat(offer.price);
                                    if (offer.highPrice) result.mrp = parseFloat(offer.highPrice);
                                    else if (offer.priceSpecification && offer.priceSpecification.price) {
                                        result.price = parseFloat(offer.priceSpecification.price);
                                    }
                                } else {
                                    if (offers.price) result.price = parseFloat(offers.price);
                                    if (offers.highPrice) result.mrp = parseFloat(offers.highPrice);
                                    else if (offers.priceSpecification && offers.priceSpecification.price) {
                                        result.price = parseFloat(offers.priceSpecification.price);
                                    }
                                }
                            }
                        }
                        if (node["@graph"] && Array.isArray(node["@graph"])) {
                            for (let n of node["@graph"]) parseNode(n);
                        }
                    };
                    for (let i = 0; i < scripts.length; i++) {
                        try {
                            const data = JSON.parse(scripts[i].innerText);
                            if (Array.isArray(data)) {
                                for (let d of data) parseNode(d);
                            } else {
                                parseNode(data);
                            }
                        } catch (e) {}
                    }
                    return result;
                    """
                    meta = driver.execute_script(js_meta_script)
                    if meta:
                        title = meta.get("title", "").strip()
                        image_url = meta.get("image_url", "").strip()
                        url = meta.get("url", "").strip()
                        price = meta.get("price")
                        mrp = meta.get("mrp")
                        page_text = meta.get("page_text", "")
                        
                        # Fallback URL absolute path normalization
                        if url and not url.startswith("http"):
                            from urllib.parse import urljoin
                            url = urljoin(config['url'], url)
                            
                        # If price / MRP not found in JSON-LD, try to parse from the page text using regex
                        if not price or not mrp:
                            from utils.parser import calculate_true_discount
                            price_parsed, mrp_parsed, discount_parsed = calculate_true_discount(page_text)
                            if not price and price_parsed:
                                price = price_parsed
                            if not mrp and mrp_parsed:
                                mrp = mrp_parsed
                                
                        if price and not mrp:
                            mrp = int(price * 1.5)  # Fallback guess if missing MRP
                            
                        if price and mrp:
                            # Re-verify and compile discount
                            discount = ((mrp - price) / mrp) * 100
                            min_discount = settings.get("min_discount", 30.0)
                            if min_discount <= discount <= 98.0 and len(title) > 5:
                                import hashlib
                                prod_id = hashlib.md5(url.encode('utf-8')).hexdigest()[:16]
                                deals.append({
                                    "id": f"{self._platform_id}_{prod_id}",
                                    "title": title,
                                    "price": int(price),
                                    "mrp": int(mrp),
                                    "discount": round(discount, 2),
                                    "image_url": clean_and_upgrade_image_url(image_url),
                                    "url": url,
                                    "is_lightning": False
                                })
                                logging.info(f"[Metadata Fallback Success] Successfully extracted deal from metadata: '{title[:35]}' Price: {price}")
                except Exception as meta_err:
                    logging.error(f"[Metadata Fallback Error] {meta_err}")
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
                            "image_url": clean_and_upgrade_image_url(img_url),
                            "url": prod_url,
                            "is_lightning": False
                        })
                except Exception as card_err:
                    logging.warning(f"[Ajio Scraper] Error parsing API product: {card_err}")
                    continue
        except Exception as e:
            logging.error(f"[Ajio Scraper] Error fetching Ajio deals: {e}", exc_info=True)
            
        return deals

    def _extract_myntra_deals(self, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        import threading
        deals = []
        def worker():
            nonlocal deals
            try:
                deals = self._extract_myntra_deals_sync(config, settings)
            except Exception as e:
                logging.error(f"[Myntra Scraper] Inner thread error: {e}", exc_info=True)
                
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        return deals

    def _extract_myntra_deals_sync(self, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        deals = []
        try:
            from curl_cffi import requests
            from bs4 import BeautifulSoup
            import json
            import re
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.myntra.com/"
            }
            logging.info(f"[Myntra Scraper] Fetching Myntra URL via curl_cffi: {config['url']}")
            r = requests.get(config['url'], headers=headers, impersonate="chrome110", timeout=20)
            
            if r.status_code != 200:
                logging.error(f"[Myntra Scraper] Page fetch failed with status: {r.status_code}")
                return []
                
            soup = BeautifulSoup(r.text, "html.parser")
            script_tag = None
            for s in soup.find_all("script"):
                if s.string and "window.__myx__" in s.string:
                    script_tag = s.string
                    break
                    
            products = []
            if script_tag:
                try:
                    json_text = script_tag.split("window.__myx__ =")[1].strip().rstrip(';')
                    if ";" in json_text:
                        json_text = json_text.split(";")[0].strip()
                    data = json.loads(json_text)
                    
                    def find_products_in_json(obj):
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if k == "results" and isinstance(v, list):
                                    return v
                                if k == "products" and isinstance(v, list):
                                    return v
                                res = find_products_in_json(v)
                                if res:
                                    return res
                        elif isinstance(obj, list):
                            for item in obj:
                                res = find_products_in_json(item)
                                if res:
                                    return res
                        return None
                    
                    products = find_products_in_json(data)
                except Exception as parse_err:
                    logging.error(f"[Myntra Scraper] JSON parsing failed: {parse_err}")
            
            if products:
                logging.info(f"[Myntra Scraper] Found {len(products)} products in JSON")
                for p in products:
                    try:
                        prod_id = p.get("productId") or p.get("styleId")
                        if not prod_id:
                            continue
                        
                        brand = p.get("brand", "")
                        name = p.get("productName") or p.get("name") or p.get("additionalInfo", "")
                        title = f"{brand} {name}".strip()
                        
                        price_val = p.get("price")
                        mrp_val = p.get("mrp") or price_val
                        if not price_val:
                            continue
                            
                        price = int(price_val)
                        mrp = int(mrp_val)
                        
                        discount = 0.0
                        discount_val = p.get("discount")
                        if discount_val:
                            if isinstance(discount_val, (int, float)):
                                discount = float(discount_val)
                            else:
                                disc_match = re.search(r'(\d+)', str(discount_val))
                                if disc_match:
                                    discount = float(disc_match.group(1))
                                    
                        if mrp > price and discount == 0.0:
                            discount = ((mrp - price) / mrp) * 100
                            
                        img_url = p.get("searchImage") or p.get("image")
                        if not img_url and p.get("images"):
                            img_url = p["images"][0].get("src") or p["images"][0].get("imageURL")
                            
                        prod_url = p.get("landingPageUrl") or p.get("url", "")
                        if prod_url and not prod_url.startswith("http"):
                            prod_url = "https://www.myntra.com/" + prod_url.lstrip("/")
                            
                        min_discount = settings.get("min_discount", 30.0)
                        if min_discount <= discount <= 98.0 and len(title) > 5:
                            deals.append({
                                "id": f"{self._platform_id}_{prod_id}",
                                "title": title,
                                "price": price,
                                "mrp": mrp,
                                "discount": round(discount, 2),
                                "image_url": clean_and_upgrade_image_url(img_url),
                                "url": prod_url,
                                "is_lightning": False
                            })
                    except Exception as card_err:
                        pass
            else:
                logging.info("[Myntra Scraper] Falling back to DOM Selector parsing")
                cards = soup.select(config.get('card_selector', "li.product-base"))
                for card in cards:
                    try:
                        title_el = card.select_one(config.get('title_selector', "h4.product-product, h3.product-brand"))
                        title = title_el.text.strip() if title_el else ""
                        
                        link_el = card.select_one(config.get('link_selector', "a"))
                        href = link_el.get("href") if link_el else ""
                        if href and not href.startswith("http"):
                            prod_url = "https://www.myntra.com/" + href.lstrip("/")
                        else:
                            prod_url = href
                            
                        prod_id = None
                        if href:
                            id_match = re.search(r'/buy/.*?(\d+)', href) or re.search(r'/(\d+)/buy', href) or re.search(r'/style/(\d+)', href)
                            if id_match:
                                prod_id = id_match.group(1)
                        if not prod_id:
                            import hashlib
                            prod_id = hashlib.md5(prod_url.encode('utf-8')).hexdigest()[:10]
                            
                        price_el = card.select_one(".product-discountedPrice, .product-price")
                        price_text = price_el.text if price_el else ""
                        price_val = None
                        if price_text:
                            price_match = re.search(r'Rs\.\s*(\d+)', price_text) or re.search(r'₹\s*(\d+)', price_text)
                            if price_match:
                                price_val = int(price_match.group(1))
                                
                        mrp_el = card.select_one("del, .product-mrp")
                        mrp_text = mrp_el.text if mrp_el else ""
                        mrp_val = None
                        if mrp_text:
                            mrp_match = re.search(r'Rs\.\s*(\d+)', mrp_text) or re.search(r'₹\s*(\d+)', mrp_text)
                            if mrp_match:
                                mrp_val = int(mrp_match.group(1))
                                
                        if not price_val:
                            continue
                        if not mrp_val:
                            mrp_val = price_val
                            
                        img_el = card.select_one(config.get('image_selector', "img"))
                        img_url = img_el.get("src") or img_el.get("data-src") if img_el else None
                        
                        discount = 0.0
                        if mrp_val > price_val:
                            discount = ((mrp_val - price_val) / mrp_val) * 100
                            
                        min_discount = settings.get("min_discount", 30.0)
                        if min_discount <= discount <= 98.0 and len(title) > 5:
                            deals.append({
                                "id": f"{self._platform_id}_{prod_id}",
                                "title": title,
                                "price": price_val,
                                "mrp": mrp_val,
                                "discount": round(discount, 2),
                                "image_url": clean_and_upgrade_image_url(img_url),
                                "url": prod_url,
                                "is_lightning": False
                            })
                    except Exception as card_err:
                        pass
        except Exception as e:
            logging.error(f"[Myntra Scraper] Error fetching Myntra deals: {e}", exc_info=True)
        return deals

    def _extract_meesho_deals(self, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        import threading
        deals = []
        def worker():
            nonlocal deals
            try:
                deals = self._extract_meesho_deals_sync(config, settings)
            except Exception as e:
                logging.error(f"[Meesho Scraper] Inner thread error: {e}", exc_info=True)
                
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        return deals

    def _extract_meesho_deals_sync(self, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        deals = []
        try:
            from curl_cffi import requests
            from bs4 import BeautifulSoup
            import json
            import re
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.meesho.com/"
            }
            logging.info(f"[Meesho Scraper] Fetching Meesho URL via curl_cffi: {config['url']}")
            r = requests.get(config['url'], headers=headers, impersonate="chrome110", timeout=20)
            
            if r.status_code != 200:
                logging.error(f"[Meesho Scraper] Page fetch failed with status: {r.status_code}")
                return []
                
            soup = BeautifulSoup(r.text, "html.parser")
            script_tag = soup.find("script", id="__NEXT_DATA__")
            
            products = []
            if script_tag and script_tag.string:
                try:
                    data = json.loads(script_tag.string)
                    def find_products_in_json(obj):
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if k == "products" and isinstance(v, list):
                                    return v
                                if k == "catalog" and isinstance(v, dict) and "products" in v:
                                    return v["products"]
                                if k == "searchResults" and isinstance(v, dict) and "products" in v:
                                    return v["products"]
                                res = find_products_in_json(v)
                                if res:
                                    return res
                        elif isinstance(obj, list):
                            for item in obj:
                                res = find_products_in_json(item)
                                if res:
                                    return res
                        return None
                    
                    products = find_products_in_json(data)
                except Exception as parse_err:
                    logging.error(f"[Meesho Scraper] JSON parsing failed: {parse_err}")
            
            if products:
                logging.info(f"[Meesho Scraper] Found {len(products)} products in JSON")
                for p in products:
                    try:
                        prod_id = p.get("productId") or p.get("id") or p.get("product_id")
                        if not prod_id:
                            continue
                        
                        title = p.get("title") or p.get("name") or p.get("productName", "")
                        price_val = p.get("price") or p.get("discountedPrice")
                        mrp_val = p.get("mrp") or p.get("originalPrice") or price_val
                        
                        if not price_val:
                            continue
                            
                        price = int(price_val)
                        mrp = int(mrp_val)
                        
                        discount = 0.0
                        discount_val = p.get("discount")
                        if discount_val:
                            if isinstance(discount_val, (int, float)):
                                discount = float(discount_val)
                            else:
                                disc_match = re.search(r'(\d+)', str(discount_val))
                                if disc_match:
                                    discount = float(disc_match.group(1))
                                    
                        if mrp > price and discount == 0.0:
                            discount = ((mrp - price) / mrp) * 100
                            
                        img_url = p.get("image") or p.get("images", [None])[0] or p.get("searchImage")
                        if isinstance(img_url, dict):
                            img_url = img_url.get("url") or img_url.get("src")
                            
                        prod_url = p.get("landingPageUrl") or p.get("url", "")
                        if prod_url and not prod_url.startswith("http"):
                            prod_url = "https://www.meesho.com/" + prod_url.lstrip("/")
                        else:
                            prod_url = f"https://www.meesho.com/p/{prod_id}"
                            
                        min_discount = settings.get("min_discount", 30.0)
                        if min_discount <= discount <= 98.0 and len(title) > 5:
                            deals.append({
                                "id": f"{self._platform_id}_{prod_id}",
                                "title": title,
                                "price": price,
                                "mrp": mrp,
                                "discount": round(discount, 2),
                                "image_url": clean_and_upgrade_image_url(img_url),
                                "url": prod_url,
                                "is_lightning": False
                            })
                    except Exception as card_err:
                        pass
            else:
                logging.info("[Meesho Scraper] Falling back to DOM Selector parsing")
                cards = soup.select(config.get('card_selector', "a[href*='/p/']"))
                for card in cards:
                    try:
                        href = card.get("href")
                        if href and not href.startswith("http"):
                            prod_url = "https://www.meesho.com" + href
                        else:
                            prod_url = href
                            
                        prod_id = None
                        if href:
                            id_match = re.search(r'/p/([a-zA-Z0-9]+)', href)
                            if id_match:
                                prod_id = id_match.group(1)
                        if not prod_id:
                            continue
                            
                        title_el = card.select_one(config.get('title_selector', "p[class*='ProductTitle']"))
                        title = title_el.text.strip() if title_el else ""
                        
                        price_el = card.select_one("[class*='Price'], p[class*='Price'], span[class*='Price']")
                        price_text = price_el.text if price_el else ""
                        price_val = None
                        if price_text:
                            price_match = re.search(r'₹\s*([0-9,]+)', price_text)
                            if price_match:
                                price_val = int(price_match.group(1).replace(",", ""))
                                
                        mrp_el = card.select_one("del, [class*='OriginalPrice'], [style*='line-through']")
                        mrp_text = mrp_el.text if mrp_el else ""
                        mrp_val = None
                        if mrp_text:
                            mrp_match = re.search(r'₹\s*([0-9,]+)', mrp_text)
                            if mrp_match:
                                mrp_val = int(mrp_match.group(1).replace(",", ""))
                                
                        if not price_val:
                            continue
                        if not mrp_val:
                            mrp_val = int(price_val * 1.3)
                            
                        img_el = card.select_one("img")
                        img_url = img_el.get("src") if img_el else None
                        
                        discount = ((mrp_val - price_val) / mrp_val) * 100
                        
                        min_discount = settings.get("min_discount", 30.0)
                        if min_discount <= discount <= 98.0 and len(title) > 5:
                            deals.append({
                                "id": f"{self._platform_id}_{prod_id}",
                                "title": title,
                                "price": price_val,
                                "mrp": mrp_val,
                                "discount": round(discount, 2),
                                "image_url": clean_and_upgrade_image_url(img_url),
                                "url": prod_url,
                                "is_lightning": False
                            })
                    except Exception as card_err:
                        pass
        except Exception as e:
            logging.error(f"[Meesho Scraper] Error fetching Meesho deals: {e}", exc_info=True)
        return deals
