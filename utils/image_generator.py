"""
utils/image_generator.py
High-Impact, Premium Social Deal Card Generator.
Renders visually striking 800x1000 branded image cards with glassmorphic cards,
price trajectory charts, deal score badges, and high-res product thumbnails.
"""

import os
import logging
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from database.db_session import SessionLocal
from knowledge_base.models import PriceHistory

logger = logging.getLogger("loot_raiders.image_generator")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH_DIR = os.path.join(BASE_DIR, "scratch")


def draw_sparkline_overlay(prod_img: Image.Image, price_history: list) -> Image.Image:
    """Draws a mini sparkline graph on the product thumbnail showing price trajectory."""
    img = prod_img.convert("RGBA")
    width, height = img.size

    if width < 80 or height < 80 or len(price_history) < 2:
        return img

    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    box_w = int(width * 0.35)
    box_h = int(height * 0.22)
    pad = 10
    x_off = width - box_w - pad
    y_off = height - box_h - pad

    # Semi-transparent dark slate background
    draw.rounded_rectangle(
        [(x_off, y_off), (x_off + box_w, y_off + box_h)],
        radius=6, fill=(15, 23, 42, 210),
    )

    min_p, max_p = min(price_history), max(price_history)
    p_range = (max_p - min_p) if max_p != min_p else 1

    trending_down = price_history[-1] <= price_history[0]
    line_color = (16, 185, 129, 255) if trending_down else (239, 68, 68, 255)

    margin = 6
    points = []
    for i, p in enumerate(price_history):
        px = x_off + margin + int((i / (len(price_history) - 1)) * (box_w - 2 * margin))
        py = y_off + box_h - margin - int(((p - min_p) / p_range) * (box_h - 2 * margin))
        points.append((px, py))

    draw.line(points, fill=line_color, width=2)
    lx, ly = points[-1]
    draw.ellipse([lx - 3, ly - 3, lx + 3, ly + 3], fill=line_color)

    return Image.alpha_composite(img, overlay)


_BACKGROUND_GRADIENT_CACHE = None
_FONT_CACHE = None


def _get_background_canvas() -> Image.Image:
    global _BACKGROUND_GRADIENT_CACHE
    if _BACKGROUND_GRADIENT_CACHE is None:
        strip_bytes = bytearray()
        for y in range(1000):
            r = int(0x07 + (0x16 - 0x07) * (y / 1000))
            g = int(0x0b + (0x1f - 0x0b) * (y / 1000))
            b = int(0x14 + (0x33 - 0x14) * (y / 1000))
            strip_bytes.extend((r, g, b))
        strip = Image.frombytes('RGB', (1, 1000), bytes(strip_bytes))
        _BACKGROUND_GRADIENT_CACHE = strip.resize((800, 1000), Image.Resampling.BILINEAR)
    return _BACKGROUND_GRADIENT_CACHE.copy()


def _get_cached_fonts():
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE

    font_bold = "C:\\Windows\\Fonts\\segoeuib.ttf"
    font_reg = "C:\\Windows\\Fonts\\segoeui.ttf"
    if not os.path.exists(font_bold):
        font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not os.path.exists(font_bold):
        font_bold = "C:\\Windows\\Fonts\\arialbd.ttf"
        font_reg = "C:\\Windows\\Fonts\\arial.ttf"

    try:
        title_font = ImageFont.truetype(font_bold, 24)
        price_font = ImageFont.truetype(font_bold, 54)
        label_font = ImageFont.truetype(font_bold, 26)
        meta_font = ImageFont.truetype(font_reg, 21)
        sub_font = ImageFont.truetype(font_reg, 16)
    except Exception:
        title_font = ImageFont.load_default()
        price_font = title_font
        label_font = title_font
        meta_font = title_font
        sub_font = title_font

    _FONT_CACHE = {
        "title": title_font,
        "price": price_font,
        "label": label_font,
        "meta": meta_font,
        "sub": sub_font
    }
    return _FONT_CACHE


def generate_deal_image(
    unique_id: str = "deal",
    platform: str = "amazon",
    title: str = "Product Deal",
    price: int = 999,
    mrp: int = 1999,
    discount: float = 50.0,
    img_url: str = None,
    original_image_url: str = None,
    is_verified_low: bool = True,
    deal_score: float = 85.0,
    **kwargs
) -> str:
    """
    Renders a high-impact, state-of-the-art social media deal card.
    Guarantees a clean, impressive image even when retailer product photo is missing.
    """
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    out_file = os.path.join(SCRATCH_DIR, f"{unique_id}_deal.jpg")
    
    target_img_url = img_url or original_image_url or kwargs.get("image_url")
    platform_clean = (platform or "amazon").lower()

    # 1. Initialize 800x1000 Canvas with Cached Premium Slate-to-Indigo Deep Gradient
    canvas = _get_background_canvas()
    draw = ImageDraw.Draw(canvas)

    # 2. Fonts Configuration
    fonts = _get_cached_fonts()
    title_font = fonts["title"]
    price_font = fonts["price"]
    label_font = fonts["label"]
    meta_font = fonts["meta"]
    sub_font = fonts["sub"]

    # 3. Top Header Bar
    is_amazon = "amazon" in platform_clean
    is_flipkart = "flipkart" in platform_clean
    
    header_color = "#f97316" if is_amazon else ("#2563eb" if is_flipkart else "#e11d48")
    header_text = "🟠 AMAZON DEALS" if is_amazon else ("🔵 FLIPKART LOOT" if is_flipkart else f"🔥 {platform.upper()} DEAL")

    # Platform capsule
    draw.rounded_rectangle([45, 28, 285, 75], radius=10, fill=header_color)
    draw.text((165, 51), header_text, font=title_font, fill="#ffffff", anchor="mm")

    # Live Loot Pulse Badge
    draw.rounded_rectangle([590, 28, 755, 75], radius=10, fill="#1e1b4b", outline="#6366f1", width=1)
    draw.ellipse([610, 44, 626, 60], fill="#22c55e")
    draw.text((680, 51), "VERIFIED", font=title_font, fill="#22c55e", anchor="mm")

    # 4. Main Stage (Product Image or Stylized Showcase Card) (690 x 440)
    draw.rounded_rectangle([45, 95, 755, 545], radius=18, fill="#0d1322", outline="#1e293b", width=2)

    # Fetch price history for overlay & bottom trend
    db = SessionLocal()
    prices_history = []
    try:
        history = db.query(PriceHistory).filter_by(product_id=unique_id).order_by(PriceHistory.timestamp.asc()).all()
        prices_history = [h.price for h in history if h.price]
    except Exception:
        pass
    finally:
        db.close()

    if not prices_history:
        prices_history = [mrp, price]
    elif len(prices_history) == 1:
        prices_history = [mrp, prices_history[0]]

    img_loaded = False
    if target_img_url and target_img_url.startswith("http") and not any(x in target_img_url for x in ["telesco.pe", "telegram.org"]):
        try:
            r = requests.get(target_img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            if r.status_code == 200 and len(r.content) > 500:
                prod_img = Image.open(BytesIO(r.content))
                if prod_img.mode != 'RGB':
                    prod_img = prod_img.convert('RGB')
                
                prod_img.thumbnail((620, 400), Image.Resampling.LANCZOS)
                prod_img = draw_sparkline_overlay(prod_img, prices_history)
                prod_img = prod_img.convert('RGB')

                x_pos = 45 + (710 - prod_img.width) // 2
                y_pos = 95 + (450 - prod_img.height) // 2
                canvas.paste(prod_img, (x_pos, y_pos))
                img_loaded = True
        except Exception as img_err:
            logger.debug(f"Image load exception in generator: {img_err}")

    # Impressive Graphic Fallback if no product thumbnail is available
    if not img_loaded:
        draw.rounded_rectangle([80, 130, 720, 510], radius=12, fill="#111827", outline="#374151", width=1)
        draw.text((400, 240), "🛍️", font=price_font, fill="#f8fafc", anchor="mm")
        draw.text((400, 320), "LIGHTNING DEAL DROP", font=label_font, fill="#38bdf8", anchor="mm")
        draw.text((400, 365), f"Exclusive {platform.title()} Price Drop Alert", font=meta_font, fill="#94a3b8", anchor="mm")
        draw.text((400, 420), "⚡ 100% Verified Bottom-Line Price ⚡", font=sub_font, fill="#22c55e", anchor="mm")

    # 5. Deal Intelligence Verdict Banner
    is_glitch = discount >= 70.0
    if is_glitch:
        alert_bg = "#dc2626"
        alert_lbl = "🚨 GLITCH DEAL: MASSIVE ERROR DROP 🚨"
    elif is_verified_low:
        alert_bg = "#16a34a"
        alert_lbl = "🔥 VERIFIED ALL-TIME LOWEST PRICE 🔥"
    else:
        alert_bg = "#0284c7"
        alert_lbl = "✨ VERIFIED CURATED PRICE DROP ✨"
        
    draw.rounded_rectangle([45, 560, 755, 608], radius=10, fill=alert_bg)
    draw.text((400, 584), alert_lbl, font=title_font, fill="#ffffff", anchor="mm")

    # 6. Pricing, Savings & Score Matrix Container
    draw.rounded_rectangle([45, 625, 755, 805], radius=16, fill="#0d1322", outline="#1e293b", width=2)
    
    # Big Price & Strikethrough MRP
    draw.text((75, 650), f"₹{int(price):,}", font=price_font, fill="#22c55e")
    draw.text((75, 722), f"MRP: ₹{int(mrp):,}", font=meta_font, fill="#64748b")
    # Draw strikethrough line over MRP
    mrp_text = f"MRP: ₹{int(mrp):,}"
    draw.line([(75, 735), (230, 735)], fill="#64748b", width=2)

    # Discount Capsule
    disc_text = f"🔥 {int(discount)}% OFF"
    draw.rounded_rectangle([320, 655, 510, 710], radius=22, fill="#dc2626")
    draw.text((415, 682), disc_text, font=label_font, fill="#ffffff", anchor="mm")

    # Deal Score Capsule
    score_text = f"⭐ {int(deal_score)}/100"
    draw.rounded_rectangle([530, 655, 725, 710], radius=22, fill="#7c3aed")
    draw.text((627, 682), score_text, font=label_font, fill="#ffffff", anchor="mm")

    # Product Title
    clean_title = title.split('\n')[0].strip()
    if len(clean_title) > 65:
        clean_title = clean_title[:62] + "..."
    draw.text((75, 760), clean_title, font=meta_font, fill="#f8fafc")

    # 7. Bottom Price Trajectory Graph Section (y = 825 to 975)
    draw.rounded_rectangle([45, 825, 755, 965], radius=16, fill="#0d1322", outline="#1e293b", width=2)
    draw.text((75, 842), "📉 90-Day Price Trajectory & Lowest Record", font=sub_font, fill="#94a3b8")

    min_price_val = min(prices_history)
    max_price_val = max(prices_history)
    p_diff = (max_price_val - min_price_val) if max_price_val != min_price_val else 1

    chart_x1, chart_x2 = 75, 725
    chart_y1, chart_y2 = 875, 945
    chart_w = chart_x2 - chart_x1
    chart_h = chart_y2 - chart_y1

    pts = []
    for i, p in enumerate(prices_history):
        px = chart_x1 + int((i / max(1, len(prices_history) - 1)) * chart_w)
        py = chart_y2 - int(((p - min_price_val) / p_diff) * chart_h)
        pts.append((px, py))

    # Draw graph line
    g_color = "#22c55e" if prices_history[-1] <= prices_history[0] else "#ef4444"
    draw.line(pts, fill=g_color, width=3)
    for px, py in pts:
        draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=g_color)

    # Save final optimized JPEG
    canvas.save(out_file, "JPEG", quality=92, optimize=True)
    logger.info(f"Generated impressive branded deal image card: {out_file}")
    return out_file
