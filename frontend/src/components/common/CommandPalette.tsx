import React, { useState, useEffect } from 'react';
import { Search, Zap, Activity, BarChart3, Bot, Sliders, X } from 'lucide-react';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTab: (tab: 'public' | 'lootmap' | 'scratch' | 'admin' | 'brain' | 'tma') => void;
  onToggleDensity?: (density: 'compact' | 'comfortable' | 'expanded') => void;
}

export function CommandPalette({ isOpen, onClose, onSelectTab, onToggleDensity }: CommandPaletteProps) {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        isOpen ? onClose() : null;
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const commands = [
    { id: 'deals', label: 'Go to Live Deals Discovery', icon: Zap, action: () => { onSelectTab('public'); onClose(); } },
    { id: 'brain', label: 'Open Loot Brain AI Console', icon: Bot, action: () => { onSelectTab('brain'); onClose(); } },
    { id: 'admin', label: 'Open Scraper & Telemetry Monitor', icon: Activity, action: () => { onSelectTab('admin'); onClose(); } },
    { id: 'lootmap', label: 'Explore Interactive Deal LootMap', icon: BarChart3, action: () => { onSelectTab('lootmap'); onClose(); } },
    { id: 'compact', label: 'Set Density: Compact (Power User)', icon: Sliders, action: () => { onToggleDensity?.('compact'); onClose(); } },
    { id: 'comfortable', label: 'Set Density: Comfortable (Default)', icon: Sliders, action: () => { onToggleDensity?.('comfortable'); onClose(); } },
    { id: 'expanded', label: 'Set Density: Expanded (Inspection)', icon: Sliders, action: () => { onToggleDensity?.('expanded'); onClose(); } },
  ];

  const filteredCommands = commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-start justify-center pt-20 px-4">
      <div className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden glass-panel-elevated animate-in fade-in zoom-in-95 duration-150">
        
        {/* Input Bar */}
        <div className="relative flex items-center border-b border-slate-800 px-4 py-3">
          <Search className="w-5 h-5 text-amber-500 mr-3" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search platform (e.g. Scraper, Brain, Density)..."
            className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
            autoFocus
          />
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Command List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500">No matching commands found.</div>
          ) : (
            filteredCommands.map((cmd) => {
              const Icon = cmd.icon;
              return (
                <button
                  key={cmd.id}
                  onClick={cmd.action}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800/80 transition-all group"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-4 h-4 text-slate-400 group-hover:text-amber-400 transition-colors" />
                    <span>{cmd.label}</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-600 group-hover:text-slate-400">Jump</span>
                </button>
              );
            })
          )}
        </div>

        {/* Footer info */}
        <div className="px-4 py-2 bg-slate-950/60 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500 font-mono">
          <span>Navigate with mouse or click</span>
          <span className="bg-slate-800 px-1.5 py-0.5 rounded text-[10px] text-slate-400">ESC to close</span>
        </div>
      </div>
    </div>
  );
}
