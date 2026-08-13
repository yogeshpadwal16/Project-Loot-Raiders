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
    sm: { icon: 24, text: "text-sm" },
    md: { icon: 32, text: "text-lg" },
    lg: { icon: 44, text: "text-2xl" },
    xl: { icon: 60, text: "text-3xl" },
  };

  const currentSize = sizeMap[size];

  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      {/* Finalized Loot Raiders Crest Icon */}
      <div className="relative flex items-center justify-center shrink-0">
        <svg
          width={currentSize.icon}
          height={currentSize.icon}
          viewBox="0 0 100 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="filter drop-shadow-md transition-transform duration-300 hover:scale-105"
        >
          <defs>
            <linearGradient id="shieldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#0B132B" />
              <stop offset="100%" stopColor="#1C2951" />
            </linearGradient>
            <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#FFD700" />
              <stop offset="50%" stopColor="#FFA500" />
              <stop offset="100%" stopColor="#D4AF37" />
            </linearGradient>
            <linearGradient id="orangeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#FF7A00" />
              <stop offset="100%" stopColor="#FF3D00" />
            </linearGradient>
          </defs>

          {/* Shield Outer Border */}
          <path
            d="M50 5 L88 20 V52 C88 74 71 90 50 97 C29 90 12 74 12 52 V20 L50 5 Z"
            fill="url(#shieldGrad)"
            stroke="url(#goldGrad)"
            strokeWidth="3.5"
          />

          {/* Inner Shield Accent */}
          <path
            d="M50 12 L80 24 V50 C80 68 67 82 50 88 C33 82 20 68 20 50 V24 L50 12 Z"
            fill="#080D1A"
            stroke="url(#orangeGrad)"
            strokeWidth="1.5"
            opacity="0.85"
          />

          {/* Crown Top Accent */}
          <path
            d="M36 28 L43 35 L50 25 L57 35 L64 28 L61 40 H39 L36 28 Z"
            fill="url(#goldGrad)"
          />

          {/* LR Monogram Cross Swords / Compass Geometry */}
          <path
            d="M33 46 H44 V72 C44 75 41 78 38 78 H33 V72 H37 V52 H33 V46 Z"
            fill="url(#goldGrad)"
          />
          <path
            d="M54 46 H67 C71.5 46 75 49.5 75 54 C75 57.5 72.5 60.5 69 61.5 L76 78 H69 L63 62 H60 V78 H54 V46 Z M60 52 V57 H66 C67.5 57 69 56 69 54.5 C69 53 67.5 52 66 52 H60 Z"
            fill="url(#orangeGrad)"
          />

          {/* Compass Star Dot */}
          <circle cx="50" cy="21" r="2.5" fill="#FFFFFF" />
        </svg>
      </div>

      {/* Brand Wordmark (Visible for 'full' and 'compact') */}
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
