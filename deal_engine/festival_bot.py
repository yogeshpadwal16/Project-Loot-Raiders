# -*- coding: utf-8 -*-
import io
import os
import logging
import requests
import httpx
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("loot_raiders.festival")

# Custom Devanagari Font URL and Local File Path
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/yatraone/YatraOne-Regular.ttf"
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "YatraOne-Regular.ttf")

FESTIVALS = {
    "10-24": {
        "desc": "Vibrant Diwali Festival of Lights card, traditional oil lamps, gold decorations, warm glowing lights background, cinematic lighting, 4k",
        "title": "\u0936\u0941\u092d \u0926\u0940\u092a\u093e\u0935\u0932\u0940",  # शुभ दीपावली
        "sub": "\u0926\u0940\u092a\u093e\u0935\u0932\u0940\u091a\u094d\u092f\u093e \u0939\u093e\u0930\u094d\u0926\u093f\u0915 \u0936\u0941\u092d\u0947\u091a\u094d\u091b\u093e..."  # दीपावलीच्या हार्दिक शुभेच्छा...
    },
    "09-07": {
        "desc": "Vibrant Ganesh Chaturthi card, Lord Ganesha, modak, grand celebration, bright golden temple background, cinematic highlights, 4k",
        "title": "\u0917\u0923\u0947\u0936 \u091a\u0924\u0941\u0930\u094d\u0925\u0940",  # गणेश चतुर्थी
        "sub": "\u092e\u0902\u0917\u0932\u092e\u094d\u092f \u0936\u0941\u092d\u0947\u091a\u094d\u091b\u093e..."  # मंगलमय शुभेच्छा...
    },
    "03-25": {
        "desc": "Vibrant Holi Festival of Colors card, gulal powders splash, joyful festive spirit background, cinematic lighting, 4k",
        "title": "\u0927\u0941\u0932\u093f\u0935\u0902\u0926\u0928",  # धुलिवंदन
        "sub": "\u093a\u094b\u0933\u0940\u091a\u094d\u092f\u093e \u0939\u093e\u0930\u094d\u0926\u093f\u0915 \u0936\u0941\u092d\u0947\u091a\u094d\u091b\u093e..."  # होळीच्या हार्दिक शुभेच्छा...
    },
    "08-02": {
        "desc": (
            "Vibrant cinematic portrait of Lord Ganesha, seated majestically, realistic textures, "
            "glowing bright orange and yellow fire background, intense golden highlights, high contrast, "
            "professional digital graphic design greeting card, mystical and spiritual, 4k resolution"
        ),
        "title": "\u0938\u0902\u0915\u0937\u094d\u091f \u091a\u0924\u0941\u0930\u094d\u0925\u0940",  # संकष्ट चतुर्थी
        "sub": "\u0928\u093f\u092e\u093f\u0924\u094d\u0924 \u0939\u093e\u0930\u094d\u0926\u093f\u0915 \u0936\u0941\u092d\u0947\u091a\u094d\u091b\u093e..."  # निमित्त हार्दिक शुभेच्छा...
    }
}

def download_font_if_needed():
    if not os.path.exists(FONT_PATH):
        try:
            logger.info("Downloading Yatra One Devanagari font...")
            res = requests.get(FONT_URL, timeout=15)
            if res.status_code == 200:
                with open(FONT_PATH, "wb") as f:
                    f.write(res.content)
                logger.info("Font downloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to download Devanagari font: {e}")

async def generate_festival_poster(prompt_details: str) -> bytes:
    """Fetches a free AI-generated festival poster from Pollinations.ai."""
    base_prompt = f"{prompt_details}, high quality, 4k, festive lighting, no text, clean composition"
    encoded_prompt = httpx.URL(base_prompt).raw_path.decode()
    # Adding seed for reproducibility and premium quality
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080&nologo=true&seed=88"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content

def overlay_channel_watermark(image_bytes: bytes, title_text: str, sub_text: str, handle: str = "@LootRaidersDeals") -> bytes:
    """
    Overlays polished Devanagari calligraphy text and watermark on the Ganesha poster.
    Applies a smooth bottom gradient vignette instead of a solid black banner.
    """
    download_font_if_needed()
    
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size
    
    # Create overlay drawing context
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Load fonts
    try:
        font_title = ImageFont.truetype(FONT_PATH, 80)
        font_sub = ImageFont.truetype(FONT_PATH, 32)
        font_watermark = ImageFont.truetype("arial.ttf", 28)
    except Exception as e:
        logger.warning(f"Could not load custom font, using default: {e}")
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_watermark = ImageFont.load_default()

    # Draw a soft dark gradient vignette at the bottom to make text highly readable
    for y in range(height - 350, height):
        alpha = int((y - (height - 350)) / 350 * 220) # Max opacity 220
        draw.line([(0, y), (width, y)], fill=(12, 4, 4, alpha))

    # Draw main title shadow
    draw.text((width // 2 + 3, height - 240 + 3), title_text, fill=(0, 0, 0, 180), font=font_title, anchor="mm")
    # Draw main title (gold color)
    draw.text((width // 2, height - 240), title_text, fill=(255, 215, 0, 255), font=font_title, anchor="mm")

    # Draw sub text shadow
    draw.text((width // 2 + 1, height - 160 + 1), sub_text, fill=(0, 0, 0, 180), font=font_sub, anchor="mm")
    # Draw sub text (white)
    draw.text((width // 2, height - 160), sub_text, fill=(255, 255, 255, 255), font=font_sub, anchor="mm")

    # Draw watermark (gold)
    draw.text((width // 2, height - 60), handle, fill=(255, 215, 0, 220), font=font_watermark, anchor="mm")

    # Composite images
    final_img = Image.alpha_composite(img, overlay).convert("RGB")
    
    output = io.BytesIO()
    final_img.save(output, format="JPEG", quality=95)
    return output.getvalue()

def send_festival_greeting(image_bytes: bytes, festival_name: str) -> bool:
    from config.settings import load_settings
    import requests
    
    settings = load_settings()
    bot_token = settings.get("telegram_bot_token")
    chat_id = settings.get("telegram_chat_id")
    
    if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "" or not chat_id:
        logger.warning("[FESTIVAL] Bot credentials not set in settings.json. Skipping posting.")
        return False
        
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    caption = (
        f"✨ <b>{festival_name} Greetings!</b> ✨\n\n"
        f"Wishing you and your family a very happy, healthy, and prosperous {festival_name}. "
        f"May this festive season fill your life with happiness and joy!\n\n"
        f"🌸 <i>Warm regards from team @LootRaidersDeals</i> 🌸"
    )
    
    try:
        files = {"photo": ("festival_poster.png", io.BytesIO(image_bytes), "image/png")}
        payload = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML"
        }
        res = requests.post(endpoint, data=payload, files=files, timeout=30)
        if res.status_code == 200:
            logger.info(f"[FESTIVAL] Successfully posted greeting card for {festival_name} to Telegram!")
            return True
        else:
            logger.error(f"[FESTIVAL] Telegram API failed to post greeting card ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        logger.error(f"[FESTIVAL] Error posting festival greeting to Telegram: {e}")
        return False

async def check_and_run_festival_bot():
    """Daily check runner."""
    from config.settings import load_settings, save_settings
    
    now = datetime.now()
    today_key = now.strftime("%m-%d")
    today_str = now.strftime("%Y-%m-%d")
    
    if today_key not in FESTIVALS:
        return
        
    settings = load_settings()
    if settings.get("last_festival_greeting_date") == today_str:
        return # Already run today
        
    config = FESTIVALS[today_key]
    festival_desc = config["desc"]
    title_text = config["title"]
    sub_text = config["sub"]
    
    # Determine printable name from prompt details
    festival_name = "Sankashti Chaturthi" if today_key == "08-02" else festival_desc.split(',')[0].split('Festival')[0].strip()
    
    logger.info(f"[FESTIVAL] Today ({today_key}) is {festival_name}! Generating poster...")
    try:
        raw_img = await generate_festival_poster(festival_desc)
        final_poster = overlay_channel_watermark(raw_img, title_text, sub_text)
        posted = send_festival_greeting(final_poster, festival_name)
        if posted:
            settings["last_festival_greeting_date"] = today_str
            save_settings(settings)
    except Exception as err:
        logger.error(f"[FESTIVAL] Error in check_and_run_festival_bot: {err}")
