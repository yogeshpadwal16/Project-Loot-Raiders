import React, { useState } from "react";
import { DealItem } from "../../types/api";
import { resolveProductImage, getProductFallbackImage } from "../../utils/productImages";
import { sanitizeTitle } from "../../utils/titleSanitizer";
import { DealBadge } from "./DealBadge";
import { DealTrustBadges } from "./DealTrustBadges";
import { ExternalLink, Flame, Package } from "lucide-react";

interface FeaturedDealProps {
  deal: DealItem;
}

export const FeaturedDeal: React.FC<FeaturedDealProps> = ({ deal }) => {
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
    <div className="relative bg-gradient-to-br from-orange-500/10 via-slate-900 to-slate-950 border-2 border-orange-500/30 rounded-2xl p-4 overflow-hidden shadow-lg">
      {/* Featured Header Pill */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-orange-500 text-white text-[10px] font-extrabold uppercase tracking-wider shadow">
          <Flame className="w-3 h-3 fill-white" />
          <span>FEATURED SPOTLIGHT</span>
        </div>
        <DealBadge variant="merchant" label={deal.platform} />
      </div>

      {/* Hero Image Container */}
      <div className="relative w-full h-48 bg-slate-950/80 rounded-xl p-3 flex items-center justify-center border border-orange-500/20 mb-3 overflow-hidden">
        {!imgFailed ? (
          <img
            src={imgSrc}
            alt={cleanTitle}
            onError={handleImageError}
            className="max-h-full max-w-full object-contain transition-transform duration-300 hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-slate-400">
            <Package className="w-12 h-12 text-orange-500 mb-1" />
            <span className="text-[10px] font-mono font-bold text-slate-400 uppercase">
              {deal.platform} Featured
            </span>
          </div>
        )}

        {discountVal > 0 && (
          <div className="absolute top-2 left-2">
            <DealBadge discount={discountVal} />
          </div>
        )}
      </div>

      {/* Deal Information */}
      <div className="space-y-2">
        <h3 className="text-sm font-extrabold text-white line-clamp-2 leading-snug">
          {cleanTitle}
        </h3>

        {/* Pricing Layout */}
        <div className="flex items-baseline gap-2 flex-wrap font-mono">
          <span className="text-2xl font-black text-emerald-400">
            ₹{deal.price ? deal.price.toLocaleString("en-IN") : "0"}
          </span>
          {deal.mrp && deal.mrp > deal.price && (
            <span className="text-xs font-semibold text-slate-400 line-through">
              ₹{deal.mrp.toLocaleString("en-IN")}
            </span>
          )}
          {savings > 0 && (
            <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              Save ₹{savings.toLocaleString("en-IN")}
            </span>
          )}
        </div>

        {/* Badges */}
        <DealTrustBadges isVerifiedLow={deal.is_verified_low} score={Math.round(deal.deal_score)} />

        {/* Direct CTA */}
        <a
          href={dealUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full py-2.5 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-extrabold text-xs uppercase tracking-wider rounded-xl flex items-center justify-center gap-1.5 shadow-md active:scale-95 transition-all mt-3"
        >
          <span>GET LOOT NOW</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
};
