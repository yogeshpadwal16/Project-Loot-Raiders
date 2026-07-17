import re
import time
import logging
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from plugins.base_plugin import BaseRetailerPlugin
from utils.parser import calculate_true_discount

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
            
            for card in cards:
                try:
                    # 1. Extract Target Link URL
                    links = card.find_elements(By.TAG_NAME, "a")
                    raw_url = None
                    if links:
                        # Scan all links for product patterns
                        for l in links:
                            href = l.get_attribute("href")
                            if href and ("javascript" not in href) and len(href) > 15:
                                # Exclude search, category, or browse pages
                                if "/search" not in href and "/s/" not in href and "/c/" not in href and "/pr?" not in href and "/all-" not in href:
                                    raw_url = href
                                    break
                        if not raw_url:
                            first_href = links[0].get_attribute("href")
                            if first_href and "/search" not in first_href and "/s/" not in first_href and "/c/" not in first_href and "/pr?" not in first_href and "/all-" not in first_href:
                                raw_url = first_href
                            
                    if not raw_url:
                        # Check if the card itself is an a tag or wrapped in/ancestor of one
                        if card.tag_name == "a":
                            raw_url = card.get_attribute("href")
                        else:
                            try:
                                parent_a = card.find_element(By.XPATH, "./ancestor::a")
                                parent_href = parent_a.get_attribute("href")
                                if parent_href and "/search" not in parent_href and "/s/" not in parent_href and "/c/" not in parent_href and "/pr?" not in parent_href and "/all-" not in parent_href:
                                    raw_url = parent_href
                            except:
                                pass
                            
                    if not raw_url:
                        # Fallback: check data-product-slug attribute (JioMart / Meesho and other modern SPAs)
                        slug = card.get_attribute("data-product-slug")
                        if not slug:
                            try:
                                parent_container = card.find_element(By.XPATH, "./parent::div[@data-product-slug]")
                                slug = parent_container.get_attribute("data-product-slug")
                            except:
                                pass
                        
                        if slug:
                            prod_id = card.get_attribute("data-id")
                            if not prod_id:
                                try:
                                    gtm_el = card.find_element(By.CSS_SELECTOR, ".gtmEvents")
                                    prod_id = gtm_el.get_attribute("data-id")
                                except:
                                    pass
                            
                            if not prod_id:
                                match_num = re.findall(r'\d+$', slug)
                                if match_num:
                                    prod_id = match_num[0]
                                    
                            vertical = "groceries"
                            try:
                                gtm_el = card.find_element(By.CSS_SELECTOR, ".gtmEvents")
                                v = gtm_el.get_attribute("data-vertical")
                                if v: vertical = v.lower()
                            except:
                                pass
                                
                            # Clean slug of merchant suffix (e.g. -mmdlqy-74442527)
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
                    title = ""
                    try:
                        title_el = card.find_element(By.CSS_SELECTOR, config['title_selector'])
                        title = title_el.get_attribute("title") or title_el.get_attribute("textContent").strip()
                    except:
                        pass
                        
                    if not title and card.text:
                        # Fallback: Parse first line of text
                        lines = [l.strip() for l in card.text.split("\n") if l.strip()]
                        for l in lines:
                            if (len(l) > 12 
                                and not l.startswith("₹") 
                                and "OFF" not in l 
                                and "%" not in l):
                                title = l
                                break
                                
                    if not title or len(title) < 5:
                        continue
                        
                    title = re.sub(r'\s+', ' ', title).strip()
                    
                    # 3. Extract Image (with rating star and icon filtering)
                    img_url = None
                    try:
                        img_elements = card.find_elements(By.TAG_NAME, "img")
                        for img_element in img_elements:
                            candidate_url = None
                            for attr in ["src", "data-src", "srcset", "data-lazy-src", "data-original"]:
                                val = img_element.get_attribute(attr)
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
                                alt_text = (img_element.get_attribute("alt") or "").lower()
                                class_text = (img_element.get_attribute("class") or "").lower()
                                
                                # Filter out common UI assets, star ratings, and placeholders
                                if any(x in lower_url for x in ["star", "rating", "icon", "logo", "arrow", "placeholder", "loading", "gif", "svg"]):
                                    continue
                                if any(x in alt_text for x in ["star", "rating", "icon", "logo", "arrow"]):
                                    continue
                                if any(x in class_text for x in ["star", "rating", "icon", "logo", "arrow"]):
                                    continue
                                    
                                img_url = candidate_url
                                break
                    except Exception as img_err:
                        logging.debug(f"Image extraction error: {img_err}")
                        
                    if not img_url:
                        # Fallback for picture/source responsive image configurations
                        try:
                            sources = card.find_elements(By.TAG_NAME, "source")
                            for s in sources:
                                val = s.get_attribute("srcset") or s.get_attribute("data-srcset")
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
                        except:
                            pass
                        
                    # 4. Extract pricing and discount
                    price, mrp, true_discount = calculate_true_discount(card.text)
                    min_discount = settings.get("min_discount", 30.0)
                    if price and mrp and (min_discount <= true_discount <= 98.0):
                        from utils.parser import extract_rating_and_reviews, detect_bank_offers
                        rating, reviews = extract_rating_and_reviews(card.text)
                        has_bank_offer = detect_bank_offers(card.text)
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
                        except:
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
