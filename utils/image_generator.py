import os
import logging
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH_DIR = os.path.join(BASE_DIR, "scratch")

def generate_deal_image(unique_id: str, platform: str, title: str, price: int, mrp: int, discount: float, original_image_url: str, is_verified_low: bool, deal_score: float) -> str:
    """
    Downloads the product image, overlays MD3 liquid styled deal details (Price, MRP, Discount, Deal Score),
    and saves a 800x800 verification card in the scratch/ folder.
    Returns the absolute path to the generated image file.
    """
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    out_file = os.path.join(SCRATCH_DIR, f"deal_card_{unique_id}.jpg")
    
    # 1. Initialize 800x800 Canvas with MD3 Dark Theme Background
    canvas = Image.new('RGB', (800, 800), color='#121824')
    draw = ImageDraw.Draw(canvas)
    
    # 2. Get high-quality system fonts on Windows
    font_path_bold = "C:\\Windows\\Fonts\\segoeuib.ttf" # Segoe UI Bold
    font_path_reg = "C:\\Windows\\Fonts\\segoeui.ttf"   # Segoe UI Regular
    
    if not os.path.exists(font_path_bold):
        font_path_bold = "C:\\Windows\\Fonts\\arial.ttf"
        font_path_reg = font_path_bold
        
    try:
        title_font = ImageFont.truetype(font_path_bold, 24)
        price_font = ImageFont.truetype(font_path_bold, 56)
        label_font = ImageFont.truetype(font_path_bold, 28)
        meta_font = ImageFont.truetype(font_path_reg, 20)
    except:
        title_font = ImageFont.load_default()
        price_font = title_font
        label_font = title_font
        meta_font = title_font

    # 3. Load & Process Product Image
    img_loaded = False
    if original_image_url and original_image_url.strip() != "":
        try:
            r = requests.get(original_image_url, timeout=10)
            if r.status_code == 200:
                prod_img = Image.open(BytesIO(r.content))
                # Convert to RGB if transparent/RGBA
                if prod_img.mode != 'RGB':
                    prod_img = prod_img.convert('RGB')
                
                # Resize keeping aspect ratio
                prod_img.thumbnail((500, 420), Image.Resampling.LANCZOS)
                
                # Paste centered horizontally
                x_pos = (800 - prod_img.width) // 2
                y_pos = 120 + (420 - prod_img.height) // 2
                canvas.paste(prod_img, (x_pos, y_pos))
                img_loaded = True
        except Exception as e:
            logging.error(f"Image generator download error: {e}")
            
    if not img_loaded:
        # Draw placeholder box
        draw.rectangle([150, 150, 650, 500], fill="#1c2438", outline="#2c3a58", width=2)
        draw.text((400, 320), "No Image Available", font=title_font, fill="#95a5a6", anchor="mm")

    # 4. Draw Header Badges & Branding
    is_amazon = "amazon" in platform.lower()
    header_text = "🍊 AMAZON DEALS" if is_amazon else "💣 FLIPKART LOOT"
    draw.text((40, 40), header_text, font=title_font, fill="#ff9900" if is_amazon else "#2874f0")
    draw.text((760, 40), "LOOT RAIDERS AI", font=title_font, fill="#958f99", anchor="ra")
    
    # 5. Draw Dynamic Price/Discount banner at bottom (y = 560 to 760)
    draw.rectangle([40, 560, 760, 760], fill="#1c2438", outline="#2c3a58", width=2)
    
    # Pricing info
    draw.text((60, 580), f"₹{price:,}", font=price_font, fill="#2ecc71")
    draw.text((60, 645), f"MRP: ₹{mrp:,}", font=meta_font, fill="#95a5a6")
    
    # Discount Badge
    disc_text = f"{int(discount)}% OFF"
    draw.rectangle([280, 595, 450, 645], fill="#e74c3c")
    draw.text((365, 620), disc_text, font=label_font, fill="#ffffff", anchor="mm")
    
    # Deal score Badge
    score_text = f"SCORE: {int(deal_score)}/100"
    draw.rectangle([470, 595, 740, 645], fill="#ff9900")
    draw.text((605, 620), score_text, font=label_font, fill="#ffffff", anchor="mm")
    
    # 6. Draw Verified Low / Glitch Alert Banner
    is_glitch = discount >= 75.0
    if is_glitch:
        alert_bg = "#ff003c"
        alert_lbl = "🚨 DANGER: GLITCH PRICE ERROR DETECTED 🚨"
    elif is_verified_low:
        alert_bg = "#00b894"
        alert_lbl = "🔥 VERIFIED ALL-TIME LOW PRICE 🔥"
    else:
        alert_bg = "#0984e3"
        alert_lbl = "✨ VERIFIED PRICE DROP ✨"
        
    draw.rectangle([40, 500, 760, 545], fill=alert_bg)
    draw.text((400, 522), alert_lbl, font=title_font, fill="#ffffff", anchor="mm")
    
    # 7. Draw product Title (truncated safely)
    clean_title = title.split('\n')[0].strip()
    if len(clean_title) > 55:
        clean_title = clean_title[:52] + "..."
    draw.text((60, 700), clean_title, font=meta_font, fill="#ffffff")
    
    # Save file
    try:
        canvas.save(out_file, "JPEG", quality=85)
        logging.info(f"Composite deal verification image card generated: {out_file}")
        return out_file
    except Exception as e:
        logging.error(f"Failed to save image card: {e}")
        return None
