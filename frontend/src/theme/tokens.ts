/**
 * Centralized Design System Tokens for Project Loot Raiders.
 * Enforces Dark Mode first, semantic status colors, typography scales, and merchant branding.
 */

export const DESIGN_TOKENS = {
  colors: {
    bg: {
      dark: "#0b0f19",
      darker: "#070a10",
      card: "#131b2e",
      cardHover: "#1c2842",
    },
    border: {
      subtle: "rgba(255, 255, 255, 0.08)",
      active: "rgba(249, 115, 22, 0.4)",
    },
    text: {
      primary: "#f8fafc",
      secondary: "#94a3b8",
      muted: "#64748b",
      inverse: "#0f172a",
    },
    accent: {
      lootOrange: "#f97316",
      lootOrangeDark: "#ea580c",
      verifiedGreen: "#22c55e",
      glitchRed: "#ef4444",
      scoreGold: "#eab308",
    },
    merchant: {
      amazon: "#ff9900",
      flipkart: "#2874f0",
      myntra: "#ff3f6c",
      snapdeal: "#e40046",
      telegram: "#0088cc",
      generic: "#8b5cf6",
    },
  },
  typography: {
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
    fontSize: {
      xs: "0.75rem",
      sm: "0.875rem",
      base: "1rem",
      lg: "1.125rem",
      xl: "1.25rem",
      "2xl": "1.5rem",
      "3xl": "1.875rem",
      "4xl": "2.25rem",
    },
    fontWeight: {
      normal: "400",
      medium: "500",
      semibold: "600",
      bold: "700",
      black: "900",
    },
  },
  densityModes: {
    compact: {
      padding: "0.5rem 0.75rem",
      cardHeight: "140px",
      fontSize: "0.875rem",
    },
    detailed: {
      padding: "1rem 1.25rem",
      cardHeight: "auto",
      fontSize: "1rem",
    },
  },
};
