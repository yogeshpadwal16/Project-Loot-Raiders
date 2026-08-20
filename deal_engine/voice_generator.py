"""
deal_engine/voice_generator.py
5-Second Hinglish Voice Deal Generator.
Generates energetic, crisp audio deal alerts for high-priority loot glitches.
"""

import os
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("loot_raiders.voice")


def generate_hinglish_script(title: str, price: float, discount: float, platform: str) -> str:
    """Generates an energetic, conversational Hinglish deal announcement script."""
    clean_title = title.split("-")[0].split("(")[0].strip()[:35]
    price_val = int(price)
    
    if discount and discount >= 60:
        return f"Bhai loot lo! {clean_title} pe {int(discount)} percent off chal raha hai, sirf {price_val} rupaye me {platform.capitalize()} par! Link check karo jaldi!"
    else:
        return f"Dhamaka deal! {clean_title} mil raha hai sirf {price_val} rupaye me {platform.capitalize()} par. Grab kar lo stock khatam hone se pehle!"


async def create_voice_deal_clip_async(text: str, output_path: str) -> bool:
    """Uses edge-tts to generate a natural Indian English/Hindi voice note."""
    try:
        import edge_tts
        voice = "hi-IN-MadhurNeural" # Highly natural energetic male voice
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except ImportError:
        logger.warning("edge-tts library not installed, skipping audio generation.")
        return False
    except Exception as e:
        logger.error(f"Voice generation failed: {e}")
        return False


def generate_deal_audio_note(title: str, price: float, discount: float, platform: str, output_path: str = "/tmp/deal_alert.mp3") -> Optional[str]:
    """Synchronous entry point to generate voice note."""
    script = generate_hinglish_script(title, price, discount, platform)
    try:
        success = asyncio.run(create_voice_deal_clip_async(script, output_path))
        return output_path if success else None
    except Exception:
        return None
