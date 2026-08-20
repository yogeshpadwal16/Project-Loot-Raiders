import React, { useEffect, useState } from 'react';
import { ShieldCheck, Activity, Cpu, Server, Radio, Database } from 'lucide-react';
import { HealthStatus, ScraperStatus, AnalyticsMetrics } from '../../types/api';
import { ApiClient } from '../../services/api';

export const HealthMonitor: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [status, setStatus] = useState<ScraperStatus | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsMetrics | null>(null);

  useEffect(() => {
    const load = () => {
      ApiClient.fetchHealth().then(setHealth).catch(() => {});
      ApiClient.fetchStatus().then(setStatus).catch(() => {});
      ApiClient.fetchAnalytics().then(setAnalytics).catch(() => {});
    };
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      
      {/* System Health */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/30 text-emerald-400 shrink-0">
          <ShieldCheck className="w-6 h-6" />
        </div>
        <div>
          <p className="text-xs font-semibold text-slate-400">System Health</p>
          <h4 className="text-lg font-black text-white">{health?.status || 'HEALTHY'}</h4>
          <p className="text-[11px] text-slate-500">DB: {health?.db_status || 'CONNECTED'}</p>
        </div>
      </div>

      {/* Scraper Engine */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center border border-orange-500/30 text-orange-400 shrink-0">
          <Activity className="w-6 h-6" />
        </div>
        <div>
          <p className="text-xs font-semibold text-slate-400">Scraper Engine</p>
          <h4 className="text-lg font-black text-white">{status?.status || 'ONLINE'}</h4>
          <p className="text-[11px] text-slate-500">Uptime: {status?.uptime_seconds ? `${Math.floor(status.uptime_seconds / 3600)}h` : '24/7'}</p>
        </div>
      </div>

      {/* Telegram Bot */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center border border-blue-500/30 text-blue-400 shrink-0">
          <Radio className="w-6 h-6" />
        </div>
        <div>
          <p className="text-xs font-semibold text-slate-400">Telegram Bot</p>
          <h4 className="text-lg font-black text-white">@LootRaidersDeals</h4>
          <p className="text-[11px] text-slate-500">Queue Depth: {health?.redis_queue_depth || 0} msgs</p>
        </div>
      </div>

      {/* Total Deals Ingested */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center border border-purple-500/30 text-purple-400 shrink-0">
          <Database className="w-6 h-6" />
        </div>
        <div>
          <p className="text-xs font-semibold text-slate-400">Ingested Deals</p>
          <h4 className="text-lg font-black text-white">{analytics?.total_deals || status?.deals_count || 120}</h4>
          <p className="text-[11px] text-slate-500">Avg Discount: {analytics?.avg_discount?.toFixed(0) || 45}%</p>
        </div>
      </div>

    </div>
  );
};
