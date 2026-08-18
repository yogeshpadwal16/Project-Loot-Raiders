import React from "react";

interface DealBadgeProps {
  discount?: number;
  label?: string;
  variant?: "discount" | "hot" | "merchant" | "crash";
  className?: string;
}

export const DealBadge: React.FC<DealBadgeProps> = ({
  discount,
  label,
  variant = "discount",
  className = "",
}) => {
  if (variant === "hot") {
    return (
      <span className={`inline-flex items-center gap-1 bg-rose-500 text-white text-[10px] font-black uppercase px-2 py-0.5 rounded-full shadow-sm ${className}`}>
        🔥 HOT DEAL
      </span>
    );
  }

  if (variant === "crash") {
    return (
      <span className={`inline-flex items-center gap-1 bg-amber-500 text-slate-950 text-[10px] font-black uppercase px-2 py-0.5 rounded-full shadow-sm ${className}`}>
        ⚡ PRICE CRASH
      </span>
    );
  }

  if (variant === "merchant" && label) {
    return (
      <span className={`inline-flex items-center text-[10px] font-black uppercase text-orange-500 dark:text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded-md border border-orange-500/20 ${className}`}>
        {label}
      </span>
    );
  }

  if (discount && discount > 0) {
    return (
      <span className={`inline-flex items-center text-[11px] font-extrabold text-white bg-rose-600 dark:bg-rose-500 px-2 py-0.5 rounded-lg shadow-sm ${className}`}>
        {Math.round(discount)}% OFF
      </span>
    );
  }

  return null;
};
