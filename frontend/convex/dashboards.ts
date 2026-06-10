import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

// ===== QUERIES =====

export const getDashboard = query({
  args: { dashboardId: v.id("dashboards") },
  handler: async (ctx, args) => {
    const dashboard = await ctx.db.get(args.dashboardId);
    if (!dashboard) return null;

    return {
      id: dashboard._id,
      title: dashboard.title,
      layout: dashboard.layout,
      widgets: dashboard.widgets,
      createdAt: dashboard.createdAt,
    };
  },
});

export const listDashboards = query({
  args: { userId: v.id("users") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("dashboards")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .order("desc")
      .collect();
  },
});

export const getDashboardByUpload = query({
  args: { uploadId: v.id("uploads") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("dashboards")
      .filter((q) => q.eq(q.field("uploadId"), args.uploadId))
      .first();
  },
});

// ===== MUTATIONS =====

export const createDashboard = mutation({
  args: {
    uploadId: v.id("uploads"),
    userId: v.id("users"),
    title: v.optional(v.string()),
    columns: v.array(v.string()),
    numericColumns: v.array(v.string()),
    relationships: v.optional(v.any()),
    rowCount: v.number(),
    layout: v.optional(
      v.array(
        v.object({
          i: v.string(),
          x: v.number(),
          y: v.number(),
          w: v.number(),
          h: v.number(),
        })
      )
    ),
    widgets: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    let dashboard;
    if (args.layout && args.widgets) {
      dashboard = {
        uploadId: args.uploadId,
        userId: args.userId,
        title: args.title || "Custom Dashboard",
        layout: args.layout,
        widgets: args.widgets,
        createdAt: Date.now(),
      };
    } else {
      dashboard = generateDashboard(args);
    }

    return await ctx.db.insert("dashboards", dashboard);
  },
});

export const updateDashboard = mutation({
  args: {
    dashboardId: v.id("dashboards"),
    layout: v.optional(
      v.array(
        v.object({
          i: v.string(),
          x: v.number(),
          y: v.number(),
          w: v.number(),
          h: v.number(),
        })
      )
    ),
    widgets: v.optional(v.any()),
    title: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const patch: Record<string, any> = {};
    if (args.layout) patch.layout = args.layout;
    if (args.widgets) patch.widgets = args.widgets;
    if (args.title) patch.title = args.title;
    await ctx.db.patch(args.dashboardId, patch);
  },
});

export const deleteDashboard = mutation({
  args: { dashboardId: v.id("dashboards") },
  handler: async (ctx, args) => {
    await ctx.db.delete(args.dashboardId);
  },
});

// ===== DASHBOARD GENERATION ENGINE =====

// Dashboard input for the generation function
function generateDashboard(args: {
  uploadId: any;
  userId: any;
  title?: string;
  columns: string[];
  numericColumns: string[];
  relationships?: any;
  rowCount: number;
}) {
  const { columns, numericColumns, relationships, rowCount } = args;
  const rels = (relationships || []) as any[];

  const widgets: Record<string, any> = {};
  const layout: Array<{ i: string; x: number; y: number; w: number; h: number }> = [];

  let yPos = 0;

  // 1. KPI Cards for numeric columns
  for (let i = 0; i < Math.min(numericColumns.length, 4); i++) {
    const col = numericColumns[i];
    const id = `kpi_${i}`;
    widgets[id] = {
      type: "kpi",
      title: `Average ${col}`,
      column: col,
      aggregation: "avg",
      data: null, // Will be populated from dataset
    };
    layout.push({ i: id, x: i % 2, y: yPos, w: 1, h: 1 });
    if (i % 2 === 1) yPos++;
  }
  if (numericColumns.length > 0) yPos++;

  // 2. Charts from relationships
  for (let i = 0; i < Math.min(rels.length, 6); i++) {
    const rel = rels[i];
    const id = `chart_${i}`;
    const chartType = rel.chartHint || getDefaultChartType(rel);

    widgets[id] = {
      type: "chart",
      chartType,
      title: `${rel.sourceColumn} vs ${rel.targetColumn}`,
      sourceColumn: rel.sourceColumn,
      targetColumn: rel.targetColumn,
      description: rel.description,
      data: null,
    };
    layout.push({ i: id, x: (i % 2) * 2, y: yPos, w: 2, h: 2 });
    yPos += 2;
  }

  // 3. Data table if no relationships
  if (rels.length === 0 && columns.length > 0) {
    const id = "data_table";
    widgets[id] = {
      type: "table",
      title: "Data Overview",
      columns: columns.slice(0, 10),
      data: null,
    };
    layout.push({ i: id, x: 0, y: yPos, w: 4, h: 2 });
  }

  // 4. Summary card
  const statId = "stats_summary";
  widgets[statId] = {
    type: "stat_summary",
    title: "Dataset Summary",
    rowCount,
    columnCount: columns.length,
    numericCount: numericColumns.length,
    relationshipCount: rels.length,
  };
  layout.push({ i: statId, x: 0, y: yPos, w: 4, h: 1 });

  return {
    uploadId: args.uploadId,
    userId: args.userId,
    title: args.title || "Auto-Generated Dashboard",
    layout,
    widgets,
    createdAt: Date.now(),
  };
}

function getDefaultChartType(rel: any): string {
  const type = rel.relationshipType || "";
  const hint = rel.chartHint || "";
  if (hint) return hint;
  if (type === "one-to-one") return "scatter";
  if (type === "one-to-many") return "bar";
  if (type === "many-to-many") return "heatmap";
  return "bar";
}
