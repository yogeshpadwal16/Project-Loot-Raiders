import React, { useState } from "react";
import { DealItem } from "../../types/api";
import { resolveProductImage, getProductFallbackImage } from "../../utils/productImages";
import { DealBadge } from "./DealBadge";
import { DealTrustBadges } from "./DealTrustBadges";
import { ExternalLink, Flame } from "lucide-react";

interface FeaturedDealProps {
  deal: DealItem;
}

export const FeaturedDeal: React.FC<FeaturedDealProps> = ({ deal }) => {
  const [imgSrc, setImgSrc] = useState<string>(() =>
    resolveProductImage(deal.image_url, deal.title, deal.platform)
  );

  const discountVal =
    deal.discount ||
    (deal.mrp && deal.price && deal.mrp > deal.price
      ? Math.round(((deal.mrp - deal.price) / deal.mrp) * 100)
      : 0);

  const savings = Math.max(0, (deal.mrp || 0) - (deal.price || 0));

  const handleImageError = () => {
    const fallback = getProductFallbackImage(deal.title, deal.platform);
    if (imgSrc !== fallback) {
      setImgSrc(fallback);
    }
  };

  const dealUrl = deal.affiliate_url || deal.url;

  return (
    <div className="relative overflow-hidden bg-gradient-to-b from-orange-500/10 via-white dark:via-slate-900 to-white dark:to-slate-900 border-2 border-orange-500/30 dark:border-orange-500/40 rounded-3xl p-4 shadow-xl transition-all">
      {/* Top Banner Tag */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-1.5 bg-orange-500 text-white text-[11px] font-black uppercase px-3 py-1 rounded-full shadow-md shadow-orange-500/30">
          <Flame className="w-3.5 h-3.5 fill-white animate-pulse" />
          FEATURED LOOT DEAL
        </div>
        <DealBadge variant="merchant" label={deal.platform} />
      </div>

      {/* Product Imagery */}
      <div className="relative w-full h-44 bg-white dark:bg-slate-950 rounded-2xl p-3 flex items-center justify-center border border-slate-200/80 dark:border-slate-800/80 mb-3.5 overflow-hidden">
        <img
          src={imgSrc}
          alt={deal.title}
          onError={handleImageError}
          loading="lazy"
          className="max-h-full max-w-full object-contain transition-transform duration-300 hover:scale-105"
        />
        {discountVal > 0 && (
          <div className="absolute top-2.5 right-2.5">
            <DealBadge discount={discountVal} />
          </div>
        )}
      </div>

      {/* Deal Details & Pricing */}
      <div className="space-y-2">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white line-clamp-2 leading-snug">
          {deal.title}
        </h2>

        {/* Pricing Matrix */}
        <div className="flex items-baseline gap-2 pt-0.5">
          <span className="text-xl font-black text-emerald-600 dark:text-emerald-400">
            ₹{deal.price?.toLocaleString("en-IN")}
          </span>
          {deal.mrp && deal.mrp > deal.price && (
            <span className="text-xs text-slate-400 dark:text-slate-500 line-through">
              ₹{deal.mrp.toLocaleString("en-IN")}
            </span>
          )}
          {savings > 0 && (
            <span className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md">
              Save ₹{savings.toLocaleString("en-IN")}
            </span>
          )}
        </div>

        {/* Trust Badges */}
        <DealTrustBadges
          isVerifiedLow={deal.is_verified_low}
          score={deal.deal_score}
          discount={discountVal}
        />

        {/* Call to Action Button */}
        <a
          href={dealUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 w-full flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 text-white text-xs font-black uppercase tracking-wider py-3 rounded-2xl shadow-lg shadow-orange-500/25 transition-transform active:scale-[0.98]"
        >
          VIEW DEAL
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
};
