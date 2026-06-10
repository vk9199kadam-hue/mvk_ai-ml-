"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface ChartTypeItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  description: string;
}

const CHART_TYPES: ChartTypeItem[] = [
  {
    id: "bar",
    label: "Bar Chart",
    description: "Compare values across categories",
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <rect x="4" y="14" width="4" height="6" rx="1" />
        <rect x="10" y="8" width="4" height="12" rx="1" />
        <rect x="16" y="4" width="4" height="16" rx="1" />
      </svg>
    ),
  },
  {
    id: "line",
    label: "Line Chart",
    description: "Show trends over time",
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <path d="M3 17l4-4 4 4 8-8" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="7" cy="13" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="11" cy="17" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="19" cy="9" r="1.5" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    id: "pie",
    label: "Pie Chart",
    description: "Show proportions and percentages",
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <circle cx="12" cy="12" r="8" strokeDasharray="3 3" />
        <path d="M12 4v8l6.93 4" />
      </svg>
    ),
  },
  {
    id: "scatter",
    label: "Scatter Plot",
    description: "Find correlations between variables",
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <circle cx="6" cy="16" r="2" fill="currentColor" stroke="none" />
        <circle cx="12" cy="8" r="2" fill="currentColor" stroke="none" />
        <circle cx="18" cy="14" r="2" fill="currentColor" stroke="none" />
        <circle cx="9" cy="18" r="2" fill="currentColor" stroke="none" />
        <circle cx="15" cy="10" r="2" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    id: "area",
    label: "Area Chart",
    description: "Emphasize magnitude of change",
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <path d="M3 17l4-4 4 4 4-6 6 4v6H3z" strokeLinejoin="round" opacity={0.3} stroke="none" fill="currentColor" />
        <path d="M3 17l4-4 4 4 4-6 6 4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "heatmap",
    label: "Heatmap",
    description: "Visualize data density and patterns",
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <rect x="3" y="3" width="4" height="4" rx="1" fill="currentColor" opacity={0.3} stroke="none" />
        <rect x="9" y="3" width="4" height="4" rx="1" fill="currentColor" opacity={0.6} stroke="none" />
        <rect x="15" y="3" width="4" height="4" rx="1" fill="currentColor" opacity={0.9} stroke="none" />
        <rect x="3" y="9" width="4" height="4" rx="1" fill="currentColor" opacity={0.6} stroke="none" />
        <rect x="9" y="9" width="4" height="4" rx="1" fill="currentColor" opacity={0.4} stroke="none" />
        <rect x="15" y="9" width="4" height="4" rx="1" fill="currentColor" opacity={0.7} stroke="none" />
        <rect x="3" y="15" width="4" height="4" rx="1" fill="currentColor" opacity={0.9} stroke="none" />
        <rect x="9" y="15" width="4" height="4" rx="1" fill="currentColor" opacity={0.7} stroke="none" />
        <rect x="15" y="15" width="4" height="4" rx="1" fill="currentColor" opacity={0.3} stroke="none" />
      </svg>
    ),
  },
];

interface ChartPaletteProps {
  onAddChart: (type: string) => void;
}

export default function ChartPalette({ onAddChart }: ChartPaletteProps) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
        </svg>
        Chart Types
      </h3>
      <div className="grid grid-cols-2 gap-2">
        {CHART_TYPES.map((chart) => (
          <button
            key={chart.id}
            onClick={() => onAddChart(chart.id)}
            className={cn(
              "p-3 rounded-lg border border-gray-200 hover:border-blue-300",
              "hover:bg-blue-50 transition-all duration-200",
              "flex flex-col items-center gap-1.5 text-center"
            )}
            title={chart.description}
          >
            <span className="text-blue-600">{chart.icon}</span>
            <span className="text-xs font-medium text-gray-700">{chart.label}</span>
          </button>
        ))}
      </div>
      <p className="text-[10px] text-gray-400 mt-2 text-center">
        Click a chart type to add it to the grid
      </p>
    </div>
  );
}
