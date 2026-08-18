/**
 * Title sanitization and normalization utility for Loot Raiders.
 * Cleans SEO keyword stuffing, strips raw pipe delimiters, normalizes capitalization,
 * and produces clean, human-readable product names.
 */

export function sanitizeTitle(rawTitle?: string | null): string {
  if (!rawTitle || typeof rawTitle !== "string") return "Featured Loot Deal";

  let title = rawTitle.trim();

  // 1. Replace raw pipes, underscores, and awkward delimiters with clean spaces or hyphens
  title = title.replace(/[|│｜]+/g, " ");
  title = title.replace(/_+/g, " ");
  title = title.replace(/\s*-\s*-\s*/g, " - ");
  title = title.replace(/\s*,\s*,+/g, ", ");

  // 2. Remove common SEO keyword stuffing patterns
  // e.g., "Lightweight Comfort Summer Trendy Walking Outdoor Lace Up Classy..."
  const seoKeywords = [
    /\b(lightweight)\s+(comfort)\s+(summer)\s+(trendy)\b/gi,
    /\b(for men & women|for men and women|for boys and girls)\b/gi,
    /\b(100% genuine|best quality|top rated|super hit|hot deal)\b/gi,
  ];

  for (const pattern of seoKeywords) {
    title = title.replace(pattern, "");
  }

  // 3. Compress multiple spaces
  title = title.replace(/\s+/g, " ").trim();

  // 4. Proper Casing if all lowercase (e.g. "clearance sale" -> "Clearance Sale")
  if (title === title.toLowerCase()) {
    title = title
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

  // 5. Clean up trailing / leading punctuation
  title = title.replace(/^[\s,.\-–—/]+/, "").replace(/[\s,.\-–—/]+$/, "");

  return title || "Featured Loot Deal";
}
