import re
import urllib.parse

def extract_amazon_asin(url: str) -> str:
    decoded_url = urllib.parse.unquote(url)
    match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', decoded_url)
    return match.group(1) if match else None

def extract_flipkart_pid(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if 'pid' in params:
        return params['pid'][0]
    match = re.search(r'pid=([a-zA-Z0-9]{16})', url)
    if match: return match.group(1)
    match_path = re.search(r'/p/([a-zA-Z0-9]{16})', url)
    if match_path: return match_path.group(1)
    return None

def calculate_true_discount(text_content: str):
    if not text_content:
        return None, None, None
        
    # 1. Clean up commas and spaces
    clean_text = text_content.replace(',', '')
    
    # 2. Strip percentage discounts (e.g. 50% OFF, 50%off) so they don't get matched
    clean_text = re.sub(r'[0-9]{1,3}\s*%\s*(?:off)?', ' ', clean_text, flags=re.IGNORECASE)
    
    # 3. Strip phone numbers, pincodes, dates, and other long numbers (> 7 digits)
    clean_text = re.sub(r'\b[0-9]{7,15}\b', ' ', clean_text)
    
    # 4. Strip ratings/reviews and other common non-price metrics
    # e.g. "4.2", "28007 Reviews", "1.2L", "50W", "100 pcs", "pack of 2"
    clean_text = re.sub(r'\b[0-9]+(?:\.[0-9]+)?\s*(?:rating|review|bought|sold|view|people|size|pack|pcs|item|qty|ml|l|w|v|ah|mah|gb|tb|mb|kb|hz|khz|mhz|cm|m|inch|in|ft|yd|g|kg|mg|oz|lbs|delivery|shipping|day|hour|min|sec|wk|yr)\w*\b', ' ', clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\b[0-9]+(?:\.[0-9]+)?\s*(?:\*|star|stars)\b', ' ', clean_text, flags=re.IGNORECASE)
    
    # 5. Extract currency-prefixed numbers first (₹ or Rs.)
    currency_numbers = [int(n) for n in re.findall(r'(?:₹|Rs\.?)\s*([0-9]+)', clean_text, flags=re.IGNORECASE)]
    
    # If we have 2 or more currency numbers, use them!
    if len(currency_numbers) >= 2:
        # Sort so we know which is selling price and which is MRP
        selling_price = currency_numbers[0]
        mrp = max(currency_numbers)
        if mrp > selling_price:
            true_discount = ((mrp - selling_price) / mrp) * 100
            return selling_price, mrp, true_discount
            
    # 6. Fallback to extracting all remaining numbers
    all_numbers = [int(n) for n in re.findall(r'\b[0-9]{2,6}\b', clean_text) if int(n) > 20]
    
    # If we have at least 2 numbers, try to find a valid pair
    if len(all_numbers) >= 2:
        selling_price = all_numbers[0]
        mrp = max(all_numbers)
        if mrp > selling_price:
            true_discount = ((mrp - selling_price) / mrp) * 100
            if true_discount < 96:
                return selling_price, mrp, true_discount
                
    # If we only have 1 currency number (e.g. selling price) and no clear MRP:
    if len(currency_numbers) == 1:
        return currency_numbers[0], currency_numbers[0], 0.0

    return None, None, None

def get_high_res_image_url(url: str) -> str:
    if not url:
        return url
    
    # 1. Clean Amazon Image CDN suffixes (e.g. ._AC_SF226,225_ -> original)
    if "amazon" in url.lower() or "media-amazon" in url.lower():
        # Match ._XXXX_ before the file extension
        url = re.sub(r"\._[A-Za-z0-9,_\-]+(?=\.\w+$)", "", url)
        # Match pattern ._SRXXX,YYY_
        url = re.sub(r"\._SR\d+,\d+_(?=\.\w+$)", "", url)
        return url
        
    # 2. Upgrade Flipkart Image CDN dimensions from /image/612/612/ to /image/832/832/
    if "flixcart" in url.lower():
        url = re.sub(r"/image/\d+/\d+/", "/image/832/832/", url)
        return url
        
    return url
