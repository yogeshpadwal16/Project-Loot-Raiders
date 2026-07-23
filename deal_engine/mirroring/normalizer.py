import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from deal_engine.mirroring.schemas import NormalizedMessage, ButtonSchema

# URL and coupon regex patterns
URL_REGEX = r'(https?://[^\s>]+)'
COUPON_REGEX = r'\b([A-Z0-9]{4,15})\b'

def extract_urls_from_text(text: str) -> List[str]:
    if not text:
        return []
    urls = []
    for url in re.findall(URL_REGEX, text):
        clean_url = url.rstrip('.,;()[]{}*#"\'')
        if clean_url not in urls:
            urls.append(clean_url)
    return urls

def extract_coupons_from_text(text: str) -> List[str]:
    if not text:
        return []
    # Identify coupon-looking words, excluding generic words like "RS", "MRP", "OFF", "GET", "LOOT"
    blacklist = {"MRP", "OFF", "GET", "LOOT", "DEAL", "FREE", "RS", "INR", "BUY", "ONLY", "SAFE", "POST", "JOIN"}
    coupons = []
    for match in re.findall(COUPON_REGEX, text):
        if match.upper() not in blacklist and not match.isdigit():
            coupons.append(match)
    return coupons

def extract_seller_info(text: str) -> Optional[str]:
    if not text:
        return None
    text_lower = text.lower()
    if "amazon" in text_lower:
        return "Amazon"
    if "flipkart" in text_lower:
        return "Flipkart"
    if "myntra" in text_lower:
        return "Myntra"
    if "ajio" in text_lower:
        return "Ajio"
    if "meesho" in text_lower:
        return "Meesho"
    if "tatacliq" in text_lower or "tata cliq" in text_lower:
        return "TataCliq"
    if "jiomart" in text_lower or "jio mart" in text_lower:
        return "JioMart"
    return None

class MessageNormalizer:
    @staticmethod
    def from_pyrogram(message: Any) -> NormalizedMessage:
        """Normalize a Pyrogram message object."""
        try:
            # 1. Basic Metadata
            channel_id = str(message.chat.id)
            channel_name = message.chat.username or message.chat.title or str(message.chat.id)
            message_id = message.id
            is_edited = bool(message.edit_date)
            
            raw_text = message.text or ""
            caption = message.caption or ""
            full_text = f"{raw_text}\n{caption}".strip()
            
            # 2. Extract URLs
            extracted_urls = extract_urls_from_text(full_text)
            
            # Extract from Pyrogram message entities (text hyperlinks)
            entities = message.entities or message.caption_entities
            if entities:
                from pyrogram.enums import MessageEntityType
                for entity in entities:
                    if entity.type == MessageEntityType.TEXT_LINK and entity.url:
                        if entity.url not in extracted_urls:
                            extracted_urls.append(entity.url)
                            
            # 3. Extract Buttons
            buttons = []
            if message.reply_markup and hasattr(message.reply_markup, 'inline_keyboard'):
                for row in message.reply_markup.inline_keyboard:
                    for button in row:
                        btn_url = getattr(button, 'url', None)
                        buttons.append(ButtonSchema(text=button.text, url=btn_url))
                        if btn_url and btn_url.startswith("http") and btn_url not in extracted_urls:
                            extracted_urls.append(btn_url)
            
            # 4. Handle Media
            media_type = "none"
            media_file_id = None
            if message.photo:
                media_type = "photo"
                media_file_id = message.photo.file_id
            elif message.video:
                media_type = "video"
                media_file_id = message.video.file_id
            elif message.document:
                media_type = "document"
                media_file_id = message.document.file_id
                
            # 5. Extract Coupons & Seller Info
            coupons = extract_coupons_from_text(full_text)
            seller = extract_seller_info(full_text)
            
            return NormalizedMessage(
                channel_id=channel_id,
                channel_name=channel_name,
                message_id=message_id,
                is_edited=is_edited,
                raw_text=raw_text,
                caption=caption,
                media_type=media_type,
                media_file_id=media_file_id,
                extracted_urls=extracted_urls,
                buttons=buttons,
                seller=seller,
                coupon_codes=coupons,
                metadata={
                    "client": "pyrogram",
                    "chat_type": str(message.chat.type),
                    "views": getattr(message, 'views', 0)
                }
            )
        except Exception as e:
            logging.error(f"[Normalizer] Error normalizing Pyrogram message: {e}")
            raise

    @staticmethod
    def from_telethon(message: Any) -> NormalizedMessage:
        """Normalize a Telethon message object."""
        try:
            # 1. Basic Metadata
            # Telethon chat_id can be negative for channels
            channel_id = str(message.chat_id)
            chat_entity = getattr(message, 'chat', None)
            channel_name = getattr(chat_entity, 'username', None) or getattr(chat_entity, 'title', None) or str(message.chat_id)
            message_id = message.id
            is_edited = getattr(message, 'edit_date', None) is not None
            
            raw_text = message.text or ""
            caption = message.message or "" # Telethon fallback message field
            full_text = f"{raw_text}\n{caption}".strip()
            
            # 2. Extract URLs
            extracted_urls = extract_urls_from_text(full_text)
            
            # Extract from Telethon message entities (text hyperlinks)
            if message.entities:
                from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl
                for entity in message.entities:
                    if isinstance(entity, MessageEntityTextUrl) and entity.url:
                        if entity.url not in extracted_urls:
                            extracted_urls.append(entity.url)
                            
            # 3. Extract Buttons
            buttons = []
            if message.reply_markup and hasattr(message.reply_markup, 'rows'):
                for row in message.reply_markup.rows:
                    if hasattr(row, 'buttons'):
                        for button in row.buttons:
                            btn_url = getattr(button, 'url', None)
                            buttons.append(ButtonSchema(text=button.text, url=btn_url))
                            if btn_url and btn_url.startswith("http") and btn_url not in extracted_urls:
                                extracted_urls.append(btn_url)
            
            # 4. Handle Media
            media_type = "none"
            media_file_id = None
            if message.photo:
                media_type = "photo"
                media_file_id = f"telethon_photo_{message.photo.id}"
            elif message.video:
                media_type = "video"
                media_file_id = f"telethon_video_{message.video.id}"
            elif message.document:
                media_type = "document"
                media_file_id = f"telethon_doc_{message.document.id}"
                
            # 5. Extract Coupons & Seller Info
            coupons = extract_coupons_from_text(full_text)
            seller = extract_seller_info(full_text)
            
            return NormalizedMessage(
                channel_id=channel_id,
                channel_name=channel_name,
                message_id=message_id,
                is_edited=is_edited,
                raw_text=raw_text,
                caption=caption,
                media_type=media_type,
                media_file_id=media_file_id,
                extracted_urls=extracted_urls,
                buttons=buttons,
                seller=seller,
                coupon_codes=coupons,
                metadata={
                    "client": "telethon",
                    "views": getattr(message, 'views', 0)
                }
            )
        except Exception as e:
            logging.error(f"[Normalizer] Error normalizing Telethon message: {e}")
            raise
