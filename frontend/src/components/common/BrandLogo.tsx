import React from "react";

interface BrandLogoProps {
  variant?: "full" | "crest_only" | "compact";
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

export const BrandLogo: React.FC<BrandLogoProps> = ({
  variant = "full",
  size = "md",
  className = "",
}) => {
  const sizeMap = {
    sm: { img: "h-8 sm:h-9", text: "text-sm" },
    md: { img: "h-10 sm:h-12", text: "text-lg" },
    lg: { img: "h-16 sm:h-20", text: "text-2xl" },
    xl: { img: "h-24 sm:h-28", text: "text-3xl" },
  };

  const currentSize = sizeMap[size];

  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      {/* Official 11.png Loot Raiders Crest Emblem Image */}
      <div className="relative flex items-center justify-center shrink-0">
        <img
          src="/logo.png"
          alt="Loot Raiders Official Crest"
          className={`${currentSize.img} object-contain filter drop-shadow-md transition-transform duration-300 hover:scale-105`}
          onError={(e) => {
            // Fallback if image path fails
            e.currentTarget.style.display = "none";
          }}
        />
      </div>

      {/* Brand Wordmark & Subtitle */}
      {variant !== "crest_only" && (
        <div className="flex flex-col">
          <div className={`font-extrabold tracking-wider leading-none ${currentSize.text} text-slate-900 dark:text-white font-mono`}>
            LOOT <span className="text-orange-500 font-extrabold">RAIDERS</span>
          </div>
          {variant === "full" && (
            <span className="text-[10px] font-semibold tracking-widest uppercase text-amber-500/90 dark:text-amber-400/90 mt-0.5 font-sans">
              AI Deal Intelligence OS
            </span>
          )}
        </div>
      )}
    </div>
  );
};
