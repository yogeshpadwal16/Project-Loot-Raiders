import logging
from typing import Optional
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.plugins.base import MirrorPlugin

class FormatPlugin(MirrorPlugin):
    """
    Plugin to re-format message texts by prepending custom headers,
    appending custom footers, and adding unified channel tags.
    """
    def apply(self, message: NormalizedMessage) -> Optional[NormalizedMessage]:
        if not self.enabled:
            return message

        header = self.config.get("header", "")
        footer = self.config.get("footer", "")

        # Format raw_text if present, otherwise format caption
        if message.raw_text:
            message.raw_text = f"{header}{message.raw_text}{footer}"
        elif message.caption:
            message.caption = f"{header}{message.caption}{footer}"
        else:
            # Fallback if both are empty
            message.raw_text = f"{header.strip()}{footer.strip()}"

        return message
