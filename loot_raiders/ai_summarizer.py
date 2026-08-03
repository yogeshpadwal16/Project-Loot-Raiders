import logging
import asyncio
import google.generativeai as genai

logger = logging.getLogger("loot_raiders.ai_summarizer")

class DealSummarizer:
    def __init__(self, gemini_api_key: str):
        self.api_key = gemini_api_key
        self.enabled = False
        
        if gemini_api_key and "YOUR_" not in gemini_api_key and gemini_api_key.strip() != "":
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-3.5-flash")
                self.enabled = True
                logger.info("Gemini Deal Summarizer configured successfully.")
            except Exception as e:
                logger.error(f"Error configuring Gemini AI: {e}")

    async def summarize_deal(self, title: str, raw_details: str) -> str:
        """
        Uses Gemini API to summarize raw product details into exactly 3 punchy, high-conversion bullet points.
        Includes a robust heuristic fallback if Gemini is disabled or fails.
        """
        if not self.enabled:
            return self._heuristic_fallback(title, raw_details)
            
        prompt = f"""
        You are a high-conversion affiliate copywriter. 
        Create exactly 3 punchy, short, compelling bullet points summarizing the key selling points of this product.
        Focus on value, specifications, and savings. Keep each bullet point under 12 words. Do not use markdown bold/italic inside bullets.
        
        Product Title: {title}
        Raw Details/Specs: {raw_details}
        
        Format:
        • [Bullet 1]
        • [Bullet 2]
        • [Bullet 3]
        """
        
        try:
            # Run blocking API call in a separate thread
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            summary = response.text.strip()
            
            # Basic validation of bullet points
            lines = [l.strip() for l in summary.splitlines() if l.strip().startswith("•") or l.strip().startswith("-")]
            if len(lines) >= 3:
                return "\n".join(lines[:3])
            
            # If not formatted as expected, return raw stripped text
            return summary
        except Exception as e:
            logger.error(f"Gemini summarization failed: {e}")
            return self._heuristic_fallback(title, raw_details)

    def _heuristic_fallback(self, title: str, raw_details: str) -> str:
        """Heuristic rule-based fallback when Gemini API is unavailable."""
        logger.debug("Executing heuristic fallback for deal summary.")
        bullets = []
        
        # Heuristic 1: Extract features if available
        if raw_details:
            lines = [l.strip() for l in raw_details.splitlines() if len(l.strip()) > 10]
            for line in lines:
                if any(c in line.lower() for c in ["warranty", "display", "battery", "camera", "fast charge", "off", "free"]):
                    bullets.append(f"• {line[:50]}...")
                if len(bullets) >= 3:
                    break
                    
        # Heuristic 2: Fallback to basic details
        if len(bullets) < 3:
            bullets.append(f"• Premium quality product with verified discount.")
        if len(bullets) < 3:
            bullets.append(f"• Top rated retailer with fast doorstep delivery.")
        if len(bullets) < 3:
            bullets.append(f"• Hurry! Price drop might expire soon.")
            
        return "\n".join(bullets[:3])
