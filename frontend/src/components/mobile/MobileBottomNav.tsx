import React from "react";
import { Zap, MapPin, Cpu, Shield } from "lucide-react";

interface MobileBottomNavProps {
  activeTab: "public" | "lootmap" | "admin" | "brain" | "tma";
  setActiveTab: (tab: "public" | "lootmap" | "admin" | "brain" | "tma") => void;
}

export const MobileBottomNav: React.FC<MobileBottomNavProps> = ({
  activeTab,
  setActiveTab,
}) => {
  const tabs = [
    { id: "public" as const, label: "Deals", icon: Zap },
    { id: "lootmap" as const, label: "Loot Map", icon: MapPin },
    { id: "brain" as const, label: "AI Brain", icon: Cpu },
    { id: "admin" as const, label: "Telemetry", icon: Shield },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-white/95 dark:bg-slate-950/95 backdrop-blur-xl border-t border-slate-200/80 dark:border-slate-800/80 px-4 py-2 flex items-center justify-around shadow-2xl transition-colors pb-[max(0.5rem,env(safe-area-inset-bottom))]">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex flex-col items-center justify-center gap-1 py-1 px-3 rounded-2xl transition-all ${
              isActive
                ? "text-orange-500 font-extrabold"
                : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            <div className={`p-1 rounded-xl transition-all ${isActive ? "bg-orange-500/10" : ""}`}>
              <Icon className={`w-5 h-5 ${isActive ? "stroke-[2.5]" : "stroke-[1.75]"}`} />
            </div>
            <span className="text-[10px] leading-none tracking-tight">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
};
