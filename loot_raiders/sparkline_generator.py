import os
import requests
import logging
from io import BytesIO
from PIL import Image, ImageDraw

logger = logging.getLogger("loot_raiders.sparkline")

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)


def draw_sparkline_overlay(prod_img: Image.Image, price_history: list) -> Image.Image:
    """Draws a mini sparkline overlay on the bottom-right corner of the product image."""
    img = prod_img.convert("RGBA")
    width, height = img.size

    if width < 80 or height < 80:
        return img

    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    box_w = int(width * 0.35)
    box_h = int(height * 0.20)
    pad = 10
    x_off = width - box_w - pad
    y_off = height - box_h - pad

    # Semi-transparent dark background card box
    draw.rounded_rectangle(
        [(x_off, y_off), (x_off + box_w, y_off + box_h)],
        radius=6,
        fill=(15, 23, 42, 200)
    )

    if len(price_history) >= 2:
        min_p, max_p = min(price_history), max(price_history)
        p_range = (max_p - min_p) if max_p != min_p else 1

        # Green if trending down, red if up
        trending_down = price_history[-1] <= price_history[0]
        line_color = (16, 185, 129, 255) if trending_down else (239, 68, 68, 255)

        margin = 5
        points = []
        for i, p in enumerate(price_history):
            px = x_off + margin + int((i / (len(price_history) - 1)) * (box_w - 2 * margin))
            py = y_off + box_h - margin - int(((p - min_p) / p_range) * (box_h - 2 * margin))
            points.append((px, py))

        draw.line(points, fill=line_color, width=2)
        lx, ly = points[-1]
        draw.ellipse([lx - 3, ly - 3, lx + 3, ly + 3], fill=line_color)

    return Image.alpha_composite(img, overlay)


def generate_sparkline_thumbnail(product_id: str, image_url: str, current_price: int, mrp: int) -> str | None:
    """
    Downloads product image, retrieves price history from SQLite,
    applies the sparkline overlay, and saves it. Returns absolute path.
    """
    if not image_url or not image_url.startswith("http"):
        return None

    # Get price history from database
    from database import SessionLocal, PriceHistory
    db = SessionLocal()
    price_history = []
    try:
        entries = db.query(PriceHistory).filter_by(product_id=product_id).order_by(PriceHistory.timestamp.asc()).all()
        price_history = [e.price for e in entries]
    except Exception as e:
        logger.error(f"Failed to query price history for sparkline: {e}")
    finally:
        db.close()

    if not price_history:
        price_history = [mrp, current_price]
    elif len(price_history) == 1:
        price_history = [mrp, price_history[0]]

    try:
        res = requests.get(image_url, timeout=8)
        if res.status_code == 200:
            img = Image.open(BytesIO(res.content))
            overlay_img = draw_sparkline_overlay(img, price_history)
            
            # Save the composite card to the media folder
            out_path = os.path.join(MEDIA_DIR, f"card_{product_id}.png")
            overlay_img.convert("RGB").save(out_path, "PNG")
            return out_path
    except Exception as e:
        logger.warning(f"Failed to generate sparkline overlay for {product_id}: {e}")

    return None
