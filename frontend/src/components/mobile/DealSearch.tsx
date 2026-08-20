import React from "react";
import { Search, X } from "lucide-react";

interface DealSearchProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
}

export const DealSearch: React.FC<DealSearchProps> = ({
  value,
  onChange,
  placeholder = "Search deals, brands, products...",
}) => {
  return (
    <div className="relative w-full">
      <Search className="w-4 h-4 text-orange-500 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 border border-slate-200 dark:border-slate-800/80 rounded-2xl pl-10 pr-9 py-2.5 text-xs font-sans focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-all shadow-sm"
      />
      {value && (
        <button
          onClick={() => onChange("")}
          className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          aria-label="Clear search"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};
