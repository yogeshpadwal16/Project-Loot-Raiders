import re
import logging
from typing import Optional
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.plugins.base import MirrorPlugin
import config.settings

class FilterPlugin(MirrorPlugin):
    """
    Plugin to filter messages based on whitelist/blacklist keywords or regex,
    and minimum/maximum message lengths.
    """
    def apply(self, message: NormalizedMessage) -> Optional[NormalizedMessage]:
        if not self.enabled:
            return message

        # Combine plugin specific keywords with global blocklist keywords
        settings = config.settings.load_settings()
        global_blocklist = settings.get("blocklist_keywords", [])
        plugin_blocklist = self.config.get("blocklist_keywords", [])
        blocklist = list(set(global_blocklist + plugin_blocklist))
        
        whitelist = self.config.get("whitelist_keywords", [])
        blocklist_regex = self.config.get("blocklist_regex", "")
        min_length = self.config.get("min_length", 0)

        full_text = f"{message.raw_text or ''}\n{message.caption or ''}".strip()

        # 1. Length check
        if len(full_text) < min_length:
            logging.info(f"[Filter Plugin] Message {message.message_id} skipped: length {len(full_text)} < min_length {min_length}")
            return None

        # 2. Whitelist Check (if configured, message must contain at least one whitelist keyword)
        if whitelist:
            found_whitelist = False
            for kw in whitelist:
                if kw.strip() and kw.lower() in full_text.lower():
                    found_whitelist = True
                    break
            if not found_whitelist:
                logging.info(f"[Filter Plugin] Message {message.message_id} skipped: did not contain any whitelist keywords")
                return None

        # 3. Blacklist Keyword Check
        for kw in blocklist:
            if kw.strip() and kw.lower() in full_text.lower():
                logging.info(f"[Filter Plugin] Message {message.message_id} skipped: matched blacklist keyword '{kw}'")
                return None

        # 4. Blacklist Regex Check
        if blocklist_regex:
            try:
                if re.search(blocklist_regex, full_text, flags=re.IGNORECASE):
                    logging.info(f"[Filter Plugin] Message {message.message_id} skipped: matched blacklist regex '{blocklist_regex}'")
                    return None
            except Exception as e:
                logging.error(f"[Filter Plugin] Invalid blocklist regex '{blocklist_regex}': {e}")

        return message
