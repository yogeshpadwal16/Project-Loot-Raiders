import React from 'react';
import { Flame, Shield, MapPin, Gift, Cpu, ShieldCheck, Zap } from 'lucide-react';

interface HeaderProps {
  activeTab: 'public' | 'lootmap' | 'scratch' | 'admin' | 'brain' | 'tma';
  setActiveTab: (tab: 'public' | 'lootmap' | 'scratch' | 'admin' | 'brain' | 'tma') => void;
  brainOnline: boolean;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, setActiveTab, brainOnline }) => {
  return (
    <header className="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 text-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand Logo & Title */}
        <div 
          onClick={() => setActiveTab('public')}
          className="flex items-center gap-3 cursor-pointer group"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-orange-600 via-orange-500 to-amber-400 flex items-center justify-center shadow-lg shadow-orange-500/20 group-hover:scale-105 transition-transform">
            <Flame className="w-6 h-6 text-slate-950 fill-slate-950" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-black text-lg tracking-tight text-white">PROJECT LOOT RAIDERS</span>
              <span className="bg-orange-500/20 text-orange-400 text-xs font-extrabold px-2 py-0.5 rounded-full border border-orange-500/30">v2.0</span>
            </div>
            <p className="text-xs text-slate-400 font-medium hidden sm:block">Autonomous Deal Intelligence & Revenue Engine</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-1 bg-slate-950/60 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('public')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'public'
                ? 'bg-orange-500 text-slate-950 shadow-md shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Zap className="w-4 h-4" />
            Live Deals
          </button>

          <button
            onClick={() => setActiveTab('lootmap')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'lootmap'
                ? 'bg-orange-500 text-slate-950 shadow-md shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <MapPin className="w-4 h-4" />
            Loot Map
          </button>

          <button
            onClick={() => setActiveTab('scratch')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'scratch'
                ? 'bg-orange-500 text-slate-950 shadow-md shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Gift className="w-4 h-4" />
            Scratch Raffle
          </button>

          <button
            onClick={() => setActiveTab('brain')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'brain'
                ? 'bg-orange-500 text-slate-950 shadow-md shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Cpu className="w-4 h-4" />
            AI Brain
          </button>

          <button
            onClick={() => setActiveTab('admin')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'admin'
                ? 'bg-orange-500 text-slate-950 shadow-md shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Shield className="w-4 h-4" />
            Admin Panel
          </button>
        </nav>

        {/* Status Indicator & TMA Toggle */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800">
            <span className={`w-2.5 h-2.5 rounded-full ${brainOnline ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            <span className="text-xs font-bold text-slate-300">
              {brainOnline ? 'AI Brain Online' : 'Standard Pipeline'}
            </span>
          </div>

          <button
            onClick={() => setActiveTab('tma')}
            className="flex items-center gap-1.5 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 px-3 py-1.5 rounded-xl border border-blue-500/30 text-xs font-bold transition-all"
          >
            <ShieldCheck className="w-4 h-4" />
            TMA Mode
          </button>
        </div>

      </div>
    </header>
  );
};
