import React from "react";
import { Zap, Flame, ArrowDownRight, Award, ShieldCheck, DollarSign, Send, Server } from "lucide-react";

interface LootRadarProps {
  stats: {
    totalDeals: number;
    hotDealsCount: number;
    historicalLowsCount: number;
    priceCrashesCount: number;
    avgLootScore: number;
    verifiedSavingsTotal: number;
    telegramStatus: string;
    scraperFleetStatus: string;
  };
}

export const LootRadar: React.FC<LootRadarProps> = ({ stats }) => {
  return (
    <div className="mb-8">
      {/* Section Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight font-sans">
              LOOT RADAR
            </h2>
            <span className="px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-600 dark:text-orange-400 text-[10px] font-mono font-bold border border-orange-500/20">
              Real-Time Intelligence
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Your strongest opportunities & operational metrics right now
          </p>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        {/* Hot Deals */}
        <div className="p-3.5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-rose-500 mb-2">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Hot Loot</span>
            <Flame className="w-4 h-4 fill-rose-500/20" />
          </div>
          <div className="text-2xl font-black font-mono text-slate-900 dark:text-white">
            {stats.hotDealsCount}
          </div>
          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium mt-1">Active High-Priority</span>
        </div>

        {/* Historical Lows */}
        <div className="p-3.5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-emerald-500 mb-2">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">All-Time Lows</span>
            <Award className="w-4 h-4" />
          </div>
          <div className="text-2xl font-black font-mono text-slate-900 dark:text-white">
            {stats.historicalLowsCount}
          </div>
          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium mt-1">Record Lowest Price</span>
        </div>

        {/* Price Crashes */}
        <div className="p-3.5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-amber-500 mb-2">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Price Crashes</span>
            <ArrowDownRight className="w-4 h-4" />
          </div>
          <div className="text-2xl font-black font-mono text-slate-900 dark:text-white">
            {stats.priceCrashesCount}
          </div>
          <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium mt-1">&gt; 50% Price Drop</span>
        </div>

        {/* Average Loot Score */}
        <div className="p-3.5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-orange-500 mb-2">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Avg Loot Score</span>
            <Zap className="w-4 h-4" />
          </div>
          <div className="text-2xl font-black font-mono text-orange-600 dark:text-orange-400">
            {stats.avgLootScore}
          </div>
          <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium mt-1">Out of 100</span>
        </div>

        {/* Qualified Deals */}
        <div className="p-3.5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-blue-500 mb-2">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Qualified</span>
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div className="text-2xl font-black font-mono text-slate-900 dark:text-white">
            {stats.totalDeals}
          </div>
          <span className="text-[10px] text-blue-600 dark:text-blue-400 font-medium mt-1">Passed AI Verification</span>
        </div>

        {/* Verified Savings */}
        <div className="p-3.5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-emerald-500 mb-2">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Est. Savings</span>
            <DollarSign className="w-4 h-4" />
          </div>
          <div className="text-xl font-black font-mono text-slate-900 dark:text-white truncate">
            ₹{stats.verifiedSavingsTotal.toLocaleString()}
          </div>
          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium mt-1">Total Discount Sum</span>
        </div>

        {/* Telegram Status */}
        <div className="p-3.5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-sky-500 mb-2">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Telegram</span>
            <Send className="w-4 h-4" />
          </div>
          <div className="text-sm font-bold font-mono text-emerald-600 dark:text-emerald-400 truncate">
            {stats.telegramStatus}
          </div>
          <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium mt-1">@LootRaidersDeals</span>
        </div>

        {/* Scraper Fleet Status */}
        <div className="p-3.5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-purple-500 mb-2">
            <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Scrapers</span>
            <Server className="w-4 h-4" />
          </div>
          <div className="text-sm font-bold font-mono text-emerald-600 dark:text-emerald-400 truncate">
            {stats.scraperFleetStatus}
          </div>
          <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium mt-1">All Systems Healthy</span>
        </div>
      </div>
    </div>
  );
};
