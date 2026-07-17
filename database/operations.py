import time
import re
import urllib.parse
import logging
from selenium.webdriver.common.by import By
from database.db_session import SessionLocal
from knowledge_base.models import Product, PriceHistory, ClickLog, SelectorMatrix
from deal_engine.scorer import calculate_deal_score
from config.settings import load_settings

def initialize_database_selectors():
    db = SessionLocal()
    try:
        import json
        import os
        from config.settings import BASE_DIR
        selectors_path = os.path.join(BASE_DIR, "selectors.json")
        loaded_selectors = {}
        if os.path.exists(selectors_path):
            try:
                with open(selectors_path, "r", encoding="utf-8") as f:
                    loaded_selectors = json.load(f)
                logging.info("Successfully loaded custom selectors from selectors.json")
            except Exception as load_err:
                logging.warning(f"Failed to load selectors.json: {load_err}")

        default_matrix = {
            "amazon_master_lightning_deals": {
                "url": "https://www.amazon.in/gp/goldbox?pct-off=35-",
                "card_selector": "div[data-testid='product-card'], div[class*='ProductCard-module__card']",
                "title_selector": "span.a-truncate-full, .a-truncate-full",
                "link_selector": "a[data-testid='product-card-link'], a.a-link-normal",
                "image_selector": "img[class*='ProductCardImage-module__image'], img"
            },
            "amazon_sitewide_search_deals": {
                "url": "https://www.amazon.in/s?k=deals+of+the+day&pct-off=40-",
                "card_selector": "div[data-component-type='s-search-result']",
                "title_selector": "h2 span",
                "link_selector": "a.a-link-normal",
                "image_selector": "img.s-image"
            },
            "amazon_electronics_deals": {
                "url": "https://www.amazon.in/s?k=electronics&pct-off=30-",
                "card_selector": "div[data-component-type='s-search-result']",
                "title_selector": "h2 span",
                "link_selector": "a.a-link-normal",
                "image_selector": "img.s-image"
            },
            "amazon_appliances_deals": {
                "url": "https://www.amazon.in/s?k=home+appliances&pct-off=30-",
                "card_selector": "div[data-component-type='s-search-result']",
                "title_selector": "h2 span",
                "link_selector": "a.a-link-normal",
                "image_selector": "img.s-image"
            },
            "flipkart_sitewide_offers": {
                "url": "https://www.flipkart.com/search?q=offers&p%5B%5D=facets.discount_range_v1%255B%255D%3D40%2525%2Bor%2Bmore",
                "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
                "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
                "link_selector": "a",
                "image_selector": "img"
            },
            "flipkart_clearance_master_feed": {
                "url": "https://www.flipkart.com/search?q=clearance sale",
                "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
                "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
                "link_selector": "a",
                "image_selector": "img"
            },
            "flipkart_electronics_deals": {
                "url": "https://www.flipkart.com/search?q=electronics&p%5B%5D=facets.discount_range_v1%255B%255D%3D30%2525%2Bor%2Bmore",
                "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
                "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
                "link_selector": "a",
                "image_selector": "img"
            },
            "flipkart_appliances_deals": {
                "url": "https://www.flipkart.com/search?q=appliances&p%5B%5D=facets.discount_range_v1%255B%255D%3D30%2525%2Bor%2Bmore",
                "card_selector": "div[style*='flex'], div[data-id], div._1AtVbE, div.cPHR1N, div.slAVV4, div._1sdMkc, div._4ddWXP",
                "title_selector": "a, div.KzDlHZ, a.IRpwTa, a.wjcEwN",
                "link_selector": "a",
                "image_selector": "img"
            },
            "myntra_deals": {
                "url": "https://www.myntra.com/deals?f=discount%3A50.0",
                "card_selector": "li.product-base",
                "title_selector": "h4.product-product, h3.product-brand",
                "link_selector": "a",
                "image_selector": "img"
            },
            "ajio_deals": {
                "url": "https://www.ajio.com/s/discount-50-percent-and-above",
                "card_selector": "div.item",
                "title_selector": "div.name",
                "link_selector": "a",
                "image_selector": "img"
            },
            "meesho_deals": {
                "url": "https://www.meesho.com/search?q=offers",
                "card_selector": "a[href*='/p/']",
                "title_selector": "p[class*='ProductTitle']",
                "link_selector": "a",
                "image_selector": "img"
            },
            "tatacliq_deals": {
                "url": "https://www.tatacliq.com/search/?text=deals",
                "card_selector": "a.ProductModule__base, [class*='ProductModule__base']",
                "title_selector": "h2.ProductDescription__description, [class*='ProductDescription__description']",
                "link_selector": "a",
                "image_selector": "img"
            },
            "jiomart_deals": {
                "url": "https://www.jiomart.com/collection/basic-electricals1",
                "card_selector": "div.productContainer, div.productCard__productCard",
                "title_selector": "h3.productCard__productTitle",
                "link_selector": "a",
                "image_selector": "img"
            }
        }
        # Override with loaded selectors from selectors.json
        for plat_key, custom_config in loaded_selectors.items():
            if plat_key in default_matrix:
                default_matrix[plat_key].update(custom_config)
            else:
                default_matrix[plat_key] = custom_config

        for plat_key, config in default_matrix.items():
            existing = db.query(SelectorMatrix).filter_by(platform=plat_key).first()
            if not existing:
                existing = SelectorMatrix(platform=plat_key)
                db.add(existing)
            existing.url = config.get("url", "")
            existing.card_selector = config.get("card_selector", "")
            existing.title_selector = config.get("title_selector", "")
            existing.link_selector = config.get("link_selector", "")
            existing.image_selector = config.get("image_selector", "")
        db.commit()
        logging.info("Default scrapers selector matrix bootstrapped/updated in database.")
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to bootstrap selector matrix in DB: {e}")
    finally:
        db.close()

def save_deal_to_db(platform: str, title: str, price: int, mrp: int, discount: float, img_url: str, final_url: str, is_verified_low: bool, unique_id: str, deal_score: float = 0.0):
    db = SessionLocal()
    try:
        product = db.query(Product).filter_by(id=unique_id).first()
        if not product:
            product = Product(
                id=unique_id,
                platform=platform,
                title=title,
                image_url=img_url,
                url=final_url
            )
            db.add(product)
            db.flush()
        else:
            # Keep details up-to-date
            product.title = title
            product.image_url = img_url
            product.url = final_url
        
        price_hist = PriceHistory(
            product_id=unique_id,
            price=price,
            mrp=mrp,
            discount=discount,
            is_verified_low=is_verified_low,
            deal_score=deal_score,
            timestamp=time.time()
        )
        db.add(price_hist)
        db.commit()
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to save deal to database: {e}")
    finally:
        db.close()

def log_click_to_db(deal_id: str, title: str, ip: str, user: str, user_agent: str):
    db = SessionLocal()
    try:
        click = ClickLog(
            product_id=deal_id,
            title=title,
            ip=ip,
            user=user,
            user_agent=user_agent,
            timestamp=time.time()
        )
        db.add(click)
        db.commit()
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to log click to database: {e}")
    finally:
        db.close()

def verify_historical_low(driver, product_url: str, current_price: int, unique_id: str = None, discount: float = 0.0) -> bool:
    # If the platform is not Amazon or Flipkart, we cannot query buyhatke, so we default to True
    is_supported = any(r in product_url.lower() for r in ["amazon", "flipkart"])
    if not is_supported:
        return True
        
    historical_prices = []
    try:
        encoded_url = urllib.parse.quote_plus(product_url)
        tracker_query_url = f"https://price.buyhatke.com/products.php?url={encoded_url}"
        
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.set_page_load_timeout(5)
        try:
            driver.get(tracker_query_url)
            time.sleep(1.5)
            page_text = driver.find_element(By.TAG_NAME, "body").text.replace(',', '')
            historical_prices = [int(n) for n in re.findall(r'(?:Rs\.?|₹)\s*([0-9]+)', page_text)]
        except:
            historical_prices = []
            
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
    except:
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except:
            pass

    # If external tracker succeeded, use its data
    if historical_prices:
        lowest_ever = min(historical_prices)
        highest_ever = max(historical_prices)
        
        is_near_low = current_price <= (lowest_ever * 1.05)
        has_real_drop = False
        if highest_ever > current_price:
            drop_from_peak = ((highest_ever - current_price) / highest_ever) * 100
            if drop_from_peak >= 15.0:
                has_real_drop = True
                
        if is_near_low and has_real_drop:
            return True
        return False
        
    # Fallback 1: Compare against our local historical deals database
    if unique_id:
        db = SessionLocal()
        try:
            prices = db.query(PriceHistory.price).filter_by(product_id=unique_id).all()
            if prices:
                prices_list = [p[0] for p in prices]
                min_price = min(prices_list)
                max_price = max(prices_list)
                
                is_near_low = current_price <= min_price
                has_real_drop = False
                if max_price > current_price:
                    drop_from_peak = ((max_price - current_price) / max_price) * 100
                    if drop_from_peak >= 15.0:
                        has_real_drop = True
                        
                if is_near_low and has_real_drop:
                    return True
        except Exception as e:
            logging.error(f"Local price check failed: {e}")
        finally:
            db.close()
            
    return True

def update_selector_in_db_and_json(platform: str, card_selector=None, title_selector=None, link_selector=None, image_selector=None):
    import json
    import os
    db = SessionLocal()
    try:
        matrix = db.query(SelectorMatrix).filter_by(platform=platform).first()
        if not matrix:
            matrix = SelectorMatrix(platform=platform)
            db.add(matrix)
            
        if card_selector: matrix.card_selector = card_selector
        if title_selector: matrix.title_selector = title_selector
        if link_selector: matrix.link_selector = link_selector
        if image_selector: matrix.image_selector = image_selector
        db.commit()
        logging.info(f"Updated selector in database for {platform}")
        
        # Now update selectors.json
        from config.settings import BASE_DIR
        selectors_path = os.path.join(BASE_DIR, "selectors.json")
        data = {}
        if os.path.exists(selectors_path):
            try:
                with open(selectors_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                pass
                
        if platform not in data:
            data[platform] = {}
        if matrix.url: data[platform]["url"] = matrix.url
        data[platform]["card_selector"] = matrix.card_selector
        data[platform]["title_selector"] = matrix.title_selector
        data[platform]["link_selector"] = matrix.link_selector
        data[platform]["image_selector"] = matrix.image_selector
        
        with open(selectors_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logging.info(f"Updated selectors.json for {platform}")
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to update selectors: {e}")
    finally:
        db.close()

