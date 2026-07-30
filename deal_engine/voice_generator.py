import logging
import edge_tts

logger = logging.getLogger("loot_raiders.voice")

async def generate_deal_voice_note(
    title: str, deal_price: int, platform: str, output_path: str = "deal_alert.mp3"
) -> str:
    """Generates a high-urgency voice note using Edge-TTS (Free, no API key)."""
    text = (
        f"Loot Alert on {platform}! {title} is down to just {deal_price} rupees."
        " Tap the link below to claim before stock runs out!"
    )

    # En-IN Neural voice for Indian accent context
    voice = "en-IN-NeerjaNeural"
    communicate = edge_tts.Communicate(text, voice)

    try:
        await communicate.save(output_path)
        logger.info(f"[VOICE_NOTE] Saved voice alert to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"[VOICE_NOTE_FAIL] Failed to generate audio: {e}")
        return ""
