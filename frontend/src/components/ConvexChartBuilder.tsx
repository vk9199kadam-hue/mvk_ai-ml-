"use client";

import React, { useState, useCallback, useEffect, useMemo } from "react";
import { useQuery, useMutation } from "convex/react";
import { api } from "../../convex/_generated/api";
import { Responsive } from "react-grid-layout";
const GridLayout = Responsive as any;
import "react-grid-layout/css/styles.css";

interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
}
import {
  ResponsiveContainer,
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  ScatterChart, Scatter, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import ChartPalette from "./ChartPalette";
import type { Id } from "../../convex/_generated/dataModel";
import toast from "react-hot-toast";

// ── Color Palette ──────────────────────────────────────────────────────

const COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"];

// ── Chart Widget Config ─────────────────────────────────────────────────

interface ChartWidgetConfig {
  id: string;
  type: "bar" | "line" | "pie" | "scatter" | "area";
  title: string;
  xKey: string;
  yKey: string;
  color?: string;
}

let widgetCounter = 0;

// ── Chart Renderer ─────────────────────────────────────────────────────

function ChartRenderer({ widget, data }: { widget: ChartWidgetConfig; data: Record<string, any>[] }) {
  const { xKey, yKey, type, color } = widget;
  const chartData = data.length > 0 ? data : [{ [xKey]: "No Data", [yKey]: 0 }];

  const renderChart = () => {
    switch (type) {
      case "bar":
        return (
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey={yKey} fill={color || COLORS[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        );
      case "line":
        return (
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey={yKey} stroke={color || COLORS[1]} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
          </LineChart>
        );
      case "pie":
        return (
          <PieChart>
            <Pie data={chartData} dataKey={yKey} nameKey={xKey} cx="50%" cy="50%" outerRadius={70}
              label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
              {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          </PieChart>
        );
      case "scatter":
        return (
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis dataKey={yKey} tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Scatter data={chartData} fill={color || COLORS[4]} />
          </ScatterChart>
        );
      case "area":
        return (
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Area type="monotone" dataKey={yKey} stroke={color || COLORS[5]} fill={color || COLORS[5]} fillOpacity={0.2} strokeWidth={2} />
          </AreaChart>
        );
      default:
        return <p className="text-sm text-gray-400">Unsupported chart type</p>;
    }
  };

  return (
    <ResponsiveContainer width="100%" height="100%">
      {renderChart()}
    </ResponsiveContainer>
  );
}

// ── Widget Card ─────────────────────────────────────────────────────────

function WidgetCard({
  widget,
  columns,
  data,
  onRemove,
  onTitleChange,
  onConfigChange,
}: {
  widget: ChartWidgetConfig;
  columns: string[];
  data: Record<string, any>[];
  onRemove: () => void;
  onTitleChange: (title: string) => void;
  onConfigChange: (updates: Partial<ChartWidgetConfig>) => void;
}) {
  const [showConfig, setShowConfig] = useState(false);
  const numericColumns = columns;
  const allColumns = columns;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50/50">
        <div className="drag-handle flex items-center gap-2 flex-1 cursor-grab active:cursor-grabbing min-w-0">
          <svg className="w-4 h-4 text-gray-300 shrink-0" viewBox="0 0 16 16" fill="currentColor">
            <circle cx="5" cy="3" r="1.5" /><circle cx="11" cy="3" r="1.5" />
            <circle cx="5" cy="8" r="1.5" /><circle cx="11" cy="8" r="1.5" />
            <circle cx="5" cy="13" r="1.5" /><circle cx="11" cy="13" r="1.5" />
          </svg>
          <input
            value={widget.title}
            onChange={(e) => onTitleChange(e.target.value)}
            className="text-sm font-medium text-gray-900 bg-transparent border-none outline-none focus:ring-0 flex-1 truncate"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => { e.stopPropagation(); setShowConfig(!showConfig); }}
            className="p-1 rounded hover:bg-gray-200 transition-colors"
            title="Configure"
          >
            <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onRemove(); }}
            className="p-1 rounded hover:bg-red-100 transition-colors"
            title="Remove"
          >
            <svg className="w-3.5 h-3.5 text-gray-400 hover:text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Config Panel */}
      {showConfig && (
        <div className="px-3 py-2 border-b border-gray-100 bg-gray-50 space-y-2">
          <div>
            <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">Chart Type</label>
            <select value={widget.type} onChange={(e) => onConfigChange({ type: e.target.value as any })}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1 mt-0.5">
              <option value="bar">Bar Chart</option>
              <option value="line">Line Chart</option>
              <option value="pie">Pie Chart</option>
              <option value="scatter">Scatter Plot</option>
              <option value="area">Area Chart</option>
            </select>
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">X-Axis</label>
              <select value={widget.xKey} onChange={(e) => onConfigChange({ xKey: e.target.value })}
                className="w-full text-xs border border-gray-200 rounded px-2 py-1 mt-0.5">
                {allColumns.map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
            </div>
            <div className="flex-1">
              <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">Y-Axis</label>
              <select value={widget.yKey} onChange={(e) => onConfigChange({ yKey: e.target.value })}
                className="w-full text-xs border border-gray-200 rounded px-2 py-1 mt-0.5">
                {numericColumns.map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Chart Content */}
      <div className="flex-1 p-2 min-h-0">
        <ChartRenderer widget={widget} data={data} />
      </div>
    </div>
  );
}

// ── Main ConvexChartBuilder Component ─────────────────────────────────

interface ConvexChartBuilderProps {
  uploadId: string;
  userId?: string;
}

export default function ConvexChartBuilder({ uploadId, userId }: ConvexChartBuilderProps) {
  // Load real data from Convex
  const dataset = useQuery(api.datasets.getDatasetByUpload, { uploadId: uploadId as Id<"uploads"> });
  const data = useMemo(() => (dataset?.data || []) as Record<string, any>[], [dataset]);
  const columns = useMemo(() => (dataset?.columns || []) as string[], [dataset]);
  const isLoading = dataset === undefined;

  // Load dashboard from database
  const dashboard = useQuery(api.dashboards.getDashboardByUpload, { uploadId: uploadId as Id<"uploads"> });
  const createDashboard = useMutation(api.dashboards.createDashboard);
  const updateDashboard = useMutation(api.dashboards.updateDashboard);

  const [widgets, setWidgets] = useState<ChartWidgetConfig[]>([]);
  const [layout, setLayout] = useState<LayoutItem[]>([]);
  const [saving, setSaving] = useState(false);

  // Sync layout and widgets from database once loaded
  useEffect(() => {
    if (dashboard) {
      setLayout((dashboard.layout || []) as LayoutItem[]);
      setWidgets((dashboard.widgets || []) as ChartWidgetConfig[]);
    } else {
      setLayout([]);
      setWidgets([]);
    }
  }, [dashboard]);

  // Generate layout items from widgets
  const layoutItems = widgets.map((w, i) => {
    const existing = layout.find((l) => l.i === w.id);
    return existing || { i: w.id, x: (i * 4) % 12, y: Math.floor(i / 3) * 4, w: 4, h: 4, minW: 2, minH: 3 };
  });

  const handleAddChart = useCallback((type: string) => {
    widgetCounter++;
    const id = `widget-${widgetCounter}-${Date.now()}`;
    const numericCols = columns.filter((c) => data.some((r) => typeof r[c] === "number"));
    const xKey = columns[0] || "label";
    const yKey = numericCols[0] || columns[1] || columns[0] || "value";

    const newWidget: ChartWidgetConfig = {
      id,
      type: type as any,
      title: `${type.charAt(0).toUpperCase() + type.slice(1)} Chart`,
      xKey,
      yKey,
      color: COLORS[widgetCounter % COLORS.length],
    };
    setWidgets((prev) => [...prev, newWidget]);
    setLayout((prev) => [...prev, {
      i: id, x: (prev.length * 4) % 12, y: Math.floor(prev.length / 3) * 4,
      w: 4, h: 4, minW: 2, minH: 3,
    }]);
  }, [columns, data]);

  const handleRemoveWidget = useCallback((id: string) => {
    setWidgets((prev) => prev.filter((w) => w.id !== id));
    setLayout((prev) => prev.filter((l) => l.i !== id));
  }, []);

  const handleTitleChange = useCallback((id: string, title: string) => {
    setWidgets((prev) => prev.map((w) => (w.id === id ? { ...w, title } : w)));
  }, []);

  const handleConfigChange = useCallback((id: string, updates: Partial<ChartWidgetConfig>) => {
    setWidgets((prev) => prev.map((w) => (w.id === id ? { ...w, ...updates } : w)));
  }, []);

  const handleLayoutChange = useCallback((newLayout: any) => {
    setLayout([...newLayout]);
  }, []);

  const handleSave = useCallback(async () => {
    if (!userId) {
      toast.error("You must be logged in to save dashboard layout");
      return;
    }
    setSaving(true);
    try {
      if (dashboard) {
        // Update existing dashboard in Convex
        await updateDashboard({
          dashboardId: dashboard._id,
          layout: layout.map((l) => ({ i: l.i, x: l.x, y: l.y, w: l.w, h: l.h })),
          widgets: widgets,
          title: "Custom Dashboard",
        });
      } else {
        // Create new dashboard in Convex
        const numericCols = columns.filter((c) => data.some((r) => typeof r[c] === "number"));
        await createDashboard({
          uploadId: uploadId as Id<"uploads">,
          userId: userId as Id<"users">,
          title: "Custom Dashboard",
          columns,
          numericColumns: numericCols,
          rowCount: data.length,
          layout: layout.map((l) => ({ i: l.i, x: l.x, y: l.y, w: l.w, h: l.h })),
          widgets: widgets,
        });
      }
      toast.success("Dashboard layout saved to Convex cloud database!");
    } catch (err: any) {
      toast.error(err?.message || "Failed to save dashboard");
    } finally {
      setSaving(false);
    }
  }, [layout, widgets, uploadId, userId, dashboard, columns, data, createDashboard, updateDashboard]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-10 h-10 bg-blue-100 rounded-lg mx-auto mb-3 animate-pulse" />
          <p className="text-sm text-gray-500">Loading dataset...</p>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <p className="text-gray-400">No data available for this upload.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4 h-full">
      {/* Sidebar */}
      <div className="w-48 shrink-0">
        <ChartPalette onAddChart={handleAddChart} />
        <div className="mt-4 space-y-2">
          <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
            <p className="text-[11px] text-gray-500">
              <strong>{data.length}</strong> rows · <strong>{columns.length}</strong> columns
            </p>
          </div>
          <button onClick={handleSave} disabled={saving || widgets.length === 0}
            className="w-full btn-primary text-sm py-2 disabled:opacity-50">
            {saving ? "Saving..." : "💾 Save Layout"}
          </button>
          {widgets.length > 0 && (
            <button onClick={() => { setWidgets([]); setLayout([]); localStorage.removeItem("convex-chartbuilder-layout"); localStorage.removeItem("convex-chartbuilder-widgets"); }}
              className="w-full btn-secondary text-sm py-2 text-red-600 border-red-200 hover:bg-red-50">
              🗑️ Clear All
            </button>
          )}
        </div>
      </div>

      {/* Grid Canvas */}
      <div className="flex-1 min-h-[600px] bg-white rounded-xl border border-gray-200 p-4">
        {widgets.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-12">
            <div className="w-20 h-20 bg-gray-100 rounded-2xl flex items-center justify-center mb-4">
              <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Build Your Dashboard</h3>
            <p className="text-sm text-gray-500 max-w-sm">
              Dataset loaded with <strong>{data.length}</strong> rows and <strong>{columns.length}</strong> columns.
              Click a chart type from the palette to start visualizing your data.
            </p>
          </div>
        ) : (
          <GridLayout
            className="layout"
            layouts={{ lg: layoutItems, md: layoutItems, sm: layoutItems, xs: layoutItems }}
            cols={{ lg: 12, md: 10, sm: 6, xs: 1 }}
            breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480 }}
            onLayoutChange={handleLayoutChange}
            draggableHandle=".drag-handle"
            isResizable={true}
            isDraggable={true}
            compactType="vertical"
            margin={[12, 12]}
            containerPadding={[0, 0]}
            rowHeight={80}
          >
            {widgets.map((widget) => (
              <div key={widget.id}>
                <WidgetCard
                  widget={widget}
                  columns={columns}
                  data={data}
                  onRemove={() => handleRemoveWidget(widget.id)}
                  onTitleChange={(title) => handleTitleChange(widget.id, title)}
                  onConfigChange={(updates) => handleConfigChange(widget.id, updates)}
                />
              </div>
            ))}
          </GridLayout>
        )}
      </div>
    </div>
  );
}
