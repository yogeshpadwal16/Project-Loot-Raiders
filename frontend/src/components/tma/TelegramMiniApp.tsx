import React, { useEffect, useState } from "react";
import { DealItem } from "../../types/api";
import { ApiClient } from "../../services/api";
import { LootMobileShell } from "../mobile/LootMobileShell";
import { useTheme } from "../../theme/ThemeContext";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void;
        expand: () => void;
        close: () => void;
        setHeaderColor: (color: string) => void;
        setBackgroundColor: (color: string) => void;
        isExpanded: boolean;
        BackButton: {
          show: () => void;
          hide: () => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
        };
        HapticFeedback?: {
          impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
          notificationOccurred: (type: "error" | "success" | "warning") => void;
        };
      };
    };
  }
}

/**
 * Telegram Mini App (TMA) Adapter
 * Shares the exact same LootMobileShell design as PWA, adapted with Telegram WebApp SDK integrations.
 */
export const TelegramMiniApp: React.FC = () => {
  const [deals, setDeals] = useState<DealItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"public" | "lootmap" | "admin" | "brain" | "tma">("public");
  const { theme } = useTheme();

  const loadDeals = () => {
    setLoading(true);
    ApiClient.fetchPublicDeals(50)
      .then(setDeals)
      .catch((err) => console.warn("TMA deal fetch error:", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDeals();

    // Telegram WebApp Initialization
    const tg = window.Telegram?.WebApp;
    if (tg) {
      try {
        tg.ready();
        tg.expand();
      } catch (err) {
        console.warn("Telegram WebApp init error:", err);
      }
    }
  }, []);

  // Sync Telegram Header & Background Color with Theme
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      const bgColor = theme === "dark" ? "#020617" : "#f8fafc";
      try {
        tg.setHeaderColor(bgColor);
        tg.setBackgroundColor(bgColor);
      } catch (e) {}
    }
  }, [theme]);

  // Handle Telegram Back Button
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg && tg.BackButton) {
      if (activeTab !== "public") {
        tg.BackButton.show();
        const handleBack = () => setActiveTab("public");
        tg.BackButton.onClick(handleBack);
        return () => {
          tg.BackButton.offClick(handleBack);
          tg.BackButton.hide();
        };
      } else {
        tg.BackButton.hide();
      }
    }
  }, [activeTab]);

  return (
    <div className="telegram-safe-area-wrapper min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <LootMobileShell
        deals={deals}
        loading={loading}
        onRefresh={loadDeals}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        isTMA={false}
      />
    </div>
  );
};
