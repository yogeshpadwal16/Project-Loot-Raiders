import re
import time
import logging
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from plugins.base_plugin import BaseRetailerPlugin
from utils.parser import extract_flipkart_pid, calculate_true_discount

class FlipkartRetailerPlugin(BaseRetailerPlugin):
    @property
    def retailer_id(self) -> str:
        return "flipkart"

    def extract_deals(self, driver, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        deals = []
        flipkart_affid = settings.get("flipkart_affid", "YOUR_FLIPKART_AFFILIATE_ID")
        
        try:
            if not self.load_page_with_retries(driver, config['url'], delay=4.0):
                logging.error(f"[Flipkart Plugin] Failed to load target URL: {config['url']}")
                return []
            
            # Simulated human scrolling
            for scroll in range(1, 6):
                driver.execute_script(f"window.scrollTo(0, {scroll * 500});")
                time.sleep(1.5)
                
            cards = driver.find_elements(By.CSS_SELECTOR, config['card_selector'])
            logging.info(f"[Flipkart Plugin] Found {len(cards)} elements using card selector.")
            
            for card in cards:
                try:
                    # 1. Extract Target URL
                    links = card.find_elements(By.TAG_NAME, "a")
                    raw_url = None
                    for l in links:
                        href = l.get_attribute("href")
                        if href and ("javascript" not in href) and ("/p/" in href or "pid=" in href):
                            raw_url = href
                            break
                    if not raw_url and links:
                        raw_url = links[0].get_attribute("href")
                        
                    if not raw_url:
                        continue
                        
                    pid = extract_flipkart_pid(raw_url)
                    if not pid:
                        pid = str(hash(card.text[:40]))
                        
                    clean_base_url = f"https://www.flipkart.com/product/p/itm?pid={pid}"
                    final_url = raw_url if "affid=" in raw_url else f"{clean_base_url}&affid={flipkart_affid}"
                    
                    # 2. Extract Title
                    title = ""
                    try:
                        title_el = card.find_element(By.CSS_SELECTOR, config['title_selector'])
                        title = title_el.get_attribute("title")
                        if not title:
                            title = title_el.get_attribute("textContent").strip()
                        if title:
                            title = re.sub(r'\s+', ' ', title)
                    except:
                        pass
                        
                    if not title or title.endswith("...") or title.endswith(""):
                        try:
                            for a_el in card.find_elements(By.TAG_NAME, "a"):
                                t_attr = a_el.get_attribute("title")
                                if t_attr and len(t_attr) > len(title) and not (t_attr.endswith("...") or t_attr.endswith("")):
                                    title = re.sub(r'\s+', ' ', t_attr).strip()
                                    break
                        except:
                            pass
                            
                    if not title:
                        try:
                            blacklist = ["limited time deal", "deal of the day", "lowest price", "super deals", "bank offer", "only few left", "mobiles & accessories", "showing 1 -", "other colors/patterns", "colors/patterns", "other colors"]
                            for text_segment in card.text.split("\n"):
                                seg = text_segment.strip()
                                if (len(seg) > 15 
                                    and not seg.startswith("₹") 
                                    and "OFF" not in seg 
                                    and "%" not in seg
                                    and not any(b in seg.lower() for b in blacklist)):
                                    title = seg
                                    break
                        except:
                            pass
                            
                    if not title or len(title) < 5:
                        continue
                        
                    # 3. Extract Image
                    img_url = None
                    try:
                        img_element = card.find_element(By.CSS_SELECTOR, config['image_selector'])
                        for attr in ["src", "data-src", "srcset"]:
                            val = img_element.get_attribute(attr)
                            if val and "http" in val and "base64" not in val:
                                img_url = val
                                break
                    except:
                        pass
                        
                    # 4. Extract pricing
                    price, mrp, true_discount = calculate_true_discount(card.text)
                    if price and mrp and (30.0 <= true_discount <= 98.0):
                        deals.append({
                            "id": pid,
                            "title": title,
                            "price": price,
                            "mrp": mrp,
                            "discount": true_discount,
                            "image_url": img_url,
                            "url": final_url,
                            "is_lightning": False
                        })
                except Exception as card_err:
                    continue
        except Exception as e:
            logging.error(f"Error in Flipkart plugin crawling: {e}")
            
        return deals
