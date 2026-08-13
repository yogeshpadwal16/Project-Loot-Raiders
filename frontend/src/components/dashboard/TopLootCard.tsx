import React, { useState } from "react";
import { Award, Zap, ExternalLink, ShieldCheck, TrendingDown } from "lucide-react";
import { getProductFallbackImage } from "../../utils/productImages";

interface TopLootDeal {
  id: string;
  title: string;
  platform: string;
  price: number;
  mrp: number;
  discount: number;
  image_url: string;
  url: string;
  is_verified_low: boolean;
  deal_score: number;
  auto_cart_url?: string;
}

interface TopLootCardProps {
  deal: TopLootDeal | null;
  onOpenHistory?: (dealId: string) => void;
}

export const TopLootCard: React.FC<TopLootCardProps> = ({ deal, onOpenHistory }) => {
  if (!deal) return null;

  const fallbackSrc = getProductFallbackImage(deal.title, deal.platform);
  const [imgSrc, setImgSrc] = useState<string>(deal.image_url || fallbackSrc);

  const savings = Math.max(0, deal.mrp - deal.price);

  return (
    <div className="mb-8 p-6 rounded-3xl bg-gradient-to-br from-orange-500/10 via-amber-500/5 to-white dark:to-slate-900 border-2 border-orange-500/40 shadow-xl relative overflow-hidden backdrop-blur-xl transition-all">
      {/* Background Glow Badge */}
      <div className="absolute top-0 right-0 px-6 py-2 bg-gradient-to-l from-orange-500 to-amber-500 text-white font-extrabold text-xs tracking-widest uppercase rounded-bl-2xl shadow-lg flex items-center gap-1.5 z-10">
        <Award className="w-4 h-4" />
        <span>#1 TOP LOOT OPPORTUNITY</span>
      </div>

      <div className="flex flex-col md:flex-row items-center gap-6 pt-4 md:pt-0">
        {/* Product Image Container */}
        <div className="relative w-40 h-40 sm:w-48 sm:h-48 shrink-0 rounded-2xl bg-white p-3 flex items-center justify-center border border-slate-200 dark:border-slate-800 shadow-md overflow-hidden">
          <img
            src={imgSrc}
            alt={deal.title}
            className="max-w-full max-h-full object-contain hover:scale-105 transition-transform"
            onError={() => {
              if (imgSrc !== fallbackSrc) {
                setImgSrc(fallbackSrc);
              }
            }}
          />
          {deal.is_verified_low && (
            <span className="absolute bottom-2 left-2 px-2 py-0.5 rounded-md bg-emerald-500 text-white text-[10px] font-bold shadow">
              HISTORICAL LOW
            </span>
          )}
        </div>

        {/* Product Details & Intelligence Breakdown */}
        <div className="flex-1 w-full text-left">
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs font-mono font-bold uppercase border border-slate-300 dark:border-slate-700">
              {deal.platform}
            </span>
            <div className="flex items-center gap-1 text-orange-600 dark:text-orange-500 font-mono font-extrabold text-xs">
              <Zap className="w-4 h-4" />
              <span>LOOT SCORE: {deal.deal_score}/100</span>
            </div>
          </div>

          <h3 className="text-lg sm:text-xl font-extrabold text-slate-900 dark:text-white line-clamp-2 leading-snug mb-3">
            {deal.title}
          </h3>

          {/* Pricing & Savings */}
          <div className="flex items-baseline gap-3 mb-4">
            <span className="text-3xl font-black font-mono text-orange-600 dark:text-orange-400">
              ₹{deal.price.toLocaleString("en-IN")}
            </span>
            {deal.mrp > deal.price && (
              <span className="text-sm font-mono text-slate-400 line-through">
                ₹{deal.mrp.toLocaleString("en-IN")}
              </span>
            )}
            <span className="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-mono font-extrabold text-xs border border-emerald-500/20 flex items-center gap-1">
              <TrendingDown className="w-3.5 h-3.5" />
              {deal.discount}% OFF (Save ₹{savings.toLocaleString("en-IN")})
            </span>
          </div>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center gap-3">
            <a
              href={deal.auto_cart_url || deal.url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-extrabold text-sm tracking-wide shadow-lg shadow-orange-500/25 active:scale-95 transition-all flex items-center gap-2"
            >
              <span>GET LOOT NOW</span>
              <ExternalLink className="w-4 h-4" />
            </a>

            {onOpenHistory && (
              <button
                onClick={() => onOpenHistory(deal.id)}
                className="px-4 py-3 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 font-semibold text-xs border border-slate-300 dark:border-slate-700 transition-all"
              >
                Inspect Price Chart
              </button>
            )}

            <div className="inline-flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono ml-auto">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
              <span>Verified Merchant</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
