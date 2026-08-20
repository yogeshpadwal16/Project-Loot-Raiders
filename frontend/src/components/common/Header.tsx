import React from "react";
import { BrandLogo } from "./BrandLogo";
import { ThemeToggle } from "./ThemeToggle";
import {
  Zap,
  MapPin,
  Cpu,
  Shield,
  Command,
  LogOut,
  Sparkles,
} from "lucide-react";

interface HeaderProps {
  activeTab: "public" | "lootmap" | "admin" | "brain" | "tma";
  setActiveTab: (tab: "public" | "lootmap" | "admin" | "brain" | "tma") => void;
  brainOnline: boolean;
  onOpenCommandPalette?: () => void;
  density?: "compact" | "comfortable" | "expanded";
  onToggleDensity?: () => void;
  onLogout?: () => void;
}

/**
 * Redesigned Premium Desktop Top Header
 * Clean, uncluttered, distinctive branding with central nav, utility indicators, and illustrated ThemeToggle.
 */
export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  brainOnline,
  onOpenCommandPalette,
  onLogout,
}) => {
  return (
    <header className="sticky top-0 z-40 bg-white/95 dark:bg-slate-950/90 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800/80 text-slate-900 dark:text-slate-100 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        
        {/* LEFT: Unified Brand Crest + Wordmark + Tagline */}
        <div
          onClick={() => setActiveTab("public")}
          className="cursor-pointer group flex items-center shrink-0"
        >
          <BrandLogo variant="full" size="md" subtitle="Best Deals. Zero Nonsense." />
        </div>

        {/* CENTER: Clean, Uncluttered Navigation Links */}
        <nav className="hidden md:flex items-center gap-1.5">
          <button
            onClick={() => setActiveTab("public")}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === "public"
                ? "text-orange-500 bg-orange-500/10 font-extrabold shadow-sm"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-900"
            }`}
          >
            <Zap className={`w-3.5 h-3.5 ${activeTab === "public" ? "text-orange-500" : ""}`} />
            Live Deals
          </button>

          <button
            onClick={() => setActiveTab("lootmap")}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === "lootmap"
                ? "text-orange-500 bg-orange-500/10 font-extrabold shadow-sm"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-900"
            }`}
          >
            <MapPin className={`w-3.5 h-3.5 ${activeTab === "lootmap" ? "text-orange-500" : ""}`} />
            Loot Map
          </button>

          <button
            onClick={() => setActiveTab("brain")}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === "brain"
                ? "text-orange-500 bg-orange-500/10 font-extrabold shadow-sm"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-900"
            }`}
          >
            <Cpu className={`w-3.5 h-3.5 ${activeTab === "brain" ? "text-orange-500" : ""}`} />
            AI Brain
          </button>

          <button
            onClick={() => setActiveTab("admin")}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === "admin"
                ? "text-orange-500 bg-orange-500/10 font-extrabold shadow-sm"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-900"
            }`}
          >
            <Shield className={`w-3.5 h-3.5 ${activeTab === "admin" ? "text-orange-500" : ""}`} />
            Telemetry
          </button>
        </nav>

        {/* RIGHT: Utility Controls + Illustrated Day/Night Toggle */}
        <div className="flex items-center gap-2.5 shrink-0">
          {/* Cmd+K Quick Commands */}
          {onOpenCommandPalette && (
            <button
              onClick={onOpenCommandPalette}
              className="hidden sm:flex items-center gap-2 px-2.5 py-1.5 rounded-xl text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-900 transition-all font-mono border border-transparent hover:border-slate-200 dark:hover:border-slate-800"
              title="Open Command Palette (Cmd + K)"
            >
              <Command className="w-3.5 h-3.5 text-orange-500" />
              <span className="hidden lg:inline text-[11px]">Commands</span>
              <kbd className="bg-slate-200/80 dark:bg-slate-800 text-[10px] text-slate-600 dark:text-slate-400 px-1.5 py-0.5 rounded border border-slate-300 dark:border-slate-700 font-mono">
                ⌘K
              </kbd>
            </button>
          )}

          {/* AI Intelligence Live Indicator */}
          <div className="hidden lg:flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-slate-100/80 dark:bg-slate-900/80 border border-slate-200/60 dark:border-slate-800/60">
            <span
              className={`w-2 h-2 rounded-full ${
                brainOnline ? "bg-emerald-500 animate-pulse shadow-[0_0_8px_#10b981]" : "bg-amber-500"
              }`}
            />
            <span className="text-[11px] font-mono font-medium text-slate-700 dark:text-slate-300">
              {brainOnline ? "AI Active" : "Online"}
            </span>
          </div>

          {/* Telegram Mini App Shortcut */}
          <button
            onClick={() => setActiveTab("tma")}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-bold text-orange-600 dark:text-orange-400 bg-orange-500/10 hover:bg-orange-500/20 border border-orange-500/20 transition-all"
            title="Open Telegram Mini App View"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">TMA</span>
          </button>

          {/* EXACT Illustrated Day / Night Sky Toggle */}
          <ThemeToggle size="sm" />

          {/* Owner Logout Control */}
          {onLogout && (
            <button
              onClick={onLogout}
              className="p-1.5 rounded-xl text-slate-500 dark:text-slate-400 hover:text-rose-500 dark:hover:text-rose-400 hover:bg-rose-500/10 transition-all"
              title="Logout from Command Console"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
