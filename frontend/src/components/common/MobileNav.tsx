import React from "react";
import { Zap, MapPin, Cpu, Shield, ShieldCheck } from "lucide-react";

interface MobileNavProps {
  activeTab: "public" | "lootmap" | "admin" | "brain" | "tma";
  setActiveTab: (tab: "public" | "lootmap" | "admin" | "brain" | "tma") => void;
}

export const MobileNav: React.FC<MobileNavProps> = ({ activeTab, setActiveTab }) => {
  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur-lg border-t border-slate-200 dark:border-slate-800 px-2 py-1.5 flex items-center justify-around shadow-lg">
      <button
        onClick={() => setActiveTab("public")}
        className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all ${
          activeTab === "public"
            ? "text-orange-500 font-bold"
            : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
        }`}
      >
        <Zap className="w-5 h-5" />
        <span className="text-[10px]">Deals</span>
      </button>

      <button
        onClick={() => setActiveTab("lootmap")}
        className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all ${
          activeTab === "lootmap"
            ? "text-orange-500 font-bold"
            : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
        }`}
      >
        <MapPin className="w-5 h-5" />
        <span className="text-[10px]">LootMap</span>
      </button>

      <button
        onClick={() => setActiveTab("brain")}
        className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all ${
          activeTab === "brain"
            ? "text-orange-500 font-bold"
            : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
        }`}
      >
        <Cpu className="w-5 h-5" />
        <span className="text-[10px]">AI Brain</span>
      </button>

      <button
        onClick={() => setActiveTab("admin")}
        className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all ${
          activeTab === "admin"
            ? "text-orange-500 font-bold"
            : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
        }`}
      >
        <Shield className="w-5 h-5" />
        <span className="text-[10px]">Telemetry</span>
      </button>

      <button
        onClick={() => setActiveTab("tma")}
        className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all ${
          activeTab === "tma"
            ? "text-orange-500 font-bold"
            : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
        }`}
      >
        <ShieldCheck className="w-5 h-5" />
        <span className="text-[10px]">TMA</span>
      </button>
    </div>
  );
};
