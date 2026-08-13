import React from "react";
import { Cpu, Send, Server, ShieldCheck, Flame, ArrowDownRight, Award } from "lucide-react";

interface BentoSummaryProps {
  hotCount: number;
  lowsCount: number;
  crashesCount: number;
  aiOpportunitiesCount: number;
  scraperFleetCount: string;
}

export const BentoSummary: React.FC<BentoSummaryProps> = ({
  hotCount,
  lowsCount,
  crashesCount,
  aiOpportunitiesCount,
  scraperFleetCount,
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
      {/* Card 1: AI Brain High Priority Pick */}
      <div className="p-5 rounded-2xl bg-gradient-to-br from-orange-500/10 to-slate-900 border border-orange-500/30 shadow-lg flex flex-col justify-between">
        <div className="flex items-center justify-between text-orange-500 mb-3">
          <span className="text-xs font-mono font-bold uppercase tracking-wider">AI Brain Analysis</span>
          <Cpu className="w-5 h-5 animate-pulse" />
        </div>
        <div>
          <div className="text-3xl font-black font-mono text-white">
            {aiOpportunitiesCount}
          </div>
          <p className="text-xs text-slate-300 mt-1">
            Exceptional high-score deals evaluated and ready for publication
          </p>
        </div>
      </div>

      {/* Card 2: Hot Deals & Crashes Summary */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-lg flex flex-col justify-between">
        <div className="flex items-center justify-between text-rose-400 mb-3">
          <span className="text-xs font-mono font-bold uppercase tracking-wider">Loot Velocity</span>
          <Flame className="w-5 h-5" />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <div className="text-2xl font-black font-mono text-rose-400">{hotCount}</div>
            <span className="text-[10px] text-slate-400">Hot Deals</span>
          </div>
          <div>
            <div className="text-2xl font-black font-mono text-amber-400">{crashesCount}</div>
            <span className="text-[10px] text-slate-400">Crashes</span>
          </div>
        </div>
      </div>

      {/* Card 3: All-Time Record Lows */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-lg flex flex-col justify-between">
        <div className="flex items-center justify-between text-emerald-400 mb-3">
          <span className="text-xs font-mono font-bold uppercase tracking-wider">Record Lows</span>
          <Award className="w-5 h-5" />
        </div>
        <div>
          <div className="text-3xl font-black font-mono text-emerald-400">
            {lowsCount}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Verified lowest historical price in dataset
          </p>
        </div>
      </div>

      {/* Card 4: Operations & Telegram Pipeline */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-lg flex flex-col justify-between">
        <div className="flex items-center justify-between text-sky-400 mb-3">
          <span className="text-xs font-mono font-bold uppercase tracking-wider">Pipeline Health</span>
          <Server className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Scrapers:</span>
            <span className="font-mono font-bold text-emerald-400">{scraperFleetCount}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Telegram Channel:</span>
            <span className="font-mono font-bold text-sky-400">Connected</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">Affiliate Tag:</span>
            <span className="font-mono font-bold text-orange-400">lootraiders-21</span>
          </div>
        </div>
      </div>
    </div>
  );
};
