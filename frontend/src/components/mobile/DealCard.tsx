import React, { useState } from "react";
import { DealItem } from "../../types/api";
import { resolveProductImage, getProductFallbackImage } from "../../utils/productImages";
import { sanitizeTitle } from "../../utils/titleSanitizer";
import { DealBadge } from "./DealBadge";
import { DealTrustBadges } from "./DealTrustBadges";
import { ExternalLink, Package } from "lucide-react";

interface DealCardProps {
  deal: DealItem;
}

export const DealCard: React.FC<DealCardProps> = ({ deal }) => {
  const [imgFailed, setImgFailed] = useState(false);
  const cleanTitle = sanitizeTitle(deal.title);

  const [imgSrc, setImgSrc] = useState<string>(() =>
    resolveProductImage(deal.image_url, deal.title, deal.platform, deal.id)
  );

  const discountVal = Math.round(
    deal.discount ||
      (deal.mrp && deal.price && deal.mrp > deal.price
        ? ((deal.mrp - deal.price) / deal.mrp) * 100
        : 0)
  );

  const savings = Math.max(0, (deal.mrp || 0) - (deal.price || 0));

  const handleImageError = () => {
    const fallback = getProductFallbackImage(deal.title, deal.platform, deal.id);
    if (imgSrc !== fallback) {
      setImgSrc(fallback);
    } else {
      setImgFailed(true);
    }
  };

  const dealUrl = deal.affiliate_url || deal.url;

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800/90 rounded-2xl p-3.5 flex flex-col justify-between shadow-sm hover:shadow-md transition-all">
      {/* Product Image Area */}
      <div className="relative w-full h-36 bg-slate-50 dark:bg-slate-950 rounded-xl p-2 flex items-center justify-center border border-slate-100 dark:border-slate-800/60 mb-2.5 overflow-hidden">
        {!imgFailed ? (
          <img
            src={imgSrc}
            alt={cleanTitle}
            onError={handleImageError}
            loading="lazy"
            className="max-h-full max-w-full object-contain transition-transform duration-300 hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
            <Package className="w-8 h-8 text-orange-500 mb-1" />
            <span className="text-[9px] font-mono font-bold text-slate-500 uppercase">
              {deal.platform}
            </span>
          </div>
        )}
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
            {cleanTitle}
          </h3>

          {/* Pricing Row */}
          <div className="flex items-baseline gap-1.5 mt-1.5">
            <span className="text-base font-extrabold text-emerald-600 dark:text-emerald-400 font-mono">
              ₹{deal.price ? deal.price.toLocaleString("en-IN") : "0"}
            </span>
            {deal.mrp && deal.mrp > deal.price && (
              <span className="text-xs font-medium text-slate-400 line-through font-mono">
                ₹{deal.mrp.toLocaleString("en-IN")}
              </span>
            )}
          </div>

          {/* Savings Badge */}
          {savings > 0 && (
            <p className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 font-mono mt-0.5">
              Save ₹{savings.toLocaleString("en-IN")}
            </p>
          )}
        </div>

        {/* Trust Badges */}
        <DealTrustBadges isVerifiedLow={deal.is_verified_low} score={Math.round(deal.deal_score)} />

        {/* View Deal Button */}
        <a
          href={dealUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full py-2 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-extrabold text-xs rounded-xl flex items-center justify-center gap-1.5 shadow-sm active:scale-95 transition-all mt-2"
        >
          <span>VIEW DEAL</span>
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
};
