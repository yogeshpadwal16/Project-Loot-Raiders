import React, { useEffect, useState } from 'react';
import { Flame, ExternalLink, Bookmark, Sparkles, RefreshCw, Zap } from 'lucide-react';
import { DealItem } from '../../types/api';
import { ApiClient } from '../../services/api';

export const TelegramMiniApp: React.FC = () => {
  const [deals, setDeals] = useState<DealItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadDeals = () => {
    setLoading(true);
    ApiClient.fetchPublicDeals(20)
      .then(setDeals)
      .catch((err) => console.warn('TMA deal fetch error:', err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDeals();
  }, []);

  return (
    <div className="max-w-md mx-auto min-h-screen bg-slate-950 text-slate-100 p-4 pb-20 space-y-4 font-sans">
      
      {/* TMA Header */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex items-center justify-between shadow-xl">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-orange-500 flex items-center justify-center text-slate-950 font-black">
            <Flame className="w-5 h-5 fill-slate-950" />
          </div>
          <div>
            <h1 className="text-base font-black tracking-tight text-white">LOOT RAIDERS TMA</h1>
            <p className="text-[10px] text-slate-400 font-semibold">Telegram Native Deal Feed</p>
          </div>
        </div>

        <button
          onClick={loadDeals}
          className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl transition-all"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* TMA Compact Deal Feed */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-12 text-center text-xs font-semibold text-slate-400">
            Fetching latest verified deals...
          </div>
        ) : deals.length === 0 ? (
          <div className="py-12 text-center text-xs font-semibold text-slate-400">
            No active deals currently queued.
          </div>
        ) : (
          deals.map((deal) => (
            <div
              key={deal.id}
              className="bg-slate-900 border border-slate-800/80 rounded-2xl p-3 flex gap-3 items-center justify-between shadow-lg"
            >
              <div className="w-16 h-16 rounded-xl bg-slate-950 p-1.5 flex items-center justify-center shrink-0 border border-slate-800">
                <img
                  src={deal.image_url || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=300'}
                  alt={deal.title}
                  className="max-h-full max-w-full object-contain rounded"
                />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-[10px] font-black uppercase text-orange-400 bg-orange-500/10 px-2 py-0.2 rounded border border-orange-500/20">
                    {deal.platform}
                  </span>
                  {deal.discount > 0 && (
                    <span className="text-[10px] font-bold text-emerald-400">
                      {deal.discount.toFixed(0)}% OFF
                    </span>
                  )}
                </div>

                <h3 className="text-xs font-bold text-slate-100 line-clamp-1 mb-1">{deal.title}</h3>

                <div className="flex items-baseline gap-2">
                  <span className="text-sm font-black text-emerald-400">₹{deal.price.toLocaleString('en-IN')}</span>
                  {deal.mrp > deal.price && (
                    <span className="text-[10px] text-slate-500 line-through">₹{deal.mrp.toLocaleString('en-IN')}</span>
                  )}
                </div>
              </div>

              <a
                href={deal.affiliate_url || deal.url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2.5 bg-orange-500 hover:bg-orange-600 text-slate-950 rounded-xl shrink-0 shadow-md shadow-orange-500/20"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          ))
        )}
      </div>

    </div>
  );
};
