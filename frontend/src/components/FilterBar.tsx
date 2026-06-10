"use client";

import React from "react";
import { useDashboardFilters } from "@/store";

export default function FilterBar() {
  const {
    confidenceMin,
    searchQuery,
    dateRange,
    setConfidenceMin,
    setSearchQuery,
    setDateRange,
    reset,
  } = useDashboardFilters();

  return (
    <div className="card p-4">
      <div className="flex items-center flex-wrap gap-3">
        {/* Search */}
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search reports, datasets..."
            className="input-field text-sm"
          />
        </div>

        {/* Confidence Filter */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500 whitespace-nowrap">
            Min Confidence:
          </label>
          <select
            value={confidenceMin}
            onChange={(e) => setConfidenceMin(Number(e.target.value))}
            className="input-field !w-24 text-sm"
          >
            <option value={0}>Any</option>
            <option value={0.5}>≥ 50%</option>
            <option value={0.7}>≥ 70%</option>
            <option value={0.9}>≥ 90%</option>
          </select>
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">From:</label>
          <input
            type="date"
            value={dateRange?.[0] || ""}
            onChange={(e) =>
              setDateRange([e.target.value, dateRange?.[1] || ""])
            }
            className="input-field !w-36 text-sm"
          />
          <label className="text-xs text-gray-500">To:</label>
          <input
            type="date"
            value={dateRange?.[1] || ""}
            onChange={(e) =>
              setDateRange([dateRange?.[0] || "", e.target.value])
            }
            className="input-field !w-36 text-sm"
          />
        </div>

        {/* Reset */}
        <button
          onClick={reset}
          className="px-3 py-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
        >
          Reset Filters
        </button>
      </div>
    </div>
  );
}
