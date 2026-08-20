from utils.affiliate import get_best_affiliate_url, generate_auto_cart_url
from utils.normalizer import get_canonical_product_id
from config.settings import load_settings

def monetize_url(url: str, platform_hint: str = None) -> tuple:
    """
    Synchronous monetization helper.
    Returns:
        tuple: (monetized_url, platform, auto_cart_url)
    """
    _, platform = get_canonical_product_id(url)
    if not platform:
        platform = platform_hint or "generic"
        
    settings = load_settings()
    monetized = get_best_affiliate_url(url, platform, settings)
    auto_cart = generate_auto_cart_url(url, platform, settings)
    return monetized, platform, auto_cart
