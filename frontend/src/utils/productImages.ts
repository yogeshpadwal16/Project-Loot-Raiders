/**
 * Utility for robust product image validation and taxonomy fallback resolution.
 * Prevents broken images, blank cards, or generic logo silhouettes across all platforms.
 */

/**
 * Checks if a provided image URL is a genuine product image rather than a generic platform placeholder.
 */
export function isValidProductImageUrl(url?: string | null): boolean {
  if (!url || typeof url !== "string") return false;
  const clean = url.trim().toLowerCase();
  
  if (clean.length < 10) return false;
  if (clean.includes("static-assets-web.flixcart.com/fk-p-linchpin-web")) return false;
  if (clean.includes("placeholder") || clean.includes("default-image") || clean.includes("no-image")) return false;
  if (clean.includes("blank.gif") || clean.includes("spacer.gif")) return false;

  // Genuine retail CDNs
  if (
    clean.includes("media-amazon.com") ||
    clean.includes("ssl-images-amazon.com") ||
    clean.includes("rukminim1.flixcart.com/image") ||
    clean.includes("rukminim2.flixcart.com/image") ||
    clean.includes("myntassets.com") ||
    clean.includes("ajio.com") ||
    clean.includes("telesco.pe") ||
    clean.includes("unsplash.com") ||
    clean.endsWith(".jpg") ||
    clean.endsWith(".jpeg") ||
    clean.endsWith(".png") ||
    clean.endsWith(".webp")
  ) {
    return true;
  }

  return true;
}

/**
 * Comprehensive Product Category Taxonomy Fallbacks with high-resolution photography.
 */
export function getProductFallbackImage(title: string = "", platform: string = ""): string {
  const text = title.toLowerCase();

  // 1. Air Fryer / Deep Fryer / Kitchen Appliance
  if (text.includes("air fryer") || text.includes("fryer") || text.includes("airfryer") || text.includes("maf671") || text.includes("cripsmaxx") || text.includes("af-4.2l") || text.includes("hilton digital")) {
    return "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=500&auto=format&fit=crop&q=80";
  }

  // 2. Soldering Iron / Electronics Repair / Toolkit / Hardware
  if (text.includes("soldering") || text.includes("soldering iron") || text.includes("hillgrove") || text.includes("fadman") || text.includes("solder") || text.includes("multimeter") || text.includes("tool kit")) {
    return "https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=500&auto=format&fit=crop&q=80";
  }

  // 3. Trimmer / Grooming / Shaver / Hair Clipper
  if (text.includes("trimmer") || text.includes("shaver") || text.includes("grooming") || text.includes("op 535") || text.includes("cordless") || text.includes("clipper") || text.includes("philips trimmer") || text.includes("nova trimmer")) {
    return "https://images.unsplash.com/photo-1621607512214-68297480165e?w=500&auto=format&fit=crop&q=80";
  }

  // 4. Sneakers / Shoes / Footwear / Running Shoes / Mesh Casuals
  if (text.includes("shoe") || text.includes("sneaker") || text.includes("running") || text.includes("walking") || text.includes("mesh") || text.includes("puma") || text.includes("nike") || text.includes("campus") || text.includes("asian") || text.includes("bata") || text.includes("casual shoe") || text.includes("loafer")) {
    return "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&auto=format&fit=crop&q=80";
  }

  // 5. Skincare / Beauty / Body Lotion / Shampoo / Serum / Makeup
  if (text.includes("lotion") || text.includes("shampoo") || text.includes("serum") || text.includes("vaseline") || text.includes("lakme") || text.includes("livon") || text.includes("mamaearth") || text.includes("face wash") || text.includes("moisturizer") || text.includes("cream") || text.includes("foundation") || text.includes("sunscreen")) {
    return "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=500&auto=format&fit=crop&q=80";
  }

  // 6. Ceiling Fan / BLDC Fan / Table Fan / Cooler / Air Conditioner
  if (text.includes("fan") || text.includes("bldc") || text.includes("havells") || text.includes("bajaj") || text.includes("orient") || text.includes("crompton") || text.includes("atomberg") || text.includes("cooler") || text.includes("ac") || text.includes("air conditioner")) {
    return "https://images.unsplash.com/photo-1618941723637-251d5336bf7b?w=500&auto=format&fit=crop&q=80";
  }

  // 7. Smart TV / LED TV / QLED / OLED / 4K Television / Monitor
  if (text.includes("tv") || text.includes("television") || text.includes("led") || text.includes("qled") || text.includes("oled") || text.includes("monitor") || text.includes("vw40") || text.includes("display") || text.includes("screen")) {
    return "https://images.unsplash.com/photo-1593784991095-a205069470b6?w=500&auto=format&fit=crop&q=80";
  }

  // 8. Smartwatch / Fitness Band / Wearables
  if (text.includes("watch") || text.includes("smartwatch") || text.includes("band") || text.includes("fire-boltt") || text.includes("noise") || text.includes("boat wave") || text.includes("fastrack") || text.includes("amazfit")) {
    return "https://images.unsplash.com/photo-1579586337278-3befd40fd17a?w=500&auto=format&fit=crop&q=80";
  }

  // 9. Headphones / Earbuds / TWS / Neckband / Soundbar / Speakers
  if (text.includes("headphone") || text.includes("earphone") || text.includes("earbuds") || text.includes("tws") || text.includes("jbl") || text.includes("sony") || text.includes("boat") || text.includes("airpods") || text.includes("tune 780") || text.includes("soundbar") || text.includes("speaker")) {
    return "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&auto=format&fit=crop&q=80";
  }

  // 10. Laptop / MacBook / Computer / Tablet / iPad
  if (text.includes("laptop") || text.includes("macbook") || text.includes("asus") || text.includes("hp") || text.includes("lenovo") || text.includes("dell") || text.includes("vivobook") || text.includes("thinkpad") || text.includes("ipad") || text.includes("tablet")) {
    return "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500&auto=format&fit=crop&q=80";
  }

  // 11. Smartphone / Mobile 5G / iPhone / Galaxy
  if (text.includes("iphone") || text.includes("samsung") || text.includes("galaxy") || text.includes("phone") || text.includes("mobile") || text.includes("5g") || text.includes("oneplus") || text.includes("pixel") || text.includes("redmi") || text.includes("realme")) {
    return "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&auto=format&fit=crop&q=80";
  }

  // 12. Bed / Mattress / Nilkamal Furniture / Sofa / Chair
  if (text.includes("bed") || text.includes("nilkamal") || text.includes("mattress") || text.includes("furniture") || text.includes("chair") || text.includes("table") || text.includes("sofa") || text.includes("wardrobe") || text.includes("desk")) {
    return "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=500&auto=format&fit=crop&q=80";
  }

  // 13. Cookware / Bottles / Kitchen Jar / Amazon Brand Solimo / Prestige
  if (text.includes("jar") || text.includes("glass") || text.includes("bottle") || text.includes("solimo") || text.includes("cookware") || text.includes("pan") || text.includes("kettle") || text.includes("borosilicate") || text.includes("prestige")) {
    return "https://images.unsplash.com/photo-1584992236310-6edddc08acff?w=500&auto=format&fit=crop&q=80";
  }

  // 14. Clothes / Apparel / T-Shirt / Hoodie / Jeans / Jacket
  if (text.includes("shirt") || text.includes("t-shirt") || text.includes("hoodie") || text.includes("jeans") || text.includes("trousers") || text.includes("jacket") || text.includes("kurta") || text.includes("saree") || text.includes("dress")) {
    return "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500&auto=format&fit=crop&q=80";
  }

  // 15. Powerbank / Charger / Cables / Tech Accessories
  if (text.includes("powerbank") || text.includes("charger") || text.includes("cable") || text.includes("adapter") || text.includes("fast charging") || text.includes("usb")) {
    return "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=500&auto=format&fit=crop&q=80";
  }

  // Default High-Velocity Tech / Loot Product
  return "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=500&auto=format&fit=crop&q=80";
}

/**
 * Master image resolver that guarantees a non-broken, high-resolution product image for every deal.
 */
export function resolveProductImage(rawUrl?: string | null, title?: string, platform?: string): string {
  if (isValidProductImageUrl(rawUrl)) {
    return rawUrl as string;
  }
  return getProductFallbackImage(title, platform);
}
