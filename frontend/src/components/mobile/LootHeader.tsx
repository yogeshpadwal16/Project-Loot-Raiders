import React from "react";
import { LootBrand } from "./LootBrand";
import { ThemeToggle } from "../common/ThemeToggle";

interface LootHeaderProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const LootHeader: React.FC<LootHeaderProps> = () => {
  return (
    <header className="sticky top-0 z-40 bg-white/95 dark:bg-slate-950/95 backdrop-blur-lg border-b border-slate-200/80 dark:border-slate-800/80 px-4 py-3 transition-colors pt-[max(0.75rem,env(safe-area-inset-top))]">
      <div className="flex items-center justify-between">
        {/* Brand Logo & Tagline */}
        <LootBrand size="md" showTagline={true} />

        {/* Illustrated Day/Night Toggle */}
        <div className="flex items-center gap-2">
          <ThemeToggle size="sm" />
        </div>
      </div>
    </header>
  );
};
