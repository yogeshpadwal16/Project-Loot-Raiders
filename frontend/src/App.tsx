import React, { useEffect, useState } from 'react';
import { Header } from './components/common/Header';
import { CommandPalette } from './components/common/CommandPalette';
import { LootDealCard } from './components/deals/LootDealCard';
import { PriceHistoryModal } from './components/deals/PriceHistoryModal';
import { LootMap } from './components/deals/LootMap';
import { ScratchCardModal } from './components/deals/ScratchCardModal';
import { HealthMonitor } from './components/admin/HealthMonitor';
import { LootDataTable } from './components/admin/LootDataTable';
import { BrainConsole } from './components/brain/BrainConsole';
import { TelegramMiniApp } from './components/tma/TelegramMiniApp';
import { DealItem } from './types/api';
import { ApiClient } from './services/api';
import { Zap, Search, SlidersHorizontal, RefreshCw, Layers } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<'public' | 'lootmap' | 'scratch' | 'admin' | 'brain' | 'tma'>('public');
  const [deals, setDeals] = useState<DealItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedChartDeal, setSelectedChartDeal] = useState<DealItem | null>(null);
  const [showScratchModal, setShowScratchModal] = useState(false);
  const [brainOnline, setBrainOnline] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [density, setDensity] = useState<'compact' | 'comfortable' | 'expanded'>('comfortable');

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedMerchant, setSelectedMerchant] = useState<string>('all');

  const cycleDensity = () => {
    if (density === 'comfortable') setDensity('compact');
    else if (density === 'compact') setDensity('expanded');
    else setDensity('comfortable');
  };

  const loadDeals = () => {
    setLoading(true);
    ApiClient.fetchPublicDeals(100)
      .then((data) => setDeals(data))
      .catch((err) => console.warn('Deal fetch error:', err))
      .finally(() => setLoading(false));

    ApiClient.fetchBrainStatus()
      .then((res) => setBrainOnline(res.status === 'ONLINE'))
      .catch(() => setBrainOnline(false));
  };

  useEffect(() => {
    loadDeals();

    // SSE Realtime Deal Stream
    const sse = new EventSource('/api/deals/stream');
    sse.onmessage = (evt) => {
      try {
        const newDeal = JSON.parse(evt.data);
        if (newDeal && newDeal.title) {
          setDeals((prev) => [newDeal, ...prev]);
        }
      } catch (err) {}
    };

    return () => sse.close();
  }, []);

  const filteredDeals = deals.filter((d) => {
    const matchesSearch = d.title.toLowerCase().includes(searchQuery.toLowerCase()) || d.platform.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesMerchant = selectedMerchant === 'all' || d.platform.toLowerCase().includes(selectedMerchant.toLowerCase());
    return matchesSearch && matchesMerchant;
  });

  if (activeTab === 'tma') {
    return <TelegramMiniApp />;
  }

  const gridColsClass = density === 'compact'
    ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3'
    : density === 'expanded'
    ? 'grid-cols-1 md:grid-cols-2 gap-6'
    : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5';

  return (
    <div className="min-h-screen bg-canvas text-slate-100 font-sans selection:bg-amber-500 selection:text-slate-950">
      
      {/* Header Navigation */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        brainOnline={brainOnline}
        onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        density={density}
        onToggleDensity={cycleDensity}
      />

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        
        {/* PUBLIC DEALS DISCOVERY PLATFORM */}
        {activeTab === 'public' && (
          <div className="space-y-6">
            
            {/* Search & Filter Bar */}
            <div className="bg-surface/90 border border-border/80 rounded-2xl p-3.5 shadow-lg glass-panel flex flex-col md:flex-row items-center justify-between gap-3">
              <div className="relative w-full md:w-96">
                <Search className="w-4 h-4 text-amber-500 absolute left-3.5 top-3" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search deals by title, merchant, or ASIN..."
                  className="w-full bg-canvas border border-border/80 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 transition-all"
                />
              </div>

              {/* Merchant Accent Filter Pills & Density Selector */}
              <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
                {['all', 'amazon', 'flipkart', 'myntra', 'ajio'].map((merch) => (
                  <button
                    key={merch}
                    onClick={() => setSelectedMerchant(merch)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold capitalize transition-all border shrink-0 ${
                      selectedMerchant === merch
                        ? 'bg-amber-500 text-slate-950 border-amber-500 shadow-md shadow-amber-500/20'
                        : 'bg-canvas text-slate-400 border-border/80 hover:text-white hover:bg-surface-hover'
                    }`}
                  >
                    {merch}
                  </button>
                ))}

                {/* Density Cycle button */}
                <button
                  onClick={cycleDensity}
                  title="Toggle layout density (compact / comfortable / expanded)"
                  className="px-3 py-1.5 bg-canvas hover:bg-surface-hover text-slate-400 hover:text-white border border-border/80 rounded-xl transition-all text-xs font-mono font-medium shrink-0 flex items-center gap-1.5"
                >
                  <Layers className="w-3.5 h-3.5 text-amber-500" />
                  <span className="capitalize">{density}</span>
                </button>

                <button
                  onClick={loadDeals}
                  className="p-2 bg-canvas hover:bg-surface-hover text-slate-400 hover:text-white border border-border/80 rounded-xl transition-all shrink-0"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>

            {/* Live Deals Grid */}
            {loading ? (
              <div className="py-24 text-center space-y-3">
                <Zap className="w-10 h-10 text-amber-500 animate-bounce mx-auto" />
                <p className="text-sm font-bold text-slate-300 font-mono">Fetching Live AI Verified Deals...</p>
              </div>
            ) : filteredDeals.length === 0 ? (
              <div className="py-24 text-center bg-surface border border-border/80 rounded-2xl p-8 space-y-3 glass-panel">
                <SlidersHorizontal className="w-10 h-10 text-slate-500 mx-auto" />
                <h3 className="text-base font-bold text-white">No Deals Match Your Filter</h3>
                <p className="text-xs text-slate-400">Try clearing your search query or selecting a different merchant filter.</p>
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
        {activeTab === 'lootmap' && <LootMap />}

        {/* SCRATCH RAFFLE */}
        {activeTab === 'scratch' && (
          <div className="py-12 flex justify-center">
            <ScratchCardModal onClose={() => setActiveTab('public')} />
          </div>
        )}

        {/* ADMIN CONTROL CENTER */}
        {activeTab === 'admin' && (
          <div className="space-y-6">
            <HealthMonitor />
            <LootDataTable data={deals} onRefresh={loadDeals} />
          </div>
        )}

        {/* LOOT BRAIN AI CONSOLE */}
        {activeTab === 'brain' && <BrainConsole />}

      </main>

      {/* Global Command Palette */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onSelectTab={setActiveTab}
        onToggleDensity={setDensity}
      />

      {/* Modals */}
      {selectedChartDeal && (
        <PriceHistoryModal deal={selectedChartDeal} onClose={() => setSelectedChartDeal(null)} />
      )}
      {showScratchModal && (
        <ScratchCardModal onClose={() => setShowScratchModal(false)} />
      )}

    </div>
  );
}
