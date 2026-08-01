import logging
from typing import Optional, List
from deal_engine.mirroring.schemas import NormalizedMessage
from deal_engine.mirroring.plugins.base import MirrorPlugin
from deal_engine.mirroring.plugins.filter import FilterPlugin
from deal_engine.mirroring.plugins.replace import ReplacePlugin
from deal_engine.mirroring.plugins.format import FormatPlugin
from deal_engine.mirroring.plugins.ocr import OCRPlugin
import config.settings

# Global registry of loaded plugins
_loaded_plugins: List[MirrorPlugin] = []

def get_default_plugin_config() -> dict:
    """Return default configuration for tgcf-inspired plugins."""
    return {
        "filter": {
            "enabled": True,
            "blocklist_keywords": [],
            "whitelist_keywords": [],
            "min_length": 10
        },
        "replace": {
            "enabled": True,
            "patterns": [
                # Clean competitor bot mentions and Telegram handles
                {"find": r"t\.me/[a-zA-Z0-9_\+]+", "replace": "", "regex": True},
                {"find": r"telegram\.me/[a-zA-Z0-9_\+]+", "replace": "", "regex": True},
                {"find": r"@[a-zA-Z0-9_]+", "replace": "", "regex": True},
                # Clean common promotional footer strings
                {"find": r"(?i)join\s+our\s+channel", "replace": "", "regex": True},
                {"find": r"(?i)subscribe\s+now", "replace": "", "regex": True},
                {"find": r"(?i)loot\s+alerts?", "replace": "", "regex": True}
            ]
        },
        "format": {
            "enabled": False,
            "header": "🔥 [LOOT DEAL] 🔥\n",
            "footer": "\n\n👉 Join @LootRaidersDeals for more deals!"
        },
        "ocr": {
            "enabled": False,
            "tesseract_path": ""
        }
    }

def initialize_plugins():
    """Load and instantiate plugins based on settings.json configuration."""
    global _loaded_plugins
    _loaded_plugins = []
    
    settings = config.settings.load_settings()
    plugin_config = settings.get("mirror_plugins", get_default_plugin_config())
    
    logging.info("[Plugins Engine] Initializing tgcf-inspired plugins...")
    
    # 1. Filter Plugin
    filter_conf = plugin_config.get("filter", {"enabled": True})
    _loaded_plugins.append(FilterPlugin(filter_conf))
    
    # 2. Replace Plugin
    replace_conf = plugin_config.get("replace", {"enabled": True})
    _loaded_plugins.append(ReplacePlugin(replace_conf))
    
    # 3. OCR Plugin
    ocr_conf = plugin_config.get("ocr", {"enabled": False})
    _loaded_plugins.append(OCRPlugin(ocr_conf))
    
    # 4. Format Plugin
    format_conf = plugin_config.get("format", {"enabled": False})
    _loaded_plugins.append(FormatPlugin(format_conf))
    
    logging.info(f"[Plugins Engine] Loaded {len(_loaded_plugins)} plugins.")

def apply_plugins(message: NormalizedMessage) -> Optional[NormalizedMessage]:
    """
    Passes a NormalizedMessage through the pipeline of active plugins.
    If any plugin returns None, the message is filtered out.
    """
    global _loaded_plugins
    # Lazy initialization if not already loaded
    if not _loaded_plugins:
        initialize_plugins()
        
    current_msg = message
    for plugin in _loaded_plugins:
        if not plugin.enabled:
            continue
        try:
            current_msg = plugin.apply(current_msg)
            if current_msg is None:
                # Filtered out / dropped
                return None
        except Exception as e:
            logging.error(f"[Plugins Engine] Error applying plugin {plugin.__class__.__name__}: {e}")
            
    return current_msg
