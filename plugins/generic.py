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
        deals = []
        try:
            if not self.load_page_with_retries(driver, config['url'], delay=5.0):
                logging.error(f"[Generic Plugin - {self._platform_id}] Failed to load target URL: {config['url']}")
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
                                raw_url = href
                                break
                        if not raw_url:
                            raw_url = links[0].get_attribute("href")
                            
                    if not raw_url:
                        # Check if the card itself or its ancestor is wrapped in an a tag
                        try:
                            parent_a = card.find_element(By.XPATH, "./ancestor::a")
                            raw_url = parent_a.get_attribute("href")
                        except:
                            pass
                            
                    if not raw_url:
                        continue
                        
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
                    
                    # 3. Extract Image
                    img_url = None
                    try:
                        img_element = card.find_element(By.CSS_SELECTOR, config['image_selector'])
                        for attr in ["data-src", "data-original", "data-img-src", "data-lazy-src", "src", "srcset"]:
                            val = img_element.get_attribute(attr)
                            if val:
                                val = val.strip()
                                if val.startswith("http") or val.startswith("data:image"):
                                    if attr == "srcset":
                                        val = val.split()[0]
                                    img_url = val
                                    break
                    except:
                        pass
                        
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
                                        img_url = url_candidate
                                        break
                        except:
                            pass
                        
                    # 4. Extract pricing and discount
                    price, mrp, true_discount = calculate_true_discount(card.text)
                    if price and mrp:
                        deals.append({
                            "id": f"{self._platform_id}_{prod_id}",
                            "title": title,
                            "price": price,
                            "mrp": mrp,
                            "discount": true_discount,
                            "image_url": img_url,
                            "url": raw_url,
                            "is_lightning": False
                        })
                except Exception as card_err:
                    continue
        except Exception as e:
            logging.error(f"Error in Generic Scraper for {self._platform_id}: {e}")
            
        return deals
