import React from 'react';
import { Flame, Shield, MapPin, Gift, Cpu, ShieldCheck, Zap, Command, Sliders } from 'lucide-react';

interface HeaderProps {
  activeTab: 'public' | 'lootmap' | 'scratch' | 'admin' | 'brain' | 'tma';
  setActiveTab: (tab: 'public' | 'lootmap' | 'scratch' | 'admin' | 'brain' | 'tma') => void;
  brainOnline: boolean;
  onOpenCommandPalette?: () => void;
  density?: 'compact' | 'comfortable' | 'expanded';
  onToggleDensity?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  brainOnline,
  onOpenCommandPalette,
  density = 'comfortable',
  onToggleDensity
}) => {
  return (
    <header className="sticky top-0 z-40 bg-surface/90 backdrop-blur-md border-b border-border/80 text-slate-100 glass-panel">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        
        {/* Brand Logo & Title */}
        <div 
          onClick={() => setActiveTab('public')}
          className="flex items-center gap-3 cursor-pointer group shrink-0"
        >
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-amber-600 via-amber-500 to-amber-400 flex items-center justify-center shadow-lg shadow-amber-500/20 group-hover:scale-105 transition-all">
            <Flame className="w-5 h-5 text-slate-950 fill-slate-950" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base tracking-tight text-white font-sans">LOOT RAIDERS</span>
              <span className="bg-amber-500/10 text-amber-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-amber-500/20">v2.5</span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium hidden lg:block">AI Deal Intelligence & Telegram Operating System</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-1 bg-canvas/80 p-1 rounded-xl border border-border/60">
          <button
            onClick={() => setActiveTab('public')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'public'
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 font-bold'
                : 'text-slate-400 hover:text-white hover:bg-surface-hover'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            Live Deals
          </button>

          <button
            onClick={() => setActiveTab('lootmap')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'lootmap'
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 font-bold'
                : 'text-slate-400 hover:text-white hover:bg-surface-hover'
            }`}
          >
            <MapPin className="w-3.5 h-3.5" />
            Loot Map
          </button>

          <button
            onClick={() => setActiveTab('scratch')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'scratch'
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 font-bold'
                : 'text-slate-400 hover:text-white hover:bg-surface-hover'
            }`}
          >
            <Gift className="w-3.5 h-3.5" />
            Raffle
          </button>

          <button
            onClick={() => setActiveTab('brain')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'brain'
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 font-bold'
                : 'text-slate-400 hover:text-white hover:bg-surface-hover'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            AI Brain
          </button>

          <button
            onClick={() => setActiveTab('admin')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'admin'
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 font-bold'
                : 'text-slate-400 hover:text-white hover:bg-surface-hover'
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            Telemetry
          </button>
        </nav>

        {/* Command Palette Trigger & Controls */}
        <div className="flex items-center gap-2 shrink-0">
          
          {/* Cmd+K Command Palette Trigger Button */}
          <button
            onClick={onOpenCommandPalette}
            className="flex items-center gap-2 bg-canvas px-3 py-1.5 rounded-xl border border-border/80 text-xs text-slate-400 hover:text-white hover:border-slate-700 transition-all font-mono"
          >
            <Command className="w-3.5 h-3.5 text-amber-500" />
            <span className="hidden sm:inline">Commands</span>
            <kbd className="bg-slate-800 text-[10px] text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">Cmd K</kbd>
          </button>

          {/* Density Selector */}
          {onToggleDensity && (
            <button
              onClick={onToggleDensity}
              title={`Current density: ${density}. Click to cycle density.`}
              className="p-1.5 bg-canvas hover:bg-surface-hover text-slate-400 hover:text-white border border-border/80 rounded-xl transition-all font-mono text-[11px] capitalize flex items-center gap-1.5"
            >
              <Sliders className="w-3.5 h-3.5 text-slate-400" />
              <span className="hidden md:inline">{density}</span>
            </button>
          )}

          {/* AI Status Indicator Pill */}
          <div className="hidden sm:flex items-center gap-2 bg-canvas px-3 py-1.5 rounded-xl border border-border/80">
            <span className={`w-2 h-2 rounded-full ${brainOnline ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            <span className="text-[11px] font-mono font-medium text-slate-300">
              {brainOnline ? 'AI Online' : 'Active'}
            </span>
          </div>

          <button
            onClick={() => setActiveTab('tma')}
            className="flex items-center gap-1.5 bg-blue-600/10 text-blue-400 hover:bg-blue-600/20 px-2.5 py-1.5 rounded-xl border border-blue-500/20 text-xs font-bold transition-all"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">TMA Mode</span>
          </button>
        </div>

      </div>
    </header>
  );
};
