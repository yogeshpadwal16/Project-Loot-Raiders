# -*- coding: utf-8 -*-
import io
import os
import logging
import requests
import httpx
from datetime import datetime

logger = logging.getLogger("loot_raiders.festival")

FESTIVALS = {
    "10-24": {
        "desc": "A majestic premium festival greeting card design for Diwali, featuring traditional glowing oil lamps, gold accents, warm bokeh background, cinematic lighting, professional digital graphic art, 4k resolution, no text, clean composition"
    },
    "09-07": {
        "desc": "A majestic premium festival greeting design for Ganesh Chaturthi, featuring Lord Ganesha, modak, bright golden temple background, cinematic lighting, 4k resolution, no text, clean composition"
    },
    "03-25": {
        "desc": "A vibrant premium greeting design for Holi, featuring splashes of colourful gulal powders, joyful festive spirit background, cinematic lighting, 4k resolution, no text, clean composition"
    },
    "08-02": {
        "desc": (
            "A majestic premium festival greeting card design for Sankashti Chaturthi, featuring Lord Ganesha "
            "seated majestically in front of a warm glowing fire and orange sunlight background, professional graphic "
            "design poster, golden accents, highly detailed, realistic textures, premium quality, no text, clean composition"
        )
    }
}

async def generate_festival_poster(prompt_details: str) -> bytes:
    """Generates a premium festival poster using Google Gemini Imagen models exclusively."""
    from config.settings import load_settings
    settings = load_settings()
    api_key = settings.get("gemini_api_key")
    
    if not api_key or "YOUR_GEMINI" in api_key or api_key.strip() == "":
        raise ValueError("GEMINI_API_KEY is not set or configured. Cannot generate poster.")

    # Loop through Gemini Pro & Flash image generation models (Nano Banana)
    models = ["nano-banana-pro-preview", "gemini-3-pro-image", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image", "gemini-2.5-flash-image"]
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt_details}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"]
            }
        }
        try:
            logger.info(f"[FESTIVAL] Attempting to generate poster using Gemini Pro/Flash Imagen model: {model}...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            inline_data = part.get("inlineData")
                            if inline_data and inline_data.get("data"):
                                import base64
                                logger.info(f"[FESTIVAL] Successfully generated poster using {model}!")
                                return base64.b64decode(inline_data["data"])
                else:
                    logger.warning(f"[FESTIVAL] Gemini API {model} returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"[FESTIVAL] Failed to call Gemini {model} API: {e}")
            
    raise RuntimeError("All Gemini/Imagen image models failed to generate the poster. Check quota/billing.")

def overlay_channel_watermark(image_bytes: bytes, title_text: str = "", sub_text: str = "", handle: str = "") -> bytes:
    """Stub function to maintain backward compatibility. Returns the image bytes unmodified."""
    return image_bytes

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
        files = {"photo": ("festival_poster.jpg", io.BytesIO(image_bytes), "image/jpeg")}
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
    
    # Determine printable name
    festival_name = "Sankashti Chaturthi" if today_key == "08-02" else "Festival"
    if today_key == "10-24":
        festival_name = "Diwali"
    elif today_key == "09-07":
        festival_name = "Ganesh Chaturthi"
    elif today_key == "03-25":
        festival_name = "Holi"
    
    logger.info(f"[FESTIVAL] Today ({today_key}) is {festival_name}! Generating poster...")
    try:
        raw_img = await generate_festival_poster(festival_desc)
        posted = send_festival_greeting(raw_img, festival_name)
        if posted:
            settings["last_festival_greeting_date"] = today_str
            save_settings(settings)
    except Exception as err:
        logger.error(f"[FESTIVAL] Error in check_and_run_festival_bot: {err}")
