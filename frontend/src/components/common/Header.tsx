import React from "react";
import { BrandLogo } from "./BrandLogo";
import { useTheme } from "../../theme/ThemeContext";
import {
  Zap,
  MapPin,
  Cpu,
  Shield,
  ShieldCheck,
  Command,
  Sliders,
  Sun,
  Moon,
  LogOut,
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

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  brainOnline,
  onOpenCommandPalette,
  density = "comfortable",
  onToggleDensity,
  onLogout,
}) => {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-40 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 transition-colors shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Finalized Loot Raiders Brand Crest Logo */}
        <div
          onClick={() => setActiveTab("public")}
          className="cursor-pointer group shrink-0"
        >
          <BrandLogo variant="full" size="md" />
        </div>

        {/* Navigation Tabs (RAFFLE COMPLETELY REMOVED) */}
        <nav className="hidden md:flex items-center gap-1 bg-slate-100 dark:bg-slate-950 p-1 rounded-xl border border-slate-200 dark:border-slate-800/80">
          <button
            onClick={() => setActiveTab("public")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "public"
                ? "bg-orange-500 text-white shadow-md shadow-orange-500/20 font-bold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-800/60"
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            Live Deals
          </button>

          <button
            onClick={() => setActiveTab("lootmap")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "lootmap"
                ? "bg-orange-500 text-white shadow-md shadow-orange-500/20 font-bold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-800/60"
            }`}
          >
            <MapPin className="w-3.5 h-3.5" />
            Loot Map
          </button>

          <button
            onClick={() => setActiveTab("brain")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "brain"
                ? "bg-orange-500 text-white shadow-md shadow-orange-500/20 font-bold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-800/60"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            AI Brain
          </button>

          <button
            onClick={() => setActiveTab("admin")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "admin"
                ? "bg-orange-500 text-white shadow-md shadow-orange-500/20 font-bold"
                : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-slate-800/60"
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            Telemetry
          </button>
        </nav>

        {/* Command Palette Trigger, Theme Toggle & Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Cmd+K Command Palette Trigger */}
          <button
            onClick={onOpenCommandPalette}
            className="flex items-center gap-2 bg-slate-100 dark:bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all font-mono"
          >
            <Command className="w-3.5 h-3.5 text-orange-500" />
            <span className="hidden sm:inline">Commands</span>
            <kbd className="bg-slate-200 dark:bg-slate-800 text-[10px] text-slate-600 dark:text-slate-400 px-1.5 py-0.5 rounded border border-slate-300 dark:border-slate-700">
              Cmd K
            </kbd>
          </button>

          {/* Density Selector */}
          {onToggleDensity && (
            <button
              onClick={onToggleDensity}
              title={`Current density: ${density}. Click to cycle.`}
              className="p-1.5 bg-slate-100 dark:bg-slate-950 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 rounded-xl transition-all font-mono text-[11px] capitalize flex items-center gap-1.5"
            >
              <Sliders className="w-3.5 h-3.5" />
              <span className="hidden md:inline">{density}</span>
            </button>
          )}

          {/* Light / Dark Mode Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-950 hover:bg-slate-200 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-all"
            title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Mode`}
          >
            {theme === "dark" ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-700" />}
          </button>

          {/* AI Status Indicator */}
          <div className="hidden lg:flex items-center gap-2 bg-slate-100 dark:bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800">
            <span
              className={`w-2 h-2 rounded-full ${
                brainOnline ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
              }`}
            />
            <span className="text-[11px] font-mono font-medium text-slate-600 dark:text-slate-300">
              {brainOnline ? "AI Active" : "Online"}
            </span>
          </div>

          <button
            onClick={() => setActiveTab("tma")}
            className="flex items-center gap-1.5 bg-orange-500/10 text-orange-600 dark:text-orange-400 hover:bg-orange-500/20 px-2.5 py-1.5 rounded-xl border border-orange-500/20 text-xs font-bold transition-all"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">TMA</span>
          </button>

          {/* Logout Button */}
          {onLogout && (
            <button
              onClick={onLogout}
              className="p-2 rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400 hover:bg-rose-500/20 border border-rose-500/20 transition-all"
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
