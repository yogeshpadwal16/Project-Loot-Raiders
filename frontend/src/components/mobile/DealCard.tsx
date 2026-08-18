import React, { useState } from "react";
import { DealItem } from "../../types/api";
import { resolveProductImage, getProductFallbackImage } from "../../utils/productImages";
import { DealBadge } from "./DealBadge";
import { DealTrustBadges } from "./DealTrustBadges";
import { ExternalLink } from "lucide-react";

interface DealCardProps {
  deal: DealItem;
}

export const DealCard: React.FC<DealCardProps> = ({ deal }) => {
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
    <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800/90 rounded-2xl p-3.5 flex flex-col justify-between shadow-sm hover:shadow-md transition-all">
      {/* Product Image Area */}
      <div className="relative w-full h-36 bg-slate-50 dark:bg-slate-950 rounded-xl p-2 flex items-center justify-center border border-slate-100 dark:border-slate-800/60 mb-2.5 overflow-hidden">
        <img
          src={imgSrc}
          alt={deal.title}
          onError={handleImageError}
          loading="lazy"
          className="max-h-full max-w-full object-contain transition-transform duration-300 hover:scale-105"
        />
        {/* Discount Badge */}
        {discountVal > 0 && (
          <div className="absolute top-2 left-2">
            <DealBadge discount={discountVal} />
          </div>
        )}
        {/* Merchant Badge */}
        <div className="absolute top-2 right-2">
          <DealBadge variant="merchant" label={deal.platform} />
        </div>
      </div>

      {/* Product Info */}
      <div className="flex-1 flex flex-col justify-between space-y-2">
        <div>
          <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 line-clamp-2 leading-snug">
            {deal.title}
          </h3>

          {/* Pricing Hierarchy */}
          <div className="flex items-baseline gap-1.5 mt-1.5 flex-wrap">
            <span className="text-base font-black text-emerald-600 dark:text-emerald-400">
              ₹{deal.price?.toLocaleString("en-IN")}
            </span>
            {deal.mrp && deal.mrp > deal.price && (
              <span className="text-[11px] text-slate-400 dark:text-slate-500 line-through">
                ₹{deal.mrp.toLocaleString("en-IN")}
              </span>
            )}
            {savings > 0 && (
              <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                Save ₹{savings.toLocaleString("en-IN")}
              </span>
            )}
          </div>
        </div>

        {/* Trust Badges */}
        <DealTrustBadges
          isVerifiedLow={deal.is_verified_low}
          score={deal.deal_score}
          discount={discountVal}
        />

        {/* View Deal Action Button */}
        <a
          href={dealUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 w-full flex items-center justify-center gap-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-black uppercase tracking-wider py-2 rounded-xl shadow-sm shadow-orange-500/20 transition-transform active:scale-[0.98]"
        >
          VIEW DEAL
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
};
