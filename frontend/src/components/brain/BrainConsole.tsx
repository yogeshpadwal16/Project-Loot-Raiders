import React, { useEffect, useState } from 'react';
import { Cpu, ShieldCheck, CheckCircle2, Search, Play, Brain, Layers, BookOpen } from 'lucide-react';
import { BrainStatus, MemoryEntry, PolicyCandidate } from '../../types/api';
import { ApiClient } from '../../services/api';

export const BrainConsole: React.FC = () => {
  const [brainStatus, setBrainStatus] = useState<BrainStatus | null>(null);
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [policies, setPolicies] = useState<PolicyCandidate[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Pipeline submission form state
  const [dealTitle, setDealTitle] = useState('');
  const [originalPrice, setOriginalPrice] = useState('1000');
  const [dealPrice, setDealPrice] = useState('500');
  const [merchant, setMerchant] = useState('Amazon');
  const [dealUrl, setDealUrl] = useState('https://amazon.in/dp/example');
  const [submitting, setSubmitting] = useState(false);
  const [pipelineResult, setPipelineResult] = useState<any>(null);

  const loadBrainData = () => {
    ApiClient.fetchBrainStatus().then(setBrainStatus).catch(() => {});
    ApiClient.fetchBrainMemories(searchQuery).then(setMemories).catch(() => {});
    ApiClient.fetchBrainPolicies().then(setPolicies).catch(() => {});
  };

  useEffect(() => {
    loadBrainData();
  }, [searchQuery]);

  const handleApprovePolicy = async (policyId: string) => {
    try {
      await ApiClient.approveBrainPolicy(policyId);
      loadBrainData();
    } catch (err) {
      alert(`Policy approval failed: ${err}`);
    }
  };

  const handleSubmitPipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setPipelineResult(null);
    try {
      const res = await ApiClient.processBrainPipeline({
        title: dealTitle,
        original_price: parseFloat(originalPrice),
        deal_price: parseFloat(dealPrice),
        merchant,
        url: dealUrl
      });
      setPipelineResult(res);
      loadBrainData();
    } catch (err) {
      setPipelineResult({ status: 'ERROR', error: String(err) });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-2xl flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-orange-500/10 flex items-center justify-center border border-orange-500/30 text-orange-400">
            <Brain className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-black text-white">LOOT BRAIN AI CONTROL CENTER</h2>
              <span className="text-xs font-black text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                {brainStatus?.status || 'ONLINE'}
              </span>
            </div>
            <p className="text-xs text-slate-400">Autonomous multi-agent deal intelligence & self-evolving learning engine</p>
          </div>
        </div>
      </div>

      {/* Agents Registry Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {brainStatus?.agents.map((agent) => (
          <div key={agent.agent_id} className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-black text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded-md border border-orange-500/20">
                {agent.agent_id}
              </span>
              <span className="text-[10px] font-mono text-emerald-400">{agent.state}</span>
            </div>
            <h4 className="text-sm font-bold text-white">{agent.name}</h4>
            <p className="text-xs text-slate-400 leading-snug">{agent.role}</p>
            <div className="flex flex-wrap gap-1 pt-1">
              {agent.capabilities.map((cap) => (
                <span key={cap} className="text-[10px] bg-slate-950 text-slate-400 px-2 py-0.5 rounded border border-slate-800">
                  {cap}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Pipeline Test Form & Proposed Policies */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Submit Raw Deal Form */}
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-2xl space-y-4">
          <h3 className="text-base font-black text-white flex items-center gap-2">
            <Play className="w-4 h-4 text-orange-400" />
            Submit Deal to 15-Step Pipeline
          </h3>

          <form onSubmit={handleSubmitPipeline} className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-400">Deal Title</label>
              <input
                type="text"
                required
                value={dealTitle}
                onChange={(e) => setDealTitle(e.target.value)}
                placeholder="e.g. Sony WH-1000XM5 Wireless Headphones"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-orange-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-slate-400">Original Price (₹)</label>
                <input
                  type="number"
                  required
                  value={originalPrice}
                  onChange={(e) => setOriginalPrice(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-orange-500"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-400">Deal Price (₹)</label>
                <input
                  type="number"
                  required
                  value={dealPrice}
                  onChange={(e) => setDealPrice(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-400">Merchant URL</label>
              <input
                type="text"
                required
                value={dealUrl}
                onChange={(e) => setDealUrl(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-orange-500"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-slate-950 font-black py-2.5 rounded-xl text-xs shadow-lg shadow-orange-500/20 transition-all disabled:opacity-50"
            >
              {submitting ? 'PROCESSING THROUGH AGENTS...' : 'PROCESS DEAL PIPELINE'}
            </button>
          </form>

          {pipelineResult && (
            <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800 text-xs space-y-1">
              <span className="font-bold text-orange-400">Pipeline Result:</span>
              <pre className="text-[11px] text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(pipelineResult, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Proposed Self-Improvement Policies */}
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-2xl space-y-4">
          <h3 className="text-base font-black text-white flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            AI Policy Candidate Signoff ({policies.length})
          </h3>

          {policies.length === 0 ? (
            <div className="bg-slate-950 p-6 rounded-2xl border border-slate-800 text-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <p className="text-xs font-bold text-white">No Unapproved Policies</p>
              <p className="text-[11px] text-slate-500 mt-1">Subconscious loop is active and scanning deal patterns in background.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {policies.map((p) => (
                <div key={p.policy_id} className="bg-slate-950 p-4 rounded-2xl border border-slate-800 flex items-start justify-between gap-3">
                  <div>
                    <span className="text-[10px] font-mono text-orange-400">{p.policy_id}</span>
                    <h4 className="text-xs font-bold text-white">{p.description}</h4>
                    <p className="text-[10px] text-slate-500">Target: {p.target_component}</p>
                  </div>
                  <button
                    onClick={() => handleApprovePolicy(p.policy_id)}
                    className="bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-xs transition-all shrink-0"
                  >
                    Approve
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>

      {/* Dual Memory Search */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-black text-white flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-purple-400" />
            Dual Memory Store Search ({memories.length})
          </h3>

          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search memory entries..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-96 overflow-y-auto pr-1">
          {memories.map((m) => (
            <div key={m.memory_id} className="bg-slate-950 p-3 rounded-2xl border border-slate-800/80 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-black text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                  {m.category}
                </span>
                <span className="text-[10px] text-slate-500 font-mono">{m.agent_id}</span>
              </div>
              <h4 className="text-xs font-bold text-slate-200">{m.title}</h4>
              <p className="text-[11px] text-slate-400 line-clamp-2">{m.content}</p>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
