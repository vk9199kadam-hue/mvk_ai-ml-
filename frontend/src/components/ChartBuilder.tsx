"use client";

import React, { useState, useCallback, useEffect } from "react";
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
import { cn } from "@/lib/utils";


// ── Color Palette ──────────────────────────────────────────────────────

const COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"];

// ── Chart Widget Definitions ───────────────────────────────────────────

interface ChartWidgetConfig {
  id: string;
  type: "bar" | "line" | "pie" | "scatter" | "area" | "heatmap";
  title: string;
  data: Record<string, any>[];
  xKey: string;
  yKey: string;
  color?: string;
}

let widgetCounter = 0;

function generateSampleData(type: string): { data: Record<string, any>[]; xKey: string; yKey: string } {
  if (type === "pie") {
    return {
      data: [
        { name: "Auto-Approved", value: 45 },
        { name: "Manual Review", value: 30 },
        { name: "Review Required", value: 20 },
        { name: "Advisory Only", value: 5 },
      ],
      xKey: "name",
      yKey: "value",
    };
  }
  return {
    data: [
      { label: "Jan", value: 12, value2: 8 },
      { label: "Feb", value: 19, value2: 14 },
      { label: "Mar", value: 15, value2: 11 },
      { label: "Apr", value: 22, value2: 16 },
      { label: "May", value: 18, value2: 13 },
      { label: "Jun", value: 25, value2: 19 },
    ],
    xKey: "label",
    yKey: "value",
  };
}

function createWidget(type: string): ChartWidgetConfig {
  widgetCounter++;
  const sample = generateSampleData(type);
  return {
    id: `widget-${widgetCounter}-${Date.now()}`,
    type: type as any,
    title: `${type.charAt(0).toUpperCase() + type.slice(1)} Chart`,
    data: sample.data,
    xKey: sample.xKey,
    yKey: sample.yKey,
    color: COLORS[widgetCounter % COLORS.length],
  };
}

// ── Chart Renderer ─────────────────────────────────────────────────────

function ChartRenderer({ widget }: { widget: ChartWidgetConfig }) {
  const { data, xKey, yKey, type, color } = widget;

  const renderChart = () => {
    switch (type) {
      case "bar":
        return (
          <BarChart data={data}>
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
          <LineChart data={data}>
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
            <Pie data={data} dataKey={yKey} nameKey={xKey} cx="50%" cy="50%" outerRadius={70}              label={({ name, percent = 0 }: any) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
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
            <Scatter data={data} fill={color || COLORS[4]} />
          </ScatterChart>
        );
      case "area":
        return (
          <AreaChart data={data}>
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

// ── Chart Widget Card ──────────────────────────────────────────────────

function WidgetCard({
  widget,
  onRemove,
  onTitleChange,
  onConfigChange,
}: {
  widget: ChartWidgetConfig;
  onRemove: () => void;
  onTitleChange: (title: string) => void;
  onConfigChange: (updates: Partial<ChartWidgetConfig>) => void;
}) {
  const [showConfig, setShowConfig] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden h-full flex flex-col">
      {/* Header with Drag Handle */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50/50">
        <div className="drag-handle flex items-center gap-2 flex-1 cursor-grab active:cursor-grabbing min-w-0">
          {/* 6-dot grip icon */}
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
            <select
              value={widget.type}
              onChange={(e) => onConfigChange({ type: e.target.value as any })}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1 mt-0.5"
            >
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
              <select value={widget.xKey} onChange={(e) => onConfigChange({ xKey: e.target.value })} className="w-full text-xs border border-gray-200 rounded px-2 py-1 mt-0.5">
                {Object.keys(widget.data[0] || {}).map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">Y-Axis</label>
              <select value={widget.yKey} onChange={(e) => onConfigChange({ yKey: e.target.value })} className="w-full text-xs border border-gray-200 rounded px-2 py-1 mt-0.5">
                {Object.keys(widget.data[0] || {}).map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Chart Content */}
      <div className="flex-1 p-2 min-h-0">
        <ChartRenderer widget={widget} />
      </div>
    </div>
  );
}

// ── Main ChartBuilder Component ────────────────────────────────────────

interface ChartBuilderProps {
  uploadId?: string;
  datasetId?: string;
  onSave?: (layout: any[], widgets: ChartWidgetConfig[]) => void;
}

export default function ChartBuilder({ uploadId, datasetId, onSave }: ChartBuilderProps) {
  const [widgets, setWidgets] = useState<ChartWidgetConfig[]>([]);
  const [layout, setLayout] = useState<LayoutItem[]>([]);
  const [saving, setSaving] = useState(false);

  // Generate layout items from widgets
  const layoutItems = widgets.map((w, i) => {
    const existing = layout.find((l) => l.i === w.id);
    return existing || {
      i: w.id,
      x: (i * 4) % 12,
      y: Math.floor(i / 3) * 4,
      w: 4,
      h: 4,
      minW: 2,
      minH: 3,
    };
  });

  const handleAddChart = useCallback((type: string) => {
    const newWidget = createWidget(type);
    setWidgets((prev) => [...prev, newWidget]);
    setLayout((prev) => [
      ...prev,
      {
        i: newWidget.id,
        x: (prev.length * 4) % 12,
        y: Math.floor(prev.length / 3) * 4,
        w: 4,
        h: 4,
        minW: 2,
        minH: 3,
      },
    ]);
  }, []);

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
    setSaving(true);
    try {
      if (onSave) {
        onSave(layout, widgets);
      }  // Store in localStorage
  localStorage.setItem("chartbuilder-layout", JSON.stringify(layout));
  localStorage.setItem("chartbuilder-widgets", JSON.stringify(widgets));
    } finally {
      setSaving(false);
    }
  }, [layout, widgets, onSave]);

  // Load from localStorage on mount
  useEffect(() => {
    const savedLayout = localStorage.getItem("chartbuilder-layout");
    const savedWidgets = localStorage.getItem("chartbuilder-widgets");
    if (savedLayout && savedWidgets) {
      try {
        setLayout(JSON.parse(savedLayout));
        setWidgets(JSON.parse(savedWidgets));
      } catch {}
    }
  }, []);

  return (
    <div className="flex gap-4 h-full">
      {/* Sidebar Palette */}
      <div className="w-48 shrink-0">
        <ChartPalette onAddChart={handleAddChart} />
        <div className="mt-4 space-y-2">
          <button
            onClick={handleSave}
            disabled={saving || widgets.length === 0}
            className="w-full btn-primary text-sm py-2 disabled:opacity-50"
          >
            {saving ? "Saving..." : "💾 Save Layout"}
          </button>
          {widgets.length > 0 && (
            <button
              onClick={() => { setWidgets([]); setLayout([]); localStorage.removeItem("chartbuilder-layout"); localStorage.removeItem("chartbuilder-widgets"); }}
              className="w-full btn-secondary text-sm py-2 text-red-600 border-red-200 hover:bg-red-50"
            >
              🗑️ Clear All
            </button>
          )}
        </div>
        {widgets.length > 0 && (
          <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
            <p className="text-[11px] text-blue-700">
              <strong>{widgets.length}</strong> chart{widgets.length > 1 ? "s" : ""} added.
              Drag to rearrange, resize from bottom-right corner.
            </p>
          </div>
        )}
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
              Click a chart type from the palette on the left to add it to the grid.
              Drag to rearrange and resize from the bottom-right corner.
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
