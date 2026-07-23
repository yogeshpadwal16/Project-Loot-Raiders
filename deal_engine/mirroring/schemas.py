from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import time
import uuid

class ButtonSchema(BaseModel):
    text: str
    url: Optional[str] = None

class NormalizedMessage(BaseModel):
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str
    channel_name: str
    message_id: int
    timestamp: float = Field(default_factory=time.time)
    is_edited: bool = False
    raw_text: Optional[str] = ""
    caption: Optional[str] = ""
    media_type: Optional[str] = "none" # 'photo', 'video', 'document', 'none'
    media_file_id: Optional[str] = None
    extracted_urls: List[str] = Field(default_factory=list)
    buttons: List[ButtonSchema] = Field(default_factory=list)
    seller: Optional[str] = None
    coupon_codes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
