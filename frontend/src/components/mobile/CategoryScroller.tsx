import React from "react";

export interface CategoryItem {
  id: string;
  label: string;
  icon?: string;
}

interface CategoryScrollerProps {
  categories?: CategoryItem[];
  selectedCategory: string;
  onSelectCategory: (id: string) => void;
}

const DEFAULT_CATEGORIES: CategoryItem[] = [
  { id: "all", label: "🔥 All Deals" },
  { id: "electronics", label: "⚡ Electronics" },
  { id: "wearables", label: "⌚ Wearables" },
  { id: "audio", label: "🎧 Audio" },
  { id: "laptops", label: "💻 Laptops" },
  { id: "fashion", label: "👟 Fashion" },
  { id: "home", label: "🏠 Home" },
];

export const CategoryScroller: React.FC<CategoryScrollerProps> = ({
  categories = DEFAULT_CATEGORIES,
  selectedCategory,
  onSelectCategory,
}) => {
  return (
    <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1 px-0.5 -mx-1 select-none">
      {categories.map((cat) => {
        const isSelected = selectedCategory === cat.id;
        return (
          <button
            key={cat.id}
            onClick={() => onSelectCategory(cat.id)}
            className={`px-3.5 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all shrink-0 border ${
              isSelected
                ? "bg-orange-500 text-white border-orange-500 shadow-sm shadow-orange-500/20"
                : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800/80 hover:text-slate-900 dark:hover:text-white"
            }`}
          >
            {cat.label}
          </button>
        );
      })}
    </div>
  );
};
