import re
import logging
from typing import Optional
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.plugins.base import MirrorPlugin

class ReplacePlugin(MirrorPlugin):
    """
    Plugin to perform search-and-replace or regex-based replacement on message texts.
    Cleans up competitor channel branding, usernames, specific links, etc.
    """
    def apply(self, message: NormalizedMessage) -> Optional[NormalizedMessage]:
        if not self.enabled:
            return message

        patterns = self.config.get("patterns", [])
        if not patterns:
            return message

        # Work on both raw_text and caption
        modified_raw = message.raw_text or ""
        modified_caption = message.caption or ""

        for pattern in patterns:
            find_str = pattern.get("find", "")
            replace_str = pattern.get("replace", "")
            is_regex = pattern.get("regex", True)
            case_insensitive = pattern.get("case_insensitive", True)

            if not find_str:
                continue

            flags = 0
            if case_insensitive:
                flags |= re.IGNORECASE

            try:
                if is_regex:
                    # Regex replacement
                    compiled = re.compile(find_str, flags)
                    modified_raw = compiled.sub(replace_str, modified_raw)
                    modified_caption = compiled.sub(replace_str, modified_caption)
                else:
                    # Literal search replacement
                    if case_insensitive:
                        # Case insensitive literal replacement using regex escape
                        compiled = re.compile(re.escape(find_str), flags)
                        modified_raw = compiled.sub(replace_str, modified_raw)
                        modified_caption = compiled.sub(replace_str, modified_caption)
                    else:
                        modified_raw = modified_raw.replace(find_str, replace_str)
                        modified_caption = modified_caption.replace(find_str, replace_str)
            except Exception as e:
                logging.error(f"[Replace Plugin] Error applying pattern '{find_str}' -> '{replace_str}': {e}")

        # Update message contents
        message.raw_text = modified_raw
        message.caption = modified_caption
        return message
