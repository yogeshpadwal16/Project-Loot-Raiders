import os
import requests
import urllib.parse
from PIL import Image, ImageDraw, ImageFont

# Directory for storing generated posters
MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)


def generate_festival_poster(festival_name: str, message: str) -> str | None:
    """
    Generates a festival card poster using Pollinations.ai image API
    and overlays festival messages and brand watermark using Pillow.
    Returns the absolute path to the generated image poster.
    """
    # Create descriptive AI image generation prompt
    ai_prompt = f"Beautiful traditional {festival_name} celebrations card, elegant colors, clean background, ultra HD"
    encoded_prompt = urllib.parse.quote(ai_prompt)
    api_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=800&nologo=true"

    try:
        res = requests.get(api_url, timeout=15)
        if res.status_code != 200:
            return None

        # Load image into Pillow
        img = Image.open(io.BytesIO(res.content)) if 'io' in globals() else None
        if not img:
            import io
            img = Image.open(io.BytesIO(res.content))

        # Overlay text using ImageDraw
        draw = ImageDraw.Draw(img)
        
        # Load system fonts
        font_path = "C:\\Windows\\Fonts\\segoeui.ttf"
        if not os.path.exists(font_path):
            font_path = "C:\\Windows\\Fonts\\arial.ttf"

        try:
            large_font = ImageFont.truetype(font_path, 40)
            small_font = ImageFont.truetype(font_path, 24)
        except Exception:
            large_font = ImageFont.load_default()
            small_font = large_font

        # Draw semi-transparent dark banner at bottom
        draw.rectangle([(0, 680), (800, 800)], fill=(15, 23, 42, 210))

        # Render festival header & message
        draw.text((400, 715), f"✨ Happy {festival_name}! ✨", font=large_font, fill="#f59e0b", anchor="mm")
        draw.text((400, 765), message, font=small_font, fill="#e2e8f0", anchor="mm")

        # Save to media folder
        out_file = os.path.join(MEDIA_DIR, f"{festival_name.lower().replace(' ', '_')}_poster.jpg")
        img.save(out_file, "JPEG", quality=90)
        return out_file
    except Exception as e:
        print(f"Failed to generate festival card: {e}")
    return None


if __name__ == "__main__":
    poster = generate_festival_poster("Mahalaxmi Puja", "May goddess Laxmi bless you with wealth & prosperity!")
    print(f"Generated poster: {poster}")
