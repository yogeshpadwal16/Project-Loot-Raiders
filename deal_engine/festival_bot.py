import io
import logging
from datetime import datetime
import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("loot_raiders.festival")

FESTIVALS = {
    "10-24": "Diwali Festival of Lights, traditional oil lamps, gold decorations",
    "09-07": "Ganesh Chaturthi Lord Ganesha, modak, grand celebration",
    "03-25": "Holi Festival of Colors, vibrant gulal powders, festive spirit",
    "08-02": "Sankashti Chaturthi, Lord Ganesha, modak, divine blessings, traditional oil lamps, spiritual atmosphere",
}

async def generate_festival_poster(prompt_details: str) -> bytes:
    """Fetches a free AI-generated festival poster from Pollinations.ai."""
    base_prompt = f"Indian festival greeting poster, {prompt_details}, high quality, 4k, festive lighting"
    encoded_prompt = httpx.URL(base_prompt).raw_path.decode()
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080&nologo=true"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content

def overlay_channel_watermark(image_bytes: bytes, handle: str = "@LootRaidersDeals") -> bytes:
    """Overlays the channel handle at the bottom of the poster using Pillow."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Semi-transparent banner at the bottom
    width, height = img.size
    draw.rectangle([(0, height - 80), (width, height)], fill=(0, 0, 0, 160))

    # Watermark text
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except OSError:
        font = ImageFont.load_default()

    draw.text((30, height - 60), handle, fill=(255, 215, 0, 255), font=font)

    output = io.BytesIO()
    img.save(output, format="PNG")
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
        
    festival_desc = FESTIVALS[today_key]
    festival_name = festival_desc.split(',')[0].split('Festival')[0].strip()
    
    logger.info(f"[FESTIVAL] Today ({today_key}) is {festival_name}! Generating poster...")
    try:
        raw_img = await generate_festival_poster(festival_desc)
        final_poster = overlay_channel_watermark(raw_img)
        posted = send_festival_greeting(final_poster, festival_name)
        if posted:
            settings["last_festival_greeting_date"] = today_str
            save_settings(settings)
    except Exception as err:
        logger.error(f"[FESTIVAL] Error in check_and_run_festival_bot: {err}")
