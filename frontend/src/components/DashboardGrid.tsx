"use client";

import React from "react";
import ChartWidget, { createChartData } from "./ChartWidget";

interface ChartConfig {
  id: string;
  title: string;
  type: "bar" | "line" | "scatter" | "pie" | "heatmap";
  labels?: string[];
  values?: number[];
  x?: any[];
  y?: any[];
  size?: "small" | "medium" | "large";
}

interface DashboardGridProps {
  charts?: ChartConfig[];
  loading?: boolean;
}

const SIZES: Record<string, string> = {
  small: "col-span-1",
  medium: "col-span-1 md:col-span-2",
  large: "col-span-1 md:col-span-3 lg:col-span-2",
};

// Sample charts when no data is available
const SAMPLE_CHARTS: ChartConfig[] = [
  {
    id: "chart-1",
    title: "Pipeline Runs (Last 7 Days)",
    type: "bar",
    labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    values: [3, 5, 2, 7, 4, 1, 6],
    size: "medium",
  },
  {
    id: "chart-2",
    title: "Confidence Distribution",
    type: "pie",
    labels: ["Auto-Approved", "Manual", "Review", "Advisory"],
    values: [45, 30, 20, 5],
    size: "small",
  },
  {
    id: "chart-3",
    title: "Processing Time Trend",
    type: "line",
    x: ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"],
    y: [12.5, 10.2, 11.8, 9.5, 8.7],
    size: "medium",
  },
  {
    id: "chart-4",
    title: "File Sizes",
    type: "bar",
    labels: ["CSV A", "CSV B", "CSV C", "CSV D"],
    values: [2.5, 15.3, 0.8, 7.2],
    size: "small",
  },
];

export default function DashboardGrid({
  charts,
  loading = false,
}: DashboardGridProps) {
  const displayCharts = charts || SAMPLE_CHARTS;

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`${SIZES[i === 1 ? "medium" : "small"]} skeleton h-64 rounded-xl`}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {displayCharts.map((chart) => (
        <div key={chart.id} className={`${SIZES[chart.size || "small"]}`}>
          <ChartWidget
            data={createChartData(
              chart.type,
              chart.labels,
              chart.values,
              chart.x,
              chart.y
            )}
            title={chart.title}
            height={chart.size === "large" ? 400 : 280}
          />
        </div>
      ))}
    </div>
  );
}
