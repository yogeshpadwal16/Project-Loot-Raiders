/**
 * Utility for robust product fallback image resolution based on item title & category.
 * Prevents broken images or identical default images across different product types.
 */

export function getProductFallbackImage(title: string = "", platform: string = ""): string {
  const text = title.toLowerCase();

  // Smart Watch / Wearables
  if (text.includes("watch") || text.includes("smartwatch") || text.includes("band") || text.includes("fire-boltt") || text.includes("noise") || text.includes("boat wave")) {
    return "https://images.unsplash.com/photo-1579586337278-3befd40fd17a?w=400&auto=format&fit=crop&q=80";
  }

  // Ceiling Fan / Home Appliances
  if (text.includes("fan") || text.includes("bldc") || text.includes("havells") || text.includes("orient") || text.includes("crompton")) {
    return "https://images.unsplash.com/photo-1618941723637-251d5336bf7b?w=400&auto=format&fit=crop&q=80";
  }

  // Bed / Furniture / Mattress
  if (text.includes("bed") || text.includes("nilkamal") || text.includes("furniture") || text.includes("chair") || text.includes("table") || text.includes("sofa")) {
    return "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=400&auto=format&fit=crop&q=80";
  }

  // TV / Smart TV / Display
  if (text.includes("tv") || text.includes("television") || text.includes("led") || text.includes("monitor") || text.includes("screen")) {
    return "https://images.unsplash.com/photo-1593784991095-a205069470b6?w=400&auto=format&fit=crop&q=80";
  }

  // Laptop / Computer
  if (text.includes("laptop") || text.includes("macbook") || text.includes("asus") || text.includes("hp") || text.includes("lenovo") || text.includes("dell") || text.includes("vivobook")) {
    return "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400&auto=format&fit=crop&q=80";
  }

  // Smartphone / Mobile
  if (text.includes("iphone") || text.includes("samsung") || text.includes("galaxy") || text.includes("phone") || text.includes("mobile") || text.includes("5g") || text.includes("oneplus") || text.includes("pixel")) {
    return "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400&auto=format&fit=crop&q=80";
  }

  // Headphones / Earbuds / Audio
  if (text.includes("headphone") || text.includes("earphone") || text.includes("earbuds") || text.includes("sony") || text.includes("jbl") || text.includes("airpods") || text.includes("speaker")) {
    return "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&auto=format&fit=crop&q=80";
  }

  // Shoes / Footwear / Fashion
  if (text.includes("shoe") || text.includes("sneaker") || text.includes("puma") || text.includes("nike") || text.includes("adidas") || text.includes("running") || text.includes("shirt") || text.includes("t-shirt")) {
    return "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400&auto=format&fit=crop&q=80";
  }

  // Default Tech / Gadget Fallback
  return "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=400&auto=format&fit=crop&q=80";
}
