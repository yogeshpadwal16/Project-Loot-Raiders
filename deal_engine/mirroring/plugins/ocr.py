import os
import tempfile
import requests
import logging
from typing import Optional
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.plugins.base import MirrorPlugin

# Gracefully import PIL and pytesseract
try:
    from PIL import Image
    import pytesseract
    HAS_OCR_LIBS = True
except ImportError:
    HAS_OCR_LIBS = False

class OCRPlugin(MirrorPlugin):
    """
    Plugin to perform Optical Character Recognition (OCR) on image attachments
    to extract price/deal text that might be embedded in the image itself,
    inspired by tgcf's OCR plugin.
    """
    def apply(self, message: NormalizedMessage) -> Optional[NormalizedMessage]:
        if not self.enabled:
            return message

        if not HAS_OCR_LIBS:
            logging.warning("[OCR Plugin] PIL or pytesseract libraries are not installed. Skipping OCR.")
            return message

        tesseract_path = self.config.get("tesseract_path", "")
        if tesseract_path:
            try:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            except Exception as e:
                logging.error(f"[OCR Plugin] Failed to set custom tesseract path '{tesseract_path}': {e}")

        # Check if we have a photo URL
        img_url = message.media_file_id
        if message.media_type != "photo" or not img_url or not img_url.startswith("http"):
            # We can only perform OCR on direct HTTP URLs in this background processing context
            # (Pyrogram/Telethon file_ids require the active client to download, which is in another process/loop)
            return message

        logging.info(f"[OCR Plugin] Performing OCR on image: {img_url}")
        
        temp_file = None
        try:
            # Download the image to a temp file
            res = requests.get(img_url, timeout=10)
            if res.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(res.content)
                    temp_file = tmp.name

                # Open PIL Image and perform OCR
                with Image.open(temp_file) as img:
                    ocr_text = pytesseract.image_to_string(img)

                if ocr_text and ocr_text.strip():
                    cleaned_ocr = ocr_text.strip()
                    logging.info(f"[OCR Plugin] Successfully extracted text: {cleaned_ocr[:100]}...")
                    
                    # Append OCR text to raw_text/caption so scraper/parser can inspect it
                    prefix = "\n\n[OCR Text Extracted]:\n"
                    if message.raw_text:
                        message.raw_text += f"{prefix}{cleaned_ocr}"
                    else:
                        message.raw_text = cleaned_ocr
            else:
                logging.warning(f"[OCR Plugin] Failed to download image, status code: {res.status_code}")
        except Exception as e:
            logging.error(f"[OCR Plugin] Error during OCR processing: {e}")
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

        return message
