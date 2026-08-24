import React, { useState } from "react";
import { DealItem } from "../../types/api";
import { LootHeader } from "./LootHeader";
import { DealSearch } from "./DealSearch";
import { CategoryScroller } from "./CategoryScroller";
import { FeaturedDeal } from "./FeaturedDeal";
import { DealCard } from "./DealCard";
import { MobileBottomNav } from "./MobileBottomNav";
import { LootMap } from "../deals/LootMap";
import { BrainConsole } from "../brain/BrainConsole";
import { HealthMonitor } from "../admin/HealthMonitor";
import { getEffectiveDealScore } from "../../utils/scoreDecay";
import { Zap, SlidersHorizontal, RefreshCw } from "lucide-react";

interface LootMobileShellProps {
  deals: DealItem[];
  loading: boolean;
  onRefresh?: () => void;
  activeTab?: "public" | "lootmap" | "admin" | "brain" | "tma";
  onSelectTab?: (tab: "public" | "lootmap" | "admin" | "brain" | "tma") => void;
  isTMA?: boolean;
}

export const LootMobileShell: React.FC<LootMobileShellProps> = ({
  deals,
  loading,
  onRefresh,
  activeTab: externalActiveTab,
  onSelectTab: externalSelectTab,
  isTMA = false,
}) => {
  const [internalActiveTab, setInternalActiveTab] = useState<"public" | "lootmap" | "admin" | "brain" | "tma">("public");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");

  const activeTab = externalActiveTab || internalActiveTab;
  const setActiveTab = externalSelectTab || setInternalActiveTab;

  // Filter deals by search query and category
  const filteredDeals = deals.filter((d) => {
    const text = (d.title + " " + d.platform).toLowerCase();
    const matchesSearch = text.includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;
    if (selectedCategory === "all") return true;

    if (selectedCategory === "electronics") {
      return (
        text.includes("tv") ||
        text.includes("laptop") ||
        text.includes("mobile") ||
        text.includes("phone") ||
        text.includes("camera") ||
        text.includes("speaker")
      );
    }
    if (selectedCategory === "wearables") {
      return text.includes("watch") || text.includes("smartwatch") || text.includes("band");
    }
    if (selectedCategory === "audio") {
      return (
        text.includes("headphone") ||
        text.includes("earbuds") ||
        text.includes("airpods") ||
        text.includes("earphone") ||
        text.includes("soundbar")
      );
    }
    if (selectedCategory === "laptops") {
      return (
        text.includes("laptop") ||
        text.includes("macbook") ||
        text.includes("asus") ||
        text.includes("hp") ||
        text.includes("lenovo") ||
        text.includes("dell")
      );
    }
    if (selectedCategory === "fashion") {
      return (
        text.includes("shoe") ||
        text.includes("sneaker") ||
        text.includes("shirt") ||
        text.includes("dress") ||
        text.includes("puma") ||
        text.includes("nike")
      );
    }
    if (selectedCategory === "home") {
      return (
        text.includes("fan") ||
        text.includes("bed") ||
        text.includes("furniture") ||
        text.includes("kitchen") ||
        text.includes("fryer") ||
        text.includes("cooker")
      );
    }

    return true;
  });

  // Top featured deal (highest effective score factoring in temporal decay)
  const featuredDeal =
    filteredDeals.length > 0
      ? [...filteredDeals].sort((a, b) => getEffectiveDealScore(b) - getEffectiveDealScore(a))[0]
      : null;

  const remainingDeals = featuredDeal
    ? filteredDeals.filter((d) => d.id !== featuredDeal.id)
    : filteredDeals;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors pb-24">
      {/* Mobile Top Header */}
      <LootHeader />

      {/* Main Content Area */}
      <main className="flex-1 px-3.5 pt-3 max-w-lg mx-auto w-full space-y-4">
        {/* PUBLIC DEALS VIEW */}
        {activeTab === "public" && (
          <>
            {/* 1. Search Bar */}
            <DealSearch
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search 100+ verified live loot deals..."
            />

            {/* 2. Category Scroller */}
            <CategoryScroller
              selectedCategory={selectedCategory}
              onSelectCategory={setSelectedCategory}
            />

            {/* 3. Loading State */}
            {loading ? (
              <div className="py-20 text-center space-y-3">
                <Zap className="w-8 h-8 text-orange-500 animate-bounce mx-auto" />
                <p className="text-xs font-bold text-slate-500 dark:text-slate-400">
                  Scanning live deals across platforms...
                </p>
              </div>
            ) : filteredDeals.length === 0 ? (
              <div className="py-16 text-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 space-y-2.5 shadow-sm">
                <SlidersHorizontal className="w-8 h-8 text-slate-400 mx-auto" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  No matching deals found
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Try clearing your search term or choosing "All Deals".
                </p>
                <button
                  onClick={() => {
                    setSearchQuery("");
                    setSelectedCategory("all");
                    if (onRefresh) onRefresh();
                  }}
                  className="mt-2 inline-flex items-center gap-1.5 px-3.5 py-2 bg-orange-500 text-white rounded-xl text-xs font-bold shadow-md shadow-orange-500/20"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Reset Filter
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {/* 4. Featured Spotlight Deal */}
                {featuredDeal && !searchQuery && selectedCategory === "all" && (
                  <FeaturedDeal deal={featuredDeal} />
                )}

                {/* 5. Hot Deals Feed Header */}
                <div className="flex items-center justify-between pt-1">
                  <h2 className="text-xs font-black uppercase tracking-wider text-slate-700 dark:text-slate-300">
                    🔥 Verified Live Deals ({filteredDeals.length})
                  </h2>
                  {onRefresh && (
                    <button
                      onClick={onRefresh}
                      className="text-xs text-orange-500 hover:text-orange-600 font-bold flex items-center gap-1"
                    >
                      <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
                      Refresh
                    </button>
                  )}
                </div>

                {/* 6. Product Cards Grid (1 column on small mobile, 2 columns on >= 380px) */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {(searchQuery || selectedCategory !== "all" ? filteredDeals : remainingDeals).map(
                    (deal) => (
                      <DealCard key={deal.id} deal={deal} />
                    )
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {/* LOOT MAP */}
        {activeTab === "lootmap" && (
          <div className="pt-1">
            <LootMap />
          </div>
        )}

        {/* AI BRAIN */}
        {activeTab === "brain" && (
          <div className="pt-1">
            <BrainConsole />
          </div>
        )}

        {/* TELEMETRY */}
        {activeTab === "admin" && (
          <div className="pt-1 space-y-4">
            <HealthMonitor />
          </div>
        )}
      </main>

      {/* Thumb-Friendly Bottom Navigation (if not in single-tab TMA mode) */}
      {!isTMA && (
        <MobileBottomNav activeTab={activeTab} setActiveTab={setActiveTab} />
      )}
    </div>
  );
};
