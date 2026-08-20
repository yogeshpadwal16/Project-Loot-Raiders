import React from "react";

interface BrandLogoProps {
  variant?: "full" | "crest_only" | "compact";
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
  subtitle?: string;
}

export const BrandLogo: React.FC<BrandLogoProps> = ({
  variant = "full",
  size = "md",
  className = "",
  subtitle = "Best Deals. Zero Nonsense.",
}) => {
  const sizeMap = {
    sm: { img: "h-7 sm:h-8", title: "text-base tracking-tight", sub: "text-[9px]" },
    md: { img: "h-9 sm:h-10", title: "text-lg tracking-tight", sub: "text-[10px]" },
    lg: { img: "h-14 sm:h-16", title: "text-2xl tracking-tight", sub: "text-xs" },
    xl: { img: "h-20 sm:h-24", title: "text-3xl tracking-tight", sub: "text-sm" },
  };

  const currentSize = sizeMap[size];

  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {/* Official Loot Raiders Crest Emblem */}
      <div className="relative flex items-center justify-center shrink-0">
        <img
          src="/logo.png"
          alt="Loot Raiders Official Crest"
          className={`${currentSize.img} object-contain filter drop-shadow-sm transition-transform duration-300 group-hover:scale-105`}
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      </div>

      {/* Brand Wordmark & Tagline */}
      {variant !== "crest_only" && (
        <div className="flex flex-col justify-center">
          <div className={`font-black font-sans leading-none uppercase ${currentSize.title}`}>
            <span className="text-slate-900 dark:text-white transition-colors">LOOT </span>
            <span className="text-orange-500 font-black">RAIDERS</span>
          </div>
          {variant === "full" && (
            <span className={`${currentSize.sub} font-medium tracking-wide text-slate-500 dark:text-slate-400 mt-0.5 font-sans`}>
              {subtitle}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
