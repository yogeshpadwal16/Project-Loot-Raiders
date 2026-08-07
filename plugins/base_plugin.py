from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseRetailerPlugin(ABC):
    @property
    @abstractmethod
    def retailer_id(self) -> str:
        """
        Returns the unique platform identifier (e.g., 'amazon_master_lightning_deals').
        """
        pass
        
    @abstractmethod
    def extract_deals(self, driver, config: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Takes a selenium driver session and configuration options.
        Navigates, scrolls, crawls elements, and returns a list of standardized deal dictionaries.
        
        Returned dict items schema:
          - 'id': str (uniquely generated product ID like ASIN or Flipkart PID)
          - 'title': str
          - 'price': int
          - 'mrp': int
          - 'discount': float
          - 'image_url': str
          - 'url': str
          - 'is_lightning': bool
        """
    def scrape_details(self, driver, url: str) -> Dict[str, Any]:
        """
        Takes a selenium/playwright driver and product URL, navigates to the page,
        and extracts standardized product details (title, price, mrp, image_url, etc.).
        """
        import re
        import time
        import logging
        
        driver.get(url)
        time.sleep(3)  # Reduced wait time for browser fallback to fully load
        
        title = ""
        price = 0
        mrp = 0
        image_url = ""
        platform = self.retailer_id
        
        def clean_number(txt):
            try:
                txt = txt.replace(',', '').split('.')[0]
                nums = re.findall(r'\d+', txt)
                if nums:
                    return int(nums[0])
            except Exception:
                pass
            return 0
            
        # Standard CSS selector patterns for e-commerce stores
        if platform == "amazon":
            # Extract Title
            for s in ["#productTitle", ".qa-title-text", "span.a-size-large.product-title-word-break"]:
                elem = driver.select(s)
                if elem:
                    title = elem.inner_text().strip()
                    break
            # Extract Price
            for s in [".a-price-whole", "span.priceToPay span.a-price-whole", "#priceblock_ourprice", "#priceblock_dealprice"]:
                elem = driver.select(s)
                if elem:
                    price = clean_number(elem.inner_text())
                    if price > 0: break
            # Extract MRP
            for s in ["span.a-price.a-text-price span.a-offscreen", ".basisPrice .a-offscreen", "#listPrice"]:
                elem = driver.select(s)
                if elem:
                    mrp = clean_number(elem.inner_text())
                    if mrp > 0: break
            # Extract Image URL
            for s in ["#landingImage", "#imgBlkFront", "img#main-image"]:
                elem = driver.select(s)
                if elem:
                    image_url = elem.get_attribute("src")
                    break
                    
        elif platform == "flipkart":
            # Extract Title
            for s in ["span.B_NuCI", "h1.yhB1nd", ".B_NuCI"]:
                elem = driver.select(s)
                if elem:
                    title = elem.inner_text().strip()
                    break
            # Extract Price
            for s in ["div._30jeq3._16Jk6d", "div.Nx9378", "div._30jeq3"]:
                elem = driver.select(s)
                if elem:
                    price = clean_number(elem.inner_text())
                    if price > 0: break
            # Extract MRP
            for s in ["div._3I9_ww", "div.y3EhuJ", "div._3I9_ww"]:
                elem = driver.select(s)
                if elem:
                    mrp = clean_number(elem.inner_text())
                    if mrp > 0: break
            # Extract Image URL
            for s in ["img._396cs4._2amPTt._3qX052", "img._2r_Ty1", "img.jKmZBy", "img._396cs4"]:
                elem = driver.select(s)
                if elem:
                    image_url = elem.get_attribute("src")
                    break
                    
        elif platform == "myntra":
            # Extract Title
            for s in ["h1.pdp-title", "h1.pdp-name", ".pdp-name"]:
                elem = driver.select(s)
                if elem:
                    title = elem.inner_text().strip()
                    break
            # Extract Price
            for s in ["span.pdp-price", "strong.pdp-price"]:
                elem = driver.select(s)
                if elem:
                    price = clean_number(elem.inner_text())
                    if price > 0: break
            # Extract MRP
            for s in ["span.pdp-mrp", "span.pdp-discount"]:
                elem = driver.select(s)
                if elem:
                    mrp = clean_number(elem.inner_text())
                    if mrp > 0: break
            # Extract Image URL
            for s in ["img.pdp-modimage", "div.image-grid-image"]:
                elem = driver.select(s)
                if elem:
                    style = elem.get_attribute("style") or ""
                    m = re.search(r'url\("?(.*?)"?\)', style)
                    image_url = m.group(1) if m else elem.get_attribute("src")
                    break
                    
        elif platform == "ajio":
            # Extract Title
            for s in ["h1.prod-name", ".prod-name"]:
                elem = driver.select(s)
                if elem:
                    title = elem.inner_text().strip()
                    break
            # Extract Price
            for s in ["div.prod-sp", ".prod-sp"]:
                elem = driver.select(s)
                if elem:
                    price = clean_number(elem.inner_text())
                    if price > 0: break
            # Extract MRP
            for s in ["span.prod-cp", ".prod-cp"]:
                elem = driver.select(s)
                if elem:
                    mrp = clean_number(elem.inner_text())
                    if mrp > 0: break
            # Extract Image URL
            for s in ["img.rilrtl-lazy-img.prod-main-image", "img.rilrtl-lazy-img"]:
                elem = driver.select(s)
                if elem:
                    image_url = elem.get_attribute("src")
                    break
                    
        elif platform == "meesho":
            # Extract Title
            for s in ["span.ProductWeb__ProductName-sc-7813a8-0", "h1", "span[class*='ProductName']"]:
                elem = driver.select(s)
                if elem:
                    title = elem.inner_text().strip()
                    break
            # Extract Price
            for s in ["h4.ProductWeb__ProductPrice-sc-7813a8-1", "h4", "h4[class*='ProductPrice']"]:
                elem = driver.select(s)
                if elem:
                    price = clean_number(elem.inner_text())
                    if price > 0: break
            # Extract MRP
            for s in ["p.ProductWeb__ProductOriginalPrice-sc-7813a8-2", "p[class*='OriginalPrice']"]:
                elem = driver.select(s)
                if elem:
                    mrp = clean_number(elem.inner_text())
                    if mrp > 0: break
            if mrp == 0 and price > 0:
                mrp = int(price * 1.3) # fallback estimation
            # Extract Image URL
            for s in ["img[class*='ProductImage']", "img.ProductWeb__ProductImage-sc-7813a8-3", "img"]:
                elem = driver.select(s)
                if elem:
                    image_url = elem.get_attribute("src")
                    break
                    
        elif platform == "tatacliq":
            # Extract Title
            for s in ["h1.ProductDetails__productName", "h1"]:
                elem = driver.select(s)
                if elem:
                    title = elem.inner_text().strip()
                    break
            # Extract Price
            for s in ["h3.ProductDetails__sellingPrice", "h3"]:
                elem = driver.select(s)
                if elem:
                    price = clean_number(elem.inner_text())
                    if price > 0: break
            # Extract MRP
            for s in ["span.ProductDetails__mrpPrice", "span.ProductDetails__strikePrice"]:
                elem = driver.select(s)
                if elem:
                    mrp = clean_number(elem.inner_text())
                    if mrp > 0: break
            if mrp == 0 and price > 0:
                mrp = int(price * 1.25)
            # Extract Image URL
            for s in ["img.ProductDetails__image", "img.ProductImage"]:
                elem = driver.select(s)
                if elem:
                    image_url = elem.get_attribute("src")
                    break
                    
        elif platform == "jiomart":
            # Extract Title
            for s in ["div.product-header-name", "h1#pdp_product_name", "div.j-text-heading-xs"]:
                elem = driver.select(s)
                if elem:
                    title = elem.inner_text().strip()
                    break
            # Extract Price
            for s in ["span#pdp_selling_price", "span.j-text-heading-m", "span.price"]:
                elem = driver.select(s)
                if elem:
                    price = clean_number(elem.inner_text())
                    if price > 0: break
            # Extract MRP
            for s in ["span#pdp_mrp", "span.strike-price", "span.mrp"]:
                elem = driver.select(s)
                if elem:
                    mrp = clean_number(elem.inner_text())
                    if mrp > 0: break
            if mrp == 0 and price > 0:
                mrp = int(price * 1.2)
            # Extract Image URL
            for s in ["img#pdp_main_image", "img.product-image-zoom", "img"]:
                elem = driver.select(s)
                if elem:
                    image_url = elem.get_attribute("src")
                    break

        # Fallback to general generic meta tags if selectors missed
        if not title:
            for tag in ["meta[property='og:title']", "meta[name='twitter:title']", "title"]:
                elem = driver.select(tag)
                if elem:
                    title = elem.get_attribute("content") or elem.inner_text()
                    if title:
                        title = title.strip()
                        break

        if not image_url:
            for tag in ["meta[property='og:image']", "meta[name='twitter:image']"]:
                elem = driver.select(tag)
                if elem:
                    image_url = elem.get_attribute("content")
                    if image_url: break

        # Extract ratings & reviews metadata
        rating = None
        reviews = None
        for s in ["span.a-icon-alt", "div.score", "[data-star-rating]", "span.rating-number"]:
            try:
                elem = driver.select(s)
                if elem:
                    m = re.search(r'([1-5](?:\.\d)?)', elem.inner_text())
                    if m:
                        rating = float(m.group(1))
                        break
            except Exception:
                pass

        for s in ["span#acrCustomerReviewText", "span.ratings-count", "span.reviews-count"]:
            try:
                elem = driver.select(s)
                if elem:
                    m = re.search(r'([\d,]+)', elem.inner_text())
                    if m:
                        reviews = int(m.group(1).replace(',', ''))
                        break
            except Exception:
                pass

        # Extract bank offers & coupons
        bank_offers = []
        coupon_detail = ""
        has_bank_offer = False

        try:
            elements = driver.select_all("span.bank-offer-text, .offer-card, #bankOffers, [class*='bank-offer']")
            for el in elements:
                text = el.inner_text().strip()
                if text and len(text) > 10 and text not in bank_offers:
                    bank_offers.append(text)
                    has_bank_offer = True
        except Exception:
            pass

        try:
            coupon_elem = driver.select("#couponRules, .coupon-details, [class*='coupon-code']")
            if coupon_elem:
                coupon_detail = coupon_elem.inner_text().strip()
        except Exception:
            pass

        review_grade = "N/A"
        if rating is not None:
            if rating >= 4.5:
                review_grade = "A"
            elif rating >= 4.1:
                review_grade = "B"
            elif rating >= 3.7:
                review_grade = "C"
            elif rating >= 3.3:
                review_grade = "D"
            else:
                review_grade = "F"
                
            if reviews and reviews > 1000 and review_grade in ["A", "B", "C"]:
                review_grade += "+"
            elif reviews and reviews < 15:
                review_grade += " (Low Sample)"
            
        if image_url:
            image_url = image_url.strip()
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            if "amazon" in image_url.lower():
                image_url = re.sub(r'\._[a-zA-Z0-9_-]+_(?=\.[a-zA-Z]+$)', '._AC_SL1500_', image_url)
            elif "flipkart" in image_url.lower():
                image_url = re.sub(r'/image/\d+/\d+/', '/image/832/832/', image_url)
            
        return {
            "platform": platform,
            "title": title,
            "price": price,
            "mrp": mrp,
            "image_url": image_url,
            "rating": rating,
            "reviews": reviews,
            "has_bank_offer": has_bank_offer or bool(bank_offers),
            "bank_offers": bank_offers[:3],
            "coupon_detail": coupon_detail,
            "review_grade": review_grade
        }

    def load_page_with_retries(self, driver, url: str, max_retries: int = 3, delay: float = 3.0) -> bool:
        """
        Loads the specified URL in selenium with automatic retries and backoff.
        """
        import time
        import logging
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"[{self.retailer_id.upper()} Plugin] Loading URL (Attempt {attempt}/{max_retries}): {url}")
                driver.get(url)
                time.sleep(delay)
                return True
            except Exception as e:
                logging.warning(f"[{self.retailer_id.upper()} Plugin] Failed to load page (Attempt {attempt}): {e}")
                if attempt < max_retries:
                    time.sleep(delay * attempt)
        return False
