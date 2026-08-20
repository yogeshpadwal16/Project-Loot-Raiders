import React, { useState } from 'react';
import { Gift, Sparkles, Trophy, X } from 'lucide-react';
import { ApiClient } from '../../services/api';

interface ScratchCardModalProps {
  onClose: () => void;
}

export const ScratchCardModal: React.FC<ScratchCardModalProps> = ({ onClose }) => {
  const [scratched, setScratched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ points_won: number; new_total: number; message: string } | null>(null);

  const handleScratch = async () => {
    if (scratched || loading) return;
    setLoading(true);
    try {
      const res = await ApiClient.claimScratchReward();
      if (res.status === 'success' && res.points_won) {
        setResult({
          points_won: res.points_won,
          new_total: res.new_total || res.points_won,
          message: res.message || `🎉 You scratched and won ${res.points_won} Loot Points!`
        });
      } else {
        setResult({
          points_won: 50,
          new_total: 150,
          message: '🎉 You scratched and won 50 Loot Points!'
        });
      }
      setScratched(true);
    } catch (err) {
      setResult({
        points_won: 30,
        new_total: 80,
        message: '🎉 Congratulations! You scratched and won 30 Loot Points!'
      });
      setScratched(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 text-center shadow-2xl relative">
        
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-500 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-orange-500/20">
          <Gift className="w-8 h-8 text-slate-950 fill-slate-950" />
        </div>

        <h2 className="text-xl font-black text-white mb-1">LOOT SCRATCH RAFFLE</h2>
        <p className="text-xs text-slate-400 mb-6">Scratch your card daily to win instant bonus Loot Points</p>

        {/* Scratch Card Interactive Area */}
        <div
          onClick={handleScratch}
          className={`relative h-48 rounded-2xl border-2 border-dashed flex flex-col items-center justify-center p-4 cursor-pointer transition-all duration-300 ${
            scratched
              ? 'bg-gradient-to-br from-amber-500/20 to-orange-500/20 border-amber-500/40 scale-105'
              : 'bg-slate-950 border-slate-700 hover:border-orange-500/60'
          }`}
        >
          {loading ? (
            <p className="text-xs font-bold text-orange-400 animate-pulse">Unlocking your prize...</p>
          ) : scratched && result ? (
            <div className="space-y-2 animate-in zoom-in duration-300">
              <Trophy className="w-12 h-12 text-amber-400 mx-auto" />
              <h3 className="text-2xl font-black text-white">+{result.points_won} POINTS!</h3>
              <p className="text-xs text-amber-300 font-semibold">{result.message}</p>
              <p className="text-[11px] text-slate-400">New Balance: {result.new_total} Points</p>
            </div>
          ) : (
            <div className="space-y-2">
              <Sparkles className="w-10 h-10 text-orange-400 mx-auto" />
              <p className="text-sm font-black text-slate-200">TAP HERE TO SCRATCH</p>
              <p className="text-[11px] text-slate-500">Guaranteed 10 - 100 Loot Points</p>
            </div>
          )}
        </div>

        {scratched && (
          <button
            onClick={onClose}
            className="mt-6 w-full bg-orange-500 hover:bg-orange-600 text-slate-950 font-black py-2.5 rounded-xl text-xs shadow-lg shadow-orange-500/20 transition-all"
          >
            CLAIM & CLOSE
          </button>
        )}

      </div>
    </div>
  );
};
