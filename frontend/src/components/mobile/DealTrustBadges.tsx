import React from "react";
import { ShieldCheck, TrendingDown, Sparkles } from "lucide-react";

interface DealTrustBadgesProps {
  isVerifiedLow?: boolean;
  score?: number;
  discount?: number;
  className?: string;
}

export const DealTrustBadges: React.FC<DealTrustBadgesProps> = ({
  isVerifiedLow,
  score = 0,
  discount = 0,
  className = "",
}) => {
  return (
    <div className={`flex flex-wrap items-center gap-1.5 ${className}`}>
      {/* Historical Low Badge */}
      {isVerifiedLow && (
        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 dark:bg-emerald-500/15 px-2 py-0.5 rounded-md border border-emerald-500/20">
          <TrendingDown className="w-3 h-3" />
          All-Time Low
        </span>
      )}

      {/* AI Verified / Safe Deal */}
      {score >= 70 && (
        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 dark:bg-blue-500/15 px-2 py-0.5 rounded-md border border-blue-500/20">
          <ShieldCheck className="w-3 h-3" />
          AI Verified
        </span>
      )}

      {/* Best Price */}
      {discount >= 60 && !isVerifiedLow && (
        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-600 dark:text-amber-400 bg-amber-500/10 dark:bg-amber-500/15 px-2 py-0.5 rounded-md border border-amber-500/20">
          <Sparkles className="w-3 h-3" />
          Best Price
        </span>
      )}
    </div>
  );
};
