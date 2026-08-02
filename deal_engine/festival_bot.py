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
        "name": "Diwali",
        "desc": "An epic cinematic poster for Diwali, featuring traditional glowing oil lamps, rich gold accents, warm bokeh lights, volumetric smoke, floating dust embers, professional digital art, 8k resolution, no text, clean composition",
        "caption": (
            "✨ <b>शुभ दीपावली!</b> ✨\n\n"
            "तुम्हाला आणि तुमच्या संपूर्ण कुटुंबाला दीपावलीच्या निमित्ताने सुख, समृद्धी आणि उत्तम आरोग्य लाभो, हीच प्रार्थना. "
            "हा दिव्यांचा सण तुमच्या आयुष्यात प्रकाश आणि आनंद घेऊन येवो!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "09-07": {
        "name": "Ganesh Chaturthi",
        "desc": "An epic cinematic poster of Lord Ganesha, seated majestically on a golden throne, realistic detailed textures, dramatic volumetric lighting, bright golden temple background with soft glowing smoke and floating dust particles, high contrast, professional digital art, award-winning illustration style, 8k resolution, no text, clean composition",
        "caption": (
            "✨ <b>गणेश चतुर्थीच्या हार्दिक शुभेच्छा!</b> ✨\n\n"
            "बाप्पाच्या आगमनाने तुमच्या घरी सुख, समृद्धी आणि ऐश्वर्य नांदो. "
            "गणेश चतुर्थीच्या निमित्ताने तुम्हाला व तुमच्या कुटुंबाला हार्दिक शुभेच्छा!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "03-25": {
        "name": "Holi",
        "desc": "An epic cinematic poster for Holi, featuring vibrant splashes of colourful gulal powders, joyful festive spirit background, dynamic lighting, floating powder particles, professional digital art, 8k resolution, no text, clean composition",
        "caption": (
            "✨ <b>धुलिवंदन व होळीच्या हार्दिक शुभेच्छा!</b> ✨\n\n"
            "रंगांचा हा सण तुमच्या आयुष्यात नवी उमेद, उत्साह आणि आनंद घेऊन येवो. "
            "तुम्हाला आणि तुमच्या कुटुंबाला होळीच्या हार्दिक शुभेच्छा!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    },
    "08-02": {
        "name": "Sankashti Chaturthi",
        "desc": (
            "An epic cinematic poster of Lord Ganesha, seated majestically on a golden throne, "
            "realistic detailed textures, dramatic volumetric lighting, warm golden and deep orange "
            "fire background with soft glowing smoke and floating dust particles, high contrast, "
            "professional digital art, award-winning illustration style, 8k resolution, no text, clean composition"
        ),
        "caption": (
            "✨ <b>संकष्टी चतुर्थीच्या हार्दिक शुभेच्छा!</b> ✨\n\n"
            "तुम्हाला आणि तुमच्या संपूर्ण कुटुंबाला संकष्टी चतुर्थीच्या निमित्ताने सुख, समृद्धी आणि उत्तम आरोग्य लाभो, हीच गणरायाच्या चरणी प्रार्थना. "
            "बाप्पा तुमच्या आयुष्यातील सर्व संकटे दूर करोत!\n\n"
            "🌸 <i>टीम @LootRaidersDeals कडून मनःपूर्वक शुभेच्छा</i> 🌸"
        )
    }
}

async def generate_festival_poster(prompt_details: str) -> bytes:
    """Generates a premium festival poster using Google Gemini Imagen models exclusively (Nano Banana)."""
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

def send_festival_greeting(image_bytes: bytes, caption: str) -> bool:
    from config.settings import load_settings
    import requests
    
    settings = load_settings()
    bot_token = settings.get("telegram_bot_token")
    chat_id = settings.get("telegram_chat_id")
    
    if not bot_token or "YOUR_TELEGRAM" in bot_token or bot_token.strip() == "" or not chat_id:
        logger.warning("[FESTIVAL] Bot credentials not set in settings.json. Skipping posting.")
        return False
        
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    try:
        files = {"photo": ("festival_poster.jpg", io.BytesIO(image_bytes), "image/jpeg")}
        payload = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML"
        }
        res = requests.post(endpoint, data=payload, files=files, timeout=30)
        if res.status_code == 200:
            logger.info("[FESTIVAL] Successfully posted greeting card to Telegram!")
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
    caption = config["caption"]
    
    logger.info(f"[FESTIVAL] Today ({today_key}) is {config['name']}! Generating poster...")
    try:
        raw_img = await generate_festival_poster(festival_desc)
        posted = send_festival_greeting(raw_img, caption)
        if posted:
            settings["last_festival_greeting_date"] = today_str
            save_settings(settings)
    except Exception as err:
        logger.error(f"[FESTIVAL] Error in check_and_run_festival_bot: {err}")
