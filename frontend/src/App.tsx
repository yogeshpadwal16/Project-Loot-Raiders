import React, { useEffect, useState } from "react";
import { ThemeProvider } from "./theme/ThemeContext";
import { AuthScreen } from "./components/auth/AuthScreen";
import { Header } from "./components/common/Header";
import { CommandPalette } from "./components/common/CommandPalette";
import { LootRadar } from "./components/dashboard/LootRadar";
import { BentoSummary } from "./components/dashboard/BentoSummary";
import { TopLootCard } from "./components/dashboard/TopLootCard";
import { LootDealCard } from "./components/deals/LootDealCard";
import { PriceHistoryModal } from "./components/deals/PriceHistoryModal";
import { LootMap } from "./components/deals/LootMap";
import { HealthMonitor } from "./components/admin/HealthMonitor";
import { LootDataTable } from "./components/admin/LootDataTable";
import { BrainConsole } from "./components/brain/BrainConsole";
import { TelegramMiniApp } from "./components/tma/TelegramMiniApp";
import { LootMobileShell } from "./components/mobile/LootMobileShell";
import { DealItem } from "./types/api";
import { ApiClient } from "./services/api";
import { getEffectiveDealScore } from "./utils/scoreDecay";
import { Zap, Search, SlidersHorizontal, RefreshCw, Layers } from "lucide-react";

export function AppContent() {
  // Session State
  const [token, setToken] = useState<string | null>(() => {
    try {
      return localStorage.getItem("loot_session_token");
    } catch {
      return null;
    }
  });

  const [activeTab, setActiveTab] = useState<"public" | "lootmap" | "admin" | "brain" | "tma">("public");
  const [deals, setDeals] = useState<DealItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedChartDeal, setSelectedChartDeal] = useState<DealItem | null>(null);
  const [brainOnline, setBrainOnline] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [density, setDensity] = useState<"compact" | "comfortable" | "expanded">("comfortable");

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedMerchant, setSelectedMerchant] = useState<string>("all");

  const [systemStatus, setSystemStatus] = useState<{
    telegramStatus: string;
    scraperFleetStatus: string;
    scraperFleetCount: string;
  }>({
    telegramStatus: "Connected",
    scraperFleetStatus: "Engine Active",
    scraperFleetCount: "14/14"
  });
  const [fetchError, setFetchError] = useState<string | null>(null);

  const cycleDensity = () => {
    if (density === "comfortable") setDensity("compact");
    else if (density === "compact") setDensity("expanded");
    else setDensity("comfortable");
  };

  const handleLoginSuccess = (newToken: string) => {
    try {
      localStorage.setItem("loot_session_token", newToken);
    } catch {}
    setToken(newToken);
  };

  const handleLogout = () => {
    try {
      localStorage.removeItem("loot_session_token");
    } catch {}
    setToken(null);
  };

  const loadDeals = () => {
    setLoading(true);
    setFetchError(null);
    ApiClient.fetchPublicDeals(100)
      .then((data) => {
        setDeals(data || []);
        setFetchError(null);
      })
      .catch((err) => {
        console.warn("Deal fetch error:", err);
        setFetchError(err?.message || "Failed to load live deals");
      })
      .finally(() => setLoading(false));

    ApiClient.fetchBrainStatus()
      .then((res) => setBrainOnline(res.status === "ONLINE"))
      .catch(() => setBrainOnline(false));

    ApiClient.fetchStatus()
      .then((statusData: any) => {
        const healthMap = statusData?.crawler_health || {};
        const fleetKeys = Object.keys(healthMap);
        if (fleetKeys.length > 0) {
          const healthyCount = fleetKeys.filter((k: string) => healthMap[k]?.status === "Healthy").length;
          setSystemStatus({
            telegramStatus: statusData?.is_running ? "Connected" : "Standby",
            scraperFleetStatus: `${healthyCount}/${fleetKeys.length} Online`,
            scraperFleetCount: `${healthyCount}/${fleetKeys.length}`
          });
        } else {
          setSystemStatus({
            telegramStatus: statusData?.is_running ? "Connected" : "Standby",
            scraperFleetStatus: statusData?.is_running ? "Scanners Operating" : "Scanners Paused",
            scraperFleetCount: statusData?.is_running ? "Active" : "Paused"
          });
        }
      })
      .catch(() => {
        setSystemStatus({
          telegramStatus: "Not reported",
          scraperFleetStatus: "Unavailable",
          scraperFleetCount: "--/--"
        });
      });
  };

  useEffect(() => {
    if (token) {
      loadDeals();

      // SSE Realtime Deal Stream
      const sse = new EventSource("/api/deals/stream");
      sse.onmessage = (evt) => {
        try {
          const newDeal = JSON.parse(evt.data);
          if (newDeal && newDeal.title) {
            setDeals((prev) => [newDeal, ...prev]);
          }
        } catch (err) {}
      };

      return () => sse.close();
    }
  }, [token]);

  // Detect Telegram Mini App (TMA) mode
  const isTmaMode = () => {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const hash = window.location.hash || "";
      const isTg = !!((window as any).Telegram?.WebApp?.initData || urlParams.get("tgWebAppData") || urlParams.get("tgWebAppPlatform"));
      const isExplicitTma = urlParams.get("tma") === "1" || urlParams.get("tab") === "tma" || hash.includes("tma");
      return isTg || isExplicitTma;
    } catch {
      return false;
    }
  };

  if (isTmaMode() || activeTab === "tma") {
    return <TelegramMiniApp />;
  }

  if (!token) {
    return <AuthScreen onLoginSuccess={handleLoginSuccess} />;
  }

  const filteredDeals = deals.filter((d) => {
    const matchesSearch =
      d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.platform.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesMerchant =
      selectedMerchant === "all" ||
      d.platform.toLowerCase().includes(selectedMerchant.toLowerCase());
    return matchesSearch && matchesMerchant;
  });

  // Calculate real metrics for Loot Radar
  const hotDealsCount = deals.filter((d) => d.deal_score >= 80).length;
  const historicalLowsCount = deals.filter((d) => d.is_verified_low).length;
  const priceCrashesCount = deals.filter((d) => d.discount >= 50).length;
  const avgLootScore =
    deals.length > 0
      ? Math.round(deals.reduce((acc, d) => acc + (d.deal_score || 0), 0) / deals.length)
      : 0;
  const verifiedSavingsTotal = deals.reduce(
    (acc, d) => acc + Math.max(0, (d.mrp || 0) - (d.price || 0)),
    0
  );

  // Highest effective scoring deal for TopLoot hero feature card (factoring in temporal decay)
  const topDeal =
    deals.length > 0
      ? [...deals].sort((a, b) => getEffectiveDealScore(b) - getEffectiveDealScore(a))[0]
      : null;

  const gridColsClass =
    density === "compact"
      ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3"
      : density === "expanded"
      ? "grid-cols-1 md:grid-cols-2 gap-6"
      : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5";

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors">
      
      {/* 1. MOBILE EXPERIENCE (< 768px: Dedicated Consumer Deal Discovery Shell) */}
      <div className="block md:hidden">
        <LootMobileShell
          deals={deals}
          loading={loading}
          onRefresh={loadDeals}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
        />
      </div>

      {/* 2. DESKTOP EXPERIENCE (>= 768px: Approved Operational Interface + Redesigned Header) */}
      <div className="hidden md:block">
        {/* Redesigned Desktop Top Header */}
        <Header
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          brainOnline={brainOnline}
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
          density={density}
          onToggleDensity={cycleDensity}
          onLogout={handleLogout}
        />

        {/* Existing Desktop Content (Intact & Untouched) */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* PUBLIC LIVE DEALS DISCOVERY PLATFORM */}
          {activeTab === "public" && (
            <div className="space-y-6">
              {/* 1. Loot Radar Component */}
              <LootRadar
                stats={{
                  totalDeals: deals.length,
                  hotDealsCount,
                  historicalLowsCount,
                  priceCrashesCount,
                  avgLootScore,
                  verifiedSavingsTotal,
                  telegramStatus: systemStatus.telegramStatus,
                  scraperFleetStatus: systemStatus.scraperFleetStatus,
                }}
              />

              {/* 2. Bento Summary Component */}
              <BentoSummary
                hotCount={hotDealsCount}
                lowsCount={historicalLowsCount}
                crashesCount={priceCrashesCount}
                aiOpportunitiesCount={hotDealsCount}
                scraperFleetCount={systemStatus.scraperFleetCount}
              />

              {/* 3. Top Loot Hero Feature Card */}
              {topDeal && (
                <TopLootCard
                  deal={topDeal}
                  onOpenHistory={(id) => {
                    const target = deals.find((d) => d.id === id);
                    if (target) setSelectedChartDeal(target);
                  }}
                />
              )}

              {/* 4. Search & Filter Bar */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-3.5 shadow-md flex flex-col md:flex-row items-center justify-between gap-3">
                <div className="relative w-full md:w-96">
                  <Search className="w-4 h-4 text-orange-500 absolute left-3.5 top-3" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search deals by title, merchant, or ASIN..."
                    className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-orange-500 transition-all font-mono"
                  />
                </div>

                {/* Merchant Filter Pills */}
                <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
                  {["all", "amazon", "flipkart", "myntra", "ajio"].map((merch) => (
                    <button
                      key={merch}
                      onClick={() => setSelectedMerchant(merch)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold capitalize transition-all border shrink-0 ${
                        selectedMerchant === merch
                          ? "bg-orange-500 text-white border-orange-500 shadow-md shadow-orange-500/20"
                          : "bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:text-slate-900 dark:hover:text-white"
                      }`}
                    >
                      {merch}
                    </button>
                  ))}

                  <button
                    onClick={cycleDensity}
                    title="Toggle layout density"
                    className="px-3 py-1.5 bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 rounded-xl text-xs font-mono font-medium shrink-0 flex items-center gap-1.5"
                  >
                    <Layers className="w-3.5 h-3.5 text-orange-500" />
                    <span className="capitalize">{density}</span>
                  </button>

                  <button
                    onClick={loadDeals}
                    className="p-2 bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 rounded-xl transition-all shrink-0"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
                  </button>
                </div>
              </div>

              {/* 5. Live Deals Matrix Grid */}
              {loading ? (
                <div className="py-24 text-center space-y-3">
                  <Zap className="w-10 h-10 text-orange-500 animate-bounce mx-auto" />
                  <p className="text-sm font-bold text-slate-600 dark:text-slate-300 font-mono">
                    Fetching Live AI Verified Deals...
                  </p>
                </div>
              ) : fetchError && deals.length === 0 ? (
                <div className="py-24 text-center bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/50 rounded-2xl p-8 space-y-3 shadow-md">
                  <Zap className="w-10 h-10 text-amber-500 mx-auto" />
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    Reconnecting to Ingestion Engine
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
                    The backend crawler is actively processing deals. Snapshot fallback will load automatically when available.
                  </p>
                  <button
                    onClick={loadDeals}
                    className="mt-2 px-4 py-2 bg-orange-500 text-white rounded-xl text-xs font-mono font-bold hover:bg-orange-600 transition-all shadow-md shadow-orange-500/20"
                  >
                    Retry Connection
                  </button>
                </div>
              ) : filteredDeals.length === 0 ? (
                <div className="py-24 text-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 space-y-3 shadow-md">
                  <SlidersHorizontal className="w-10 h-10 text-slate-400 mx-auto" />
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    No Deals Match Your Filter
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Try clearing your search query or selecting a different merchant.
                  </p>
                </div>
              ) : (
                <div className={`grid ${gridColsClass}`}>
                  {filteredDeals.map((deal) => (
                    <LootDealCard
                      key={deal.id}
                      deal={deal}
                      density={density}
                      onOpenChart={(d) => setSelectedChartDeal(d)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* LOOT MAP */}
          {activeTab === "lootmap" && <LootMap />}

          {/* TELEMETRY & ADMIN CONTROL CENTER */}
          {activeTab === "admin" && (
            <div className="space-y-6">
              <HealthMonitor />
              <LootDataTable data={deals} onRefresh={loadDeals} />
            </div>
          )}

          {/* LOOT BRAIN AI CONSOLE */}
          {activeTab === "brain" && <BrainConsole />}
        </main>
      </div>

      {/* Global Command Palette */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onSelectTab={(tab) => {
          if (tab !== "scratch") setActiveTab(tab);
        }}
        onToggleDensity={setDensity}
      />

      {/* Modals */}
      {selectedChartDeal && (
        <PriceHistoryModal deal={selectedChartDeal} onClose={() => setSelectedChartDeal(null)} />
      )}
    </div>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}
