import React, { useState } from "react";
import { ExternalLink, LineChart, Bookmark, Sparkles, Tag, CreditCard, ShieldCheck } from "lucide-react";
import { DealItem } from "../../types/api";
import { resolveProductImage, getProductFallbackImage } from "../../utils/productImages";

interface LootDealCardProps {
  deal: DealItem;
  onOpenChart: (deal: DealItem) => void;
  density?: "compact" | "comfortable" | "expanded";
}

export const LootDealCard: React.FC<LootDealCardProps> = ({ deal, onOpenChart, density = "comfortable" }) => {
  const [bookmarked, setBookmarked] = useState(false);

  const [imgSrc, setImgSrc] = useState<string>(() =>
    resolveProductImage(deal.image_url, deal.title, deal.platform)
  );

  const getMerchantBadge = (platform: string) => {
    const plat = platform.toLowerCase();
    if (plat.includes("amazon")) return { name: "Amazon", bg: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30" };
    if (plat.includes("flipkart")) return { name: "Flipkart", bg: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30" };
    if (plat.includes("myntra")) return { name: "Myntra", bg: "bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/30" };
    if (plat.includes("ajio")) return { name: "Ajio", bg: "bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/30" };
    return { name: platform.toUpperCase(), bg: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30" };
  };

  const merchant = getMerchantBadge(deal.platform);
  const savings = deal.mrp > deal.price ? deal.mrp - deal.price : 0;

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
    if (score >= 60) return "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/30";
    return "text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700";
  };

  if (density === "compact") {
    return (
      <div className="group bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800/80 border border-slate-200 dark:border-slate-800 hover:border-orange-500/40 rounded-xl p-2.5 transition-all shadow-sm flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <img
            src={imgSrc}
            alt={deal.title}
            className="w-10 h-10 object-contain rounded-lg bg-slate-50 dark:bg-slate-950 p-1 shrink-0 border border-slate-200 dark:border-slate-800"
            onError={() => {
              const fallback = getProductFallbackImage(deal.title, deal.platform);
              if (imgSrc !== fallback) setImgSrc(fallback);
            }}
          />
          <div className="min-w-0">
            <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate group-hover:text-orange-500 transition-colors">
              {deal.title}
            </h4>
            <div className="flex items-center gap-2 text-[11px] font-mono">
              <span className="font-bold text-emerald-600 dark:text-emerald-400">₹{deal.price.toLocaleString("en-IN")}</span>
              {deal.mrp > deal.price && <span className="text-slate-400 line-through">₹{deal.mrp.toLocaleString("en-IN")}</span>}
              <span className="text-orange-600 dark:text-orange-400 font-sans text-[10px] font-bold">({deal.discount.toFixed(0)}% OFF)</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button onClick={() => onOpenChart(deal)} className="p-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white rounded-lg border border-slate-200 dark:border-slate-700">
            <LineChart className="w-3.5 h-3.5 text-orange-500" />
          </button>
          <a href={deal.affiliate_url || deal.url} target="_blank" rel="noopener noreferrer" className="p-1.5 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-bold">
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="group relative bg-white dark:bg-slate-900 hover:bg-slate-50/80 dark:hover:bg-slate-800/80 border border-slate-200 dark:border-slate-800 hover:border-orange-500/40 rounded-2xl p-4 transition-all duration-300 shadow-md flex flex-col justify-between overflow-hidden">
      {/* Background Accent Glow */}
      <div className="absolute -top-12 -right-12 w-28 h-28 bg-orange-500/10 rounded-full blur-2xl group-hover:bg-orange-500/20 transition-all pointer-events-none" />

      <div>
        {/* Top Badges */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${merchant.bg}`}>
              {merchant.name}
            </span>

            {deal.is_verified_low && (
              <span className="flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                <ShieldCheck className="w-3 h-3" />
                HISTORICAL LOW
              </span>
            )}

            {deal.deal_score > 0 && (
              <span className={`flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${getScoreColor(deal.deal_score)}`}>
                <Sparkles className="w-3 h-3" />
                SCORE {deal.deal_score.toFixed(0)}
              </span>
            )}
          </div>

          <button
            onClick={() => setBookmarked(!bookmarked)}
            className={`p-1.5 rounded-lg border transition-all ${
              bookmarked
                ? "bg-orange-500/20 text-orange-500 border-orange-500/40"
                : "text-slate-400 border-slate-200 dark:border-slate-800 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
            title="Bookmark deal"
          >
            <Bookmark className={`w-3.5 h-3.5 ${bookmarked ? "fill-orange-500" : ""}`} />
          </button>
        </div>

        {/* Product Image & Title Layout */}
        <div className="flex gap-3 mb-3">
          <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-xl bg-slate-50 dark:bg-slate-950 p-2 flex items-center justify-center border border-slate-200 dark:border-slate-800 shrink-0 group-hover:scale-105 transition-transform overflow-hidden">
            <img
              src={imgSrc}
              alt={deal.title}
              className="max-h-full max-w-full object-contain rounded-lg"
              onError={() => {
                const fallback = getProductFallbackImage(deal.title, deal.platform);
                if (imgSrc !== fallback) setImgSrc(fallback);
              }}
            />
          </div>

          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-extrabold text-slate-900 dark:text-slate-100 group-hover:text-orange-500 transition-colors line-clamp-2 leading-snug mb-1.5">
              {deal.title}
            </h3>

            {/* Price Row */}
            <div className="flex items-baseline gap-2 flex-wrap font-mono">
              <span className="text-xl sm:text-2xl font-extrabold text-emerald-600 dark:text-emerald-400">
                ₹{deal.price.toLocaleString("en-IN")}
              </span>
              {deal.mrp > deal.price && (
                <span className="text-xs font-medium text-slate-400 line-through">
                  ₹{deal.mrp.toLocaleString("en-IN")}
                </span>
              )}
              {deal.discount > 0 && (
                <span className="text-[11px] font-sans font-bold text-orange-600 dark:text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded-md border border-orange-500/20">
                  {deal.discount.toFixed(0)}% OFF
                </span>
              )}
            </div>

            {savings > 0 && (
              <p className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
                Save ₹{savings.toLocaleString("en-IN")}
              </p>
            )}
          </div>
        </div>

        {/* Coupon or Bank Offer Pills */}
        {(deal.coupon_code || deal.bank_offer) && (
          <div className="flex items-center gap-2 mb-3 flex-wrap text-xs">
            {deal.coupon_code && (
              <span className="flex items-center gap-1 text-[11px] font-mono font-bold text-orange-600 dark:text-orange-300 bg-orange-500/10 border border-orange-500/20 px-2.5 py-0.5 rounded-lg">
                <Tag className="w-3 h-3" />
                Coupon: {deal.coupon_code}
              </span>
            )}
            {deal.bank_offer && (
              <span className="flex items-center gap-1 text-[11px] font-mono font-bold text-blue-600 dark:text-blue-300 bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 rounded-lg">
                <CreditCard className="w-3 h-3" />
                {deal.bank_offer}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="flex items-center gap-2 pt-2.5 border-t border-slate-100 dark:border-slate-800">
        <button
          onClick={() => onOpenChart(deal)}
          className="flex-1 flex items-center justify-center gap-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white px-3 py-2 rounded-xl text-xs font-bold transition-all border border-slate-200 dark:border-slate-700"
        >
          <LineChart className="w-3.5 h-3.5 text-orange-500" />
          History
        </button>

        <a
          href={deal.affiliate_url || deal.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 flex items-center justify-center gap-1.5 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-extrabold px-3 py-2 rounded-xl text-xs shadow-md shadow-orange-500/20 transition-all"
        >
          GET LOOT
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
};
