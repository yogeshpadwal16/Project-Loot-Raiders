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
    # Pre-strip percentage discounts so they don't concatenate with price numbers
    clean_text = re.sub(r'[0-9]{1,2}\s*%\s*(?:off)?', ' ', text_content, flags=re.IGNORECASE)
    # Remove comma separators
    clean_text = clean_text.replace(',', '')
    
    # Matches currency numbers
    numbers = [int(n) for n in re.findall(r'(?:₹|Rs\.?)\s*([0-9]+)', clean_text)]
    if len(numbers) < 2:
        numbers = [int(n) for n in re.findall(r'\b[0-9]{2,7}\b', clean_text) if int(n) > 49]

    if len(numbers) < 2:
        return None, None, None
        
    selling_price = numbers[0]
    mrp = max(numbers)
    
    if mrp == 0 or selling_price >= mrp:
        return None, None, None
        
    true_discount = ((mrp - selling_price) / mrp) * 100
    return selling_price, mrp, true_discount

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
