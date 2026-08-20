import React from "react";
import { useTheme } from "../../theme/ThemeContext";

interface ThemeToggleProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

/**
 * Illustrated Day/Night Toggle Component
 * Features an interactive animated sky background with sun/clouds (day) and moon/stars (night).
 */
export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  className = "",
  size = "md",
}) => {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  // Size configurations
  const dimensions = {
    sm: { width: "w-14", height: "h-7", knob: "w-5 h-5", translate: "translate-x-7" },
    md: { width: "w-16", height: "h-8", knob: "w-6 h-6", translate: "translate-x-8" },
    lg: { width: "w-20", height: "h-10", knob: "w-8 h-8", translate: "translate-x-10" },
  }[size];

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={`Switch to ${isDark ? "Light" : "Dark"} mode`}
      title={`Switch to ${isDark ? "Light" : "Dark"} mode`}
      onClick={toggleTheme}
      className={`relative inline-flex items-center ${dimensions.width} ${dimensions.height} p-0.5 rounded-full transition-all duration-500 ease-in-out cursor-pointer select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 shadow-inner overflow-hidden shrink-0 ${
        isDark
          ? "bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 border border-slate-700/80 shadow-black/40"
          : "bg-gradient-to-r from-sky-400 via-blue-400 to-sky-300 border border-sky-300/80 shadow-blue-900/10"
      } ${className}`}
    >
      {/* Background Illustrated Sky Details */}
      <div className="absolute inset-0 pointer-events-none transition-opacity duration-500">
        {/* DAY SKY: Fluffy White Clouds */}
        <div
          className={`absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center transition-all duration-500 ${
            isDark ? "opacity-0 translate-y-2 scale-75" : "opacity-100 translate-y-0 scale-100"
          }`}
        >
          <svg className="w-6 h-4 text-white/90 drop-shadow-sm" viewBox="0 0 24 16" fill="currentColor">
            <path d="M19.35 6.04C18.67 2.59 15.64 0 12 0 9.11 0 6.6 1.64 5.35 4.04 2.34 4.36 0 6.91 0 10c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z" />
          </svg>
        </div>

        {/* NIGHT SKY: Stars & Sparkles */}
        <div
          className={`absolute left-2 top-1/2 -translate-y-1/2 flex items-center gap-1 transition-all duration-500 ${
            isDark ? "opacity-100 translate-y-0 scale-100" : "opacity-0 -translate-y-2 scale-75"
          }`}
        >
          {/* Star 1 */}
          <span className="inline-block w-1.5 h-1.5 bg-white rounded-full shadow-[0_0_4px_#fff] animate-pulse" />
          {/* Star 2 */}
          <span className="inline-block w-1 h-1 bg-amber-200 rounded-full shadow-[0_0_3px_#fde047] opacity-80" />
          {/* Star 3 */}
          <span className="inline-block w-0.5 h-0.5 bg-blue-200 rounded-full opacity-60" />
        </div>
      </div>

      {/* Sliding Celestial Orb (Sun / Moon) */}
      <div
        className={`relative ${dimensions.knob} rounded-full transition-transform duration-500 ease-out transform flex items-center justify-center shadow-md ${
          isDark
            ? `${dimensions.translate} bg-gradient-to-br from-amber-100 via-slate-200 to-slate-400 shadow-slate-900/60`
            : "translate-x-0.5 bg-gradient-to-br from-amber-300 via-amber-400 to-orange-400 shadow-orange-500/50"
        }`}
      >
        {isDark ? (
          /* Moon Illustrated Texture & Craters */
          <div className="relative w-full h-full rounded-full overflow-hidden flex items-center justify-center">
            {/* Crater 1 */}
            <span className="absolute top-1 right-1.5 w-1.5 h-1.5 bg-slate-400/40 rounded-full" />
            {/* Crater 2 */}
            <span className="absolute bottom-1 left-1.5 w-1 h-1 bg-slate-400/30 rounded-full" />
            {/* Crater 3 */}
            <span className="absolute top-2.5 left-1 w-0.5 h-0.5 bg-slate-400/40 rounded-full" />
          </div>
        ) : (
          /* Sun Illustrated Rays & Glow */
          <div className="relative w-full h-full rounded-full flex items-center justify-center">
            {/* Center Core */}
            <span className="w-2.5 h-2.5 bg-amber-100/90 rounded-full blur-[0.5px]" />
          </div>
        )}
      </div>
    </button>
  );
};
