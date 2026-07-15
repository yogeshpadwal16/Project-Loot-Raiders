import re
import time
import logging
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from plugins.base_plugin import BaseRetailerPlugin
from utils.parser import extract_amazon_asin, calculate_true_discount

class AmazonRetailerPlugin(BaseRetailerPlugin):
    @property
    def retailer_id(self) -> str:
        return "amazon"

    def extract_deals(self, driver, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        deals = []
        amazon_tag = settings.get("amazon_tag", "lootraiders-21")
        
        try:
            driver.get(config['url'])
            time.sleep(4)
            
            # Simulated human scrolling
            for scroll in range(1, 6):
                driver.execute_script(f"window.scrollTo(0, {scroll * 500});")
                time.sleep(1.5)
                
            cards = driver.find_elements(By.CSS_SELECTOR, config['card_selector'])
            logging.info(f"[Amazon Plugin] Found {len(cards)} elements using card selector.")
            
            for card in cards:
                try:
                    # 1. Extract Target URL
                    links = card.find_elements(By.TAG_NAME, "a")
                    raw_url = None
                    for l in links:
                        href = l.get_attribute("href")
                        if href and ("javascript" not in href) and ("/dp/" in href or "product" in href):
                            raw_url = href
                            break
                    if not raw_url and links:
                        raw_url = links[0].get_attribute("href")
                        
                    if not raw_url:
                        continue
                        
                    asin = extract_amazon_asin(raw_url)
                    if not asin:
                        continue
                        
                    clean_base_url = f"https://www.amazon.in/dp/{asin}"
                    final_url = f"{clean_base_url}?tag={amazon_tag}"
                    
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
                            "id": asin,
                            "title": title,
                            "price": price,
                            "mrp": mrp,
                            "discount": true_discount,
                            "image_url": img_url,
                            "url": final_url,
                            "is_lightning": "lightning" in config['url'].lower()
                        })
                except Exception as card_err:
                    continue
        except Exception as e:
            logging.error(f"Error in Amazon plugin crawling: {e}")
            
        return deals
