"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";

// Dynamic import for Plotly (avoids SSR issues)
const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => (
    <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
        <p className="text-xs text-gray-400">Loading chart...</p>
      </div>
    </div>
  ),
}) as any;

interface ChartDataPoint {
  x?: any[];
  y?: any[];
  z?: any[];
  labels?: string[];
  values?: number[];
  type?: string;
  name?: string;
  marker?: Record<string, any>;
  text?: string[];
  hovertemplate?: string;
  mode?: string;
  colorscale?: string;
}

interface ChartWidgetProps {
  data: ChartDataPoint[];
  layout?: Partial<{
    title: string;
    xaxis: Record<string, any>;
    yaxis: Record<string, any>;
    showlegend: boolean;
    legend: Record<string, any>;
    margin: Record<string, number>;
    height: number;
    paper_bgcolor: string;
    plot_bgcolor: string;
    hovermode: string;
    colorway: string[];
    clickmode: string;
  }>;
  config?: Partial<{
    displayModeBar: boolean;
    responsive: boolean;
    scrollZoom: boolean;
    displaylogo: boolean;
    modeBarButtonsToRemove: string[];
  }>;
  title?: string;
  className?: string;
  height?: number;
  onPointClick?: (data: { x: any; y: any; pointIndex: number; curveNumber: number }) => void;
}

const DEFAULT_COLORS = [
  "#2563eb", "#16a34a", "#d97706", "#dc2626",
  "#8b5cf6", "#ec4899", "#06b6d4", "#f97316",
];

export default function ChartWidget({
  data,
  layout: customLayout,
  config: customConfig,
  title,
  className,
  height = 300,
  onPointClick,
}: ChartWidgetProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const defaultLayout = {
    title: title || "",
    xaxis: { gridcolor: "#f3f4f6" },
    yaxis: { gridcolor: "#f3f4f6" },
    showlegend: true,
    legend: { orientation: "h" as const, y: -0.2 },
    margin: { t: 40, r: 20, b: 40, l: 50 },
    height: isExpanded ? Math.max(height * 1.5, 400) : height,
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    hovermode: "closest" as const,
    clickmode: "select" as const,
    colorway: DEFAULT_COLORS,
  };

  const defaultConfig = {
    displayModeBar: true,
    responsive: true,
    scrollZoom: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["sendDataToCloud", "lasso2d", "select2d"],
  };

  if (!data || data.length === 0) {
    return (
      <div
        className={cn(
          "h-64 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200 flex items-center justify-center",
          className
        )}
      >
        <p className="text-sm text-gray-400">No chart data available</p>
      </div>
    );
  }

  return (
    <div className={cn("relative group", className)}>
      <Plot
        data={data as any}
        layout={{ ...defaultLayout, ...customLayout } as any}
        config={{ ...defaultConfig, ...customConfig } as any}
        className="rounded-lg"
        onClick={onPointClick ? (event: any) => {
          if (event?.points?.[0]) {
            const pt = event.points[0];
            onPointClick({
              x: pt.x,
              y: pt.y,
              pointIndex: pt.pointIndex,
              curveNumber: pt.curveNumber,
            });
          }
        } : undefined}
      />
      {/* Expand button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="absolute top-2 right-2 p-1.5 bg-white/80 rounded-md opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white shadow-sm border border-gray-200"
        title={isExpanded ? "Collapse" : "Expand"}
      >
        <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {isExpanded ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          )}
        </svg>
      </button>
    </div>
  );
}

// ── Helper: Create sample chart data from relationship metadata ─────────

export function createChartData(
  type: string,
  labels?: string[],
  values?: number[],
  x?: any[],
  y?: any[]
): ChartDataPoint[] {
  switch (type) {
    case "bar":
      return [
        {
          x: labels || [],
          y: values || [],
          type: "bar",
          marker: { color: DEFAULT_COLORS[0] },
          hovertemplate: "%{x}: %{y}<extra></extra>",
        },
      ];
    case "line":
      return [
        {
          x: x || labels || [],
          y: y || values || [],
          type: "scatter",
          mode: "lines+markers",
          marker: { color: DEFAULT_COLORS[0] },
          hovertemplate: "(%{x}, %{y})<extra></extra>",
        },
      ];
    case "scatter":
      return [
        {
          x: x || [],
          y: y || [],
          type: "scatter",
          mode: "markers",
          marker: { color: DEFAULT_COLORS[0], size: 8 },
          hovertemplate: "(%{x}, %{y})<extra></extra>",
        },
      ];
    case "pie":
      return [
        {
          labels: labels || [],
          values: values || [],
          type: "pie",
          hovertemplate: "%{label}: %{percent}<extra></extra>",
        },
      ];
    case "heatmap":
      return [
        {
          z: [values || []] as any,
          type: "heatmap",
          colorscale: "Blues",
        },
      ];
    default:
      return [
        {
          x: x || labels || [],
          y: y || values || [],
          type: "bar",
          hovertemplate: "%{x}: %{y}<extra></extra>",
        },
      ];
  }
}
