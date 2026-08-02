# -*- coding: utf-8 -*-
import io
import os
import requests
import urllib.parse
import httpx
from PIL import Image, ImageDraw, ImageFont

# Directory for storing generated posters
MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

def generate_festival_poster(festival_name: str, message: str) -> str | None:
    """
    Generates a festival card poster using Google Gemini Imagen models (Nano Banana).
    Returns the absolute path to the generated image poster.
    """
    from config.settings import load_settings
    settings = load_settings()
    api_key = settings.get("gemini_api_key")
    
    if not api_key or "YOUR_GEMINI" in api_key or api_key.strip() == "":
        print("GEMINI_API_KEY is not set or configured. Cannot generate poster.")
        return None

    ai_prompt = (
        f"An epic cinematic poster for {festival_name}, elegant colors, clean background, "
        "realistic detailed textures, dramatic volumetric lighting, professional digital art, "
        "8k resolution, no text, clean composition"
    )

    models = ["nano-banana-pro-preview", "gemini-3-pro-image", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image", "gemini-2.5-flash-image"]
    
    img_bytes = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": ai_prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"]
            }
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=60)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        inline_data = part.get("inlineData")
                        if inline_data and inline_data.get("data"):
                            import base64
                            img_bytes = base64.b64decode(inline_data["data"])
                            break
                    if img_bytes:
                        break
        except Exception as e:
            print(f"Failed to generate using {model}: {e}")

    if not img_bytes:
        print("All Gemini/Imagen image models failed to generate the poster.")
        return None

    try:
        # Load image into Pillow
        img = Image.open(io.BytesIO(img_bytes))
        
        # Save to media folder
        out_file = os.path.join(MEDIA_DIR, f"{festival_name.lower().replace(' ', '_')}_poster.jpg")
        img.save(out_file, "JPEG", quality=95)
        return out_file
    except Exception as e:
        print(f"Failed to process and save festival card: {e}")
    return None

if __name__ == "__main__":
    poster = generate_festival_poster("Mahalaxmi Puja", "May goddess Laxmi bless you with wealth & prosperity!")
    print(f"Generated poster: {poster}")
