import os
import logging
import requests
import time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from database.db_session import SessionLocal
from knowledge_base.models import PriceHistory

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH_DIR = os.path.join(BASE_DIR, "scratch")

def generate_deal_image(unique_id: str, platform: str, title: str, price: int, mrp: int, discount: float, original_image_url: str, is_verified_low: bool, deal_score: float) -> str:
    """
    Downloads the product image, queries 90-day price history, overlays deal details,
    draws a price history sparkline with a filled gradient area, and saves a premium 800x900 card.
    Returns the absolute path to the generated image file.
    """
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    out_file = os.path.join(SCRATCH_DIR, f"deal_card_{unique_id}.jpg")
    
    # 1. Initialize 800x900 Canvas with MD3 Dark Theme Background
    canvas = Image.new('RGB', (800, 900), color='#0f172a') # Premium deep slate black
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
        tiny_font = ImageFont.truetype(font_path_reg, 16)
    except:
        title_font = ImageFont.load_default()
        price_font = title_font
        label_font = title_font
        meta_font = title_font
        tiny_font = title_font

    # Draw rounded container card for product image
    draw.rectangle([60, 100, 740, 460], fill="#1e293b", outline="#334155", width=2)

    # 3. Load & Process Product Image
    img_loaded = False
    if original_image_url and original_image_url.strip() != "":
        try:
            prod_img = None
            if original_image_url.startswith("data:image"):
                import base64
                header, encoded = original_image_url.split(",", 1)
                data = base64.b64decode(encoded)
                prod_img = Image.open(BytesIO(data))
            else:
                r = requests.get(original_image_url, timeout=10)
                if r.status_code == 200:
                    prod_img = Image.open(BytesIO(r.content))
                    
            if prod_img:
                if prod_img.mode != 'RGB':
                    prod_img = prod_img.convert('RGB')
                
                # Resize product image to fit card
                prod_img.thumbnail((480, 320), Image.Resampling.LANCZOS)
                
                x_pos = (800 - prod_img.width) // 2
                y_pos = 120 + (320 - prod_img.height) // 2
                canvas.paste(prod_img, (x_pos, y_pos))
                img_loaded = True
        except Exception as e:
            logging.error(f"Image generator download error: {e}")
            
    if not img_loaded:
        draw.text((400, 280), "No Image Available", font=title_font, fill="#94a3b8", anchor="mm")

    # 4. Draw Header Badges & Branding
    is_amazon = "amazon" in platform.lower()
    header_text = "🍊 AMAZON DEALS" if is_amazon else "💣 FLIPKART LOOT"
    draw.text((60, 40), header_text, font=title_font, fill="#f97316" if is_amazon else "#3b82f6")
    draw.text((740, 40), "LOOT RAIDERS AI", font=title_font, fill="#64748b", anchor="ra")
    
    # 5. Draw Verified Low / Glitch Alert Banner
    is_glitch = discount >= 75.0
    if is_glitch:
        alert_bg = "#ef4444"
        alert_lbl = "🚨 DANGER: GLITCH PRICE ERROR DETECTED 🚨"
    elif is_verified_low:
        alert_bg = "#10b981"
        alert_lbl = "🔥 VERIFIED ALL-TIME LOW PRICE 🔥"
    else:
        alert_bg = "#06b6d4"
        alert_lbl = "✨ VERIFIED PRICE DROP ✨"
        
    draw.rectangle([60, 480, 740, 525], fill=alert_bg)
    draw.text((400, 502), alert_lbl, font=title_font, fill="#ffffff", anchor="mm")

    # 6. Draw Dynamic Price/Discount banner at bottom (y = 540 to 860)
    draw.rectangle([60, 540, 740, 860], fill="#1e293b", outline="#334155", width=2)
    
    # Pricing info
    draw.text((80, 560), f"₹{price:,}", font=price_font, fill="#10b981")
    draw.text((80, 625), f"MRP: ₹{mrp:,}", font=meta_font, fill="#94a3b8")
    
    # Discount Badge
    disc_text = f"{int(discount)}% OFF"
    draw.rectangle([290, 575, 450, 625], fill="#ef4444")
    draw.text((370, 600), disc_text, font=label_font, fill="#ffffff", anchor="mm")
    
    # Deal score Badge
    score_text = f"SCORE: {int(deal_score)}/100"
    draw.rectangle([470, 575, 720, 625], fill="#f59e0b")
    draw.text((595, 600), score_text, font=label_font, fill="#ffffff", anchor="mm")
    
    # 7. Draw product Title (truncated safely)
    clean_title = title.split('\n')[0].strip()
    if len(clean_title) > 55:
        clean_title = clean_title[:52] + "..."
    draw.text((80, 665), clean_title, font=meta_font, fill="#ffffff")
    
    # Draw separating line
    draw.line([80, 705, 720, 705], fill="#334155", width=1)
    
    # 8. Query and Draw Price History Sparkline
    db = SessionLocal()
    prices_history = []
    try:
        history = db.query(PriceHistory).filter_by(product_id=unique_id).order_by(PriceHistory.timestamp.asc()).all()
        prices_history = [h.price for h in history]
    except Exception as db_err:
        logging.error(f"Error querying price history for image: {db_err}")
    finally:
        db.close()
        
    if not prices_history:
        prices_history = [mrp, price]
    elif len(prices_history) == 1:
        prices_history = [mrp, prices_history[0]]
        
    # Scale and draw graph (y = 730 to 820, height = 90)
    graph_x_start = 140
    graph_x_end = 660
    graph_y_start = 740
    graph_y_end = 830
    graph_width = graph_x_end - graph_x_start
    graph_height = graph_y_end - graph_y_start
    
    min_val = min(prices_history)
    max_val = max(prices_history)
    val_range = max_val - min_val if max_val != min_val else 1.0
    
    points = []
    for idx, val in enumerate(prices_history):
        px = graph_x_start + (idx / (len(prices_history) - 1)) * graph_width
        py = graph_y_end - ((val - min_val) / val_range) * graph_height
        points.append((px, py))
        
    # Draw graph grid lines
    draw.line([graph_x_start, graph_y_start, graph_x_start, graph_y_end], fill="#334155", width=1)
    draw.line([graph_x_start, graph_y_end, graph_x_end, graph_y_end], fill="#334155", width=1)
    
    # Draw filled gradient polygon representing the area under the sparkline
    if len(points) >= 2:
        try:
            overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            area_points = [(graph_x_start, graph_y_end)] + points + [(graph_x_end, graph_y_end)]
            overlay_draw.polygon(area_points, fill=(6, 182, 212, 40))
            canvas = Image.alpha_composite(canvas.convert('RGBA'), overlay).convert('RGB')
            draw = ImageDraw.Draw(canvas)
        except Exception as overlay_err:
            logging.error(f"Failed to draw transparent graph overlay: {overlay_err}")
            
    # Draw sparkline path
    if len(points) >= 2:
        draw.line(points, fill="#06b6d4", width=3) # Vibrant cyan sparkline
        # Draw dot markers at each point
        for px, py in points:
            draw.ellipse([px-4, py-4, px+4, py+4], fill="#ffffff", outline="#06b6d4", width=1)
            
    # Labels
    draw.text((graph_x_start - 10, graph_y_start + 10), f"₹{int(max_val)}", font=tiny_font, fill="#ef4444", anchor="rm")
    draw.text((graph_x_start - 10, graph_y_end - 10), f"₹{int(min_val)}", font=tiny_font, fill="#10b981", anchor="rm")
    draw.text((400, 848), "90-Day Verified Price Trend Graph", font=tiny_font, fill="#64748b", anchor="mm")
    
    # Save file
    try:
        canvas.save(out_file, "JPEG", quality=85)
        logging.info(f"Composite deal verification image card generated: {out_file}")
        return out_file
    except Exception as e:
        logging.error(f"Failed to save image card: {e}")
        return None
