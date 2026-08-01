from abc import ABC, abstractmethod
from typing import Optional
from deal_engine.mirroring.schemas import NormalizedMessage

class MirrorPlugin(ABC):
    """
    Base class for all message-processing plugins, inspired by tgcf.
    Each plugin takes a NormalizedMessage, processes/modifies it,
    and returns the modified NormalizedMessage, or None if the message
    should be filtered out/dropped from the pipeline.
    """
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", False)

    @abstractmethod
    def apply(self, message: NormalizedMessage) -> Optional[NormalizedMessage]:
        """
        Apply the plugin's logic to the given message.
        """
        pass
