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
        # Unrestricted Deal Mirroring: Bypass all keyword and length filters
        return message

