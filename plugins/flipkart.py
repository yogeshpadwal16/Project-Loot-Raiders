import re
import time
import logging
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from plugins.base_plugin import BaseRetailerPlugin
from utils.parser import extract_flipkart_pid
from extractors.flipkart import (
    sanitize_flipkart_title,
    is_generic_or_search_title,
    upgrade_flipkart_image_url,
    parse_clean_price,
)

class FlipkartRetailerPlugin(BaseRetailerPlugin):
    @property
    def retailer_id(self) -> str:
        return "flipkart"

    def extract_deals(self, driver, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        deals = []
        flipkart_affid = (os.environ.get("FLIPKART_AFFID") or settings.get("flipkart_affid") or "lootraiders").strip()
        if flipkart_affid == "YOUR_FLIPKART_AFFILIATE_ID" or flipkart_affid == "":
            flipkart_affid = "lootraiders"
        min_discount_setting = float(settings.get("min_discount", 30.0))
        
        try:
            if not self.load_page_with_retries(driver, config['url'], delay=4.0):
                logging.error(f"[Flipkart Plugin] Failed to load target URL: {config['url']}")
                return []
            
            # Simulated human scrolling
            for scroll in range(1, 6):
                driver.execute_script(f"window.scrollTo(0, {scroll * 500});")
                time.sleep(1.5)
                
            cards = driver.find_elements(By.CSS_SELECTOR, config.get('card_selector', "div[data-id], div._1AtVbE, div.slAVV4, div._1sdMkc"))
            logging.info(f"[Flipkart Plugin] Found {len(cards)} elements using card selector.")
            
            for card in cards:
                try:
                    # 1. Extract Target URL
                    links = card.find_elements(By.TAG_NAME, "a")
                    raw_url = None
                    for l in links:
                        href = l.get_attribute("href")
                        if href and ("javascript" not in href) and ("/p/" in href or "pid=" in href):
                            if "/pr" not in href and "/search" not in href and "/s/" not in href and "/c/" not in href:
                                raw_url = href
                                break
                    if not raw_url and links:
                        first_href = links[0].get_attribute("href")
                        if first_href and "/pr" not in first_href and "/search" not in first_href and "/s/" not in first_href and "/c/" not in first_href:
                            raw_url = first_href
                        
                    if not raw_url:
                        continue
                        
                    pid = extract_flipkart_pid(raw_url)
                    if not pid:
                        import hashlib
                        pid = hashlib.md5(raw_url.encode()).hexdigest()[:16]
                        
                    if raw_url and not raw_url.startswith("http"):
                        raw_url = f"https://www.flipkart.com{raw_url}" if raw_url.startswith("/") else f"https://www.flipkart.com/{raw_url}"
                    
                    if flipkart_affid and "affid=" not in raw_url:
                        sep = "&" if "?" in raw_url else "?"
                        final_url = f"{raw_url}{sep}affid={flipkart_affid}"
                    else:
                        final_url = raw_url
                    
                    # 2. Extract Title with Guardrails against Search Terms
                    title = ""
                    title_selectors = [
                        config.get('title_selector', ''),
                        "span.VU-ZEz", "h1.B_NuCI", "span.VU-ZEg", "a.wjcEIp", "a.WKTcLC", "a.IRpwTa", "div._2W9tVh"
                    ]
                    for t_sel in title_selectors:
                        if not t_sel: continue
                        try:
                            t_el = card.find_element(By.CSS_SELECTOR, t_sel)
                            t_val = t_el.get_attribute("title") or t_el.get_attribute("textContent")
                            if t_val and len(t_val.strip()) > 5 and not is_generic_or_search_title(t_val):
                                title = sanitize_flipkart_title(t_val)
                                break
                        except Exception:
                            pass
                        
                    if not title or title.endswith("..."):
                        try:
                            for a_el in card.find_elements(By.TAG_NAME, "a"):
                                t_attr = a_el.get_attribute("title")
                                if t_attr and len(t_attr) > len(title) and not is_generic_or_search_title(t_attr):
                                    title = sanitize_flipkart_title(t_attr)
                                    break
                        except Exception:
                            pass
                            
                    if not title or is_generic_or_search_title(title) or len(title) < 5:
                        continue
                        
                    # 3. Extract High-Res Primary Hero Image
                    img_url = ""
                    img_selectors = [
                        config.get('image_selector', ''),
                        "img.DByuf4", "img._396cs4", "div._2r_T1I img", "img._53G4pf", "img.UCad5S", "img.vU5WPQ"
                    ]
                    for i_sel in img_selectors:
                        if not i_sel: continue
                        try:
                            i_el = card.find_element(By.CSS_SELECTOR, i_sel)
                            srcset = i_el.get_attribute("srcset")
                            if srcset:
                                parts = [p.strip().split()[0] for p in srcset.split(",") if p.strip()]
                                if parts:
                                    cand = upgrade_flipkart_image_url(parts[-1])
                                    if cand:
                                        img_url = cand
                                        break
                            for attr in ["data-src", "src", "data-original"]:
                                val = i_el.get_attribute(attr)
                                if val:
                                    cand = upgrade_flipkart_image_url(val)
                                    if cand:
                                        img_url = cand
                                        break
                            if img_url: break
                        except Exception:
                            pass
                        
                    # 4. Extract Accurate Selling Price & Strike-Through MRP
                    price = None
                    mrp = None
                    
                    price_selectors = ["div.Nx9bqj", "div._30jeq3", "div.hlbKVd", "div.Nx9bqj.CxhGGd"]
                    for p_sel in price_selectors:
                        try:
                            p_el = card.find_element(By.CSS_SELECTOR, p_sel)
                            p_val = parse_clean_price(p_el.text or p_el.get_attribute("textContent"))
                            if p_val:
                                price = p_val
                                break
                        except Exception:
                            pass
                            
                    mrp_selectors = ["div.yRaY8j", "div._3I9_ww", "div._2p6JhP._30e3Er", "div.yRaY8j._18RivS"]
                    for m_sel in mrp_selectors:
                        try:
                            m_el = card.find_element(By.CSS_SELECTOR, m_sel)
                            m_val = parse_clean_price(m_el.text or m_el.get_attribute("textContent"))
                            if m_val:
                                mrp = m_val
                                break
                        except Exception:
                            pass
                            
                    if not price:
                        from utils.parser import calculate_true_discount
                        p_t, m_t, _ = calculate_true_discount(card.text)
                        price = p_t
                        if not mrp: mrp = m_t
                        
                    if price and mrp and mrp > price:
                        true_discount = round(((mrp - price) / mrp) * 100)
                    elif price and not mrp:
                        mrp = round(price * 1.35, 2)
                        true_discount = 26
                    else:
                        continue
                        
                    if price and mrp and (min_discount_setting <= true_discount <= 98):
                        from utils.parser import extract_rating_and_reviews, detect_bank_offers
                        rating, reviews = extract_rating_and_reviews(card.text)
                        has_bank_offer = detect_bank_offers(card.text)
                        deals.append({
                            "id": pid,
                            "title": title,
                            "price": price,
                            "mrp": mrp,
                            "discount": float(true_discount),
                            "image_url": img_url,
                            "url": final_url,
                            "is_lightning": False,
                            "rating": rating,
                            "reviews": reviews,
                            "has_bank_offer": has_bank_offer
                        })
                except Exception as card_err:
                    continue
        except Exception as e:
            logging.error(f"Error in Flipkart plugin crawling: {e}")
            
        return deals
