import os
import asyncio
import logging

logger = logging.getLogger("loot_raiders.voice")

AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
os.makedirs(AUDIO_DIR, exist_ok=True)


async def generate_voice_alert(product_title: str, price: int) -> str | None:
    """
    Uses edge-tts to generate a high-quality 10-second MP3 voice alert
    announcing a major price glitch or verified low price deal.
    """
    clean_title = product_title.split('\n')[0].strip()
    if len(clean_title) > 50:
        clean_title = clean_title[:47] + "..."

    # Construct the speech prompt script
    announcement = f"Price drop alert! {clean_title} is selling for only {price} rupees. Grab this deal now!"
    voice = "en-IN-NeerjaNeural" # Premium Indian female voice
    out_file = os.path.join(AUDIO_DIR, f"alert_{int(time.time() if 'time' in globals() else 1)}.mp3")
    if 'time' not in globals():
        import time
        out_file = os.path.join(AUDIO_DIR, f"alert_{int(time.time())}.mp3")

    try:
        import edge_tts
        communicate = edge_tts.Communicate(announcement, voice)
        await communicate.save(out_file)
        logger.info(f"[Voice] Audio announcement saved to: {out_file}")
        return out_file
    except ImportError:
        logger.warning("edge-tts library is not installed. Voice alerts disabled.")
    except Exception as e:
        logger.error(f"Voice alert generation failed: {e}")
        
    return None
