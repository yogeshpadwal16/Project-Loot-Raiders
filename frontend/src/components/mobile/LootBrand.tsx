import React from "react";

interface LootBrandProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  showTagline?: boolean;
}

export const LootBrand: React.FC<LootBrandProps> = ({
  size = "md",
  className = "",
  showTagline = true,
}) => {
  const sizeMap = {
    sm: { img: "h-8", title: "text-base", sub: "text-[9px]" },
    md: { img: "h-9", title: "text-lg", sub: "text-[10px]" },
    lg: { img: "h-12", title: "text-xl", sub: "text-xs" },
  };

  const current = sizeMap[size];

  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      <img
        src="/logo.png"
        alt="Loot Raiders Crest"
        className={`${current.img} object-contain filter drop-shadow-sm`}
        onError={(e) => {
          e.currentTarget.style.display = "none";
        }}
      />
      <div className="flex flex-col">
        <div className={`font-black font-sans leading-none uppercase ${current.title} tracking-tight`}>
          <span className="text-slate-900 dark:text-white transition-colors">LOOT </span>
          <span className="text-orange-500 font-black">RAIDERS</span>
        </div>
        {showTagline && (
          <span className={`${current.sub} font-medium tracking-wide text-slate-500 dark:text-slate-400 mt-0.5 font-sans`}>
            Best Deals. Zero Nonsense.
          </span>
        )}
      </div>
    </div>
  );
};
