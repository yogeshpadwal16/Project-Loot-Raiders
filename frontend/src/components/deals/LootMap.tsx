import React, { useEffect, useState } from 'react';
import { MapPin, Activity, Flame, Radio } from 'lucide-react';
import { MapEvent } from '../../types/api';
import { ApiClient } from '../../services/api';

export const LootMap: React.FC = () => {
  const [events, setEvents] = useState<MapEvent[]>([]);

  useEffect(() => {
    const fetchEvents = () => {
      ApiClient.fetchLootMapEvents()
        .then((data) => setEvents(data))
        .catch((err) => console.warn('Loot Map fetch error:', err));
    };

    fetchEvents();
    const interval = setInterval(fetchEvents, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-2xl space-y-6">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center border border-orange-500/30">
            <MapPin className="w-5 h-5 text-orange-400" />
          </div>
          <div>
            <h2 className="text-lg font-black text-white flex items-center gap-2">
              INDIA LIVE LOOT MAP
              <span className="flex items-center gap-1 text-[11px] font-extrabold text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                <Radio className="w-3 h-3 animate-pulse" />
                LIVE STREAM
              </span>
            </h2>
            <p className="text-xs text-slate-400">Real-time telemetry of user loot claims & price drop triggers across major cities</p>
          </div>
        </div>
      </div>

      {/* Grid of City Telemetry */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {events.map((evt, idx) => (
          <div
            key={idx}
            className="bg-slate-950/80 p-4 rounded-2xl border border-slate-800/80 hover:border-orange-500/40 transition-all flex items-start gap-3 group"
          >
            <div className="w-8 h-8 rounded-xl bg-orange-500/20 flex items-center justify-center shrink-0 text-orange-400 group-hover:scale-110 transition-transform">
              <Flame className="w-4 h-4 fill-orange-400" />
            </div>
            <div>
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-bold text-white">{evt.name || (evt as any).city}</h4>
                <span className="text-[10px] text-slate-500 font-mono">
                  {evt.lat?.toFixed(2)}, {evt.lng?.toFixed(2)}
                </span>
              </div>
              <p className="text-xs text-orange-400 font-medium mt-0.5">
                {(evt as any).action || 'claimed loot deal'}
              </p>
              <p className="text-[10px] text-slate-500 mt-1">
                {(evt as any).time_ago || 'just now'}
              </p>
            </div>
          </div>
        ))}
      </div>

    </div>
  );
};
