import os
import requests
import logging

logger = logging.getLogger("loot_raiders.summarizer")


def generate_ai_summary(product_title: str, api_key: str = None) -> list[str]:
    """
    Invokes Google Gemini 1.5 Flash API (free-tier endpoints) to summarize
    product titles and details into 3 high-impact, conversion-focused bullet points.
    Returns list of 3 strings. If API fails, returns fallback bullet points.
    """
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")

    fallback = [
        "🔥 Lowest price ever recorded in history.",
        "✨ Top-rated category product with verified feedback.",
        "⚡ Massive discount active — grab before stock runs out!"
    ]

    if not api_key or "example" in api_key.lower() or api_key.strip() == "":
        return fallback

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = (
        f"Analyze this product: '{product_title}'.\n"
        f"Create exactly 3 concise, high-impact marketing bullet points (no formatting, no markdown prefix, just text) "
        f"highlighting the best reasons to purchase. Return each point on a new line."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 150,
            "temperature": 0.3
        }
    }

    try:
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=8)
        if res.status_code == 200:
            data = res.json()
            # Parse Gemini response structure
            candidates = data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                bullets = [b.strip().strip("*-• ") for b in text.split("\n") if b.strip()]
                if len(bullets) >= 3:
                    return bullets[:3]
                # Pad with fallback if fewer bullets returned
                return (bullets + fallback)[:3]
    except Exception as e:
        logger.warning(f"Gemini API summarization failed: {e}")

    return fallback
