import { v } from "convex/values";
import { action, mutation, query } from "./_generated/server";
import { internal as internalRaw } from "./_generated/api";
const internal = internalRaw as any;
import {
  callLlm,
  parseJsonResponse,
} from "./lib/openrouter";
import { getReportAgentPrompt } from "./lib/prompts";

// ===== CONFIDENCE GATING CONSTANTS =====
const CONFIDENCE_THRESHOLD = 0.65;
const MAX_RETRIES = 3;

// ===== QUERIES =====

export const getReport = query({
  args: { reportId: v.id("reports") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.reportId);
  },
});

export const listReports = query({
  args: { userId: v.id("users") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("reports")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .order("desc")
      .collect();
  },
});

// ===== MUTATION: Initialize report =====

export const initReport = mutation({
  args: {
    uploadId: v.id("uploads"),
    userId: v.id("users"),
    title: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("reports", {
      uploadId: args.uploadId,
      userId: args.userId,
      title: args.title || "Auto-Generated Analytical Report",
      sections: [],
      overallConfidence: 0,
      createdAt: Date.now(),
    });
  },
});

export const updateReportSections = mutation({
  args: {
    reportId: v.id("reports"),
    sections: v.array(
      v.object({
        sectionType: v.string(),
        title: v.string(),
        content: v.string(),
        confidence: v.number(),
      })
    ),
    overallConfidence: v.number(),
  },
  handler: async (ctx, args) => {
    const report = await ctx.db.get(args.reportId);
    if (report) {
      // Snapshot the current state as a version before modifying it
      await ctx.db.insert("reportVersions", {
        reportId: args.reportId,
        userId: report.userId,
        title: report.title,
        sections: report.sections,
        changedBy: "user",
        createdAt: Date.now(),
      });
    }

    await ctx.db.patch(args.reportId, {
      sections: args.sections,
      overallConfidence: args.overallConfidence,
    });
  },
});

export const updateSingleReportSection = mutation({
  args: {
    reportId: v.id("reports"),
    sectionType: v.string(),
    content: v.string(),
    userId: v.optional(v.id("users")),
    changedBy: v.optional(v.union(v.literal("user"), v.literal("ai"))),
  },
  handler: async (ctx, args) => {
    const report = await ctx.db.get(args.reportId);
    if (!report) throw new Error("Report not found");

    const changedBy = args.changedBy || "user";
    const userId = args.userId || report.userId;

    // Snapshot the current sections before modifying the section
    await ctx.db.insert("reportVersions", {
      reportId: args.reportId,
      userId,
      title: report.title,
      sections: report.sections,
      changedBy,
      createdAt: Date.now(),
    });

    const updatedSections = report.sections.map((sec) => {
      if (sec.sectionType === args.sectionType) {
        return { ...sec, content: args.content };
      }
      return sec;
    });

    await ctx.db.patch(args.reportId, {
      sections: updatedSections,
    });
  },
});

// ===== REPORT AGENT TYPES =====

const AGENT_TYPES = [
  "business_understanding",
  "data_collection",
  "cleaning_analysis",
  "eda",
  "statistical_analysis",
  "dashboard_viz",
  "insights",
  "recommendations",
];

// ===== CORE REPORT GENERATION ACTION =====

export const generateReport = action({
  args: {
    uploadId: v.id("uploads"),
    userId: v.id("users"),
    datasetId: v.id("datasets"),
    pipelineId: v.id("pipelineResults"),
    title: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    // Initialize the report
    const reportId = (await ctx.runMutation(internal.reports.initReport, {
      uploadId: args.uploadId,
      userId: args.userId,
      title: args.title,
    })) as any;

    // Get pipeline results for data
    const pipelineResult = await ctx.runQuery(
      internal.pipeline.getPipelineResult,
      { pipelineId: args.pipelineId }
    );

    const dataset = await ctx.runQuery(internal.datasets.getDataset, {
      datasetId: args.datasetId,
    });

    if (!dataset || !dataset.data) {
      throw new Error("No dataset available for report generation");
    }

    const data = dataset.data as Record<string, any>[];
    const columns = dataset.columns as string[];
    const udm = pipelineResult?.unifiedDataModel || {};

    // Build data profile for LLM agents
    const dataProfile = buildDataProfile(data, columns, udm);

    // Run 8 sub-agents in parallel
    const sections = await runSubAgentsInParallel(dataProfile, udm);

    // Calculate overall confidence
    const overallConfidence =
      sections.length > 0
        ? Math.round(
            (sections.reduce((sum, s) => sum + s.confidence, 0) /
              sections.length) *
              10000
          ) / 10000
        : 0;

    // Save to DB
    await ctx.runMutation(internal.reports.updateReportSections, {
      reportId,
      sections,
      overallConfidence,
    });

    return {
      reportId,
      title: args.title || "Auto-Generated Analytical Report",
      sections,
      overallConfidence,
      sectionCount: sections.length,
    };
  },
});

// ===== RUN 8 SUB-AGENTS IN PARALLEL =====

async function runSubAgentsInParallel(
  dataProfile: string,
  udm: any
): Promise<
  Array<{
    sectionType: string;
    title: string;
    content: string;
    confidence: number;
  }>
> {
  const apiKey = process.env.OPENROUTER_API_KEY;

  if (!apiKey) {
    // Deterministic fallback
    return AGENT_TYPES.map((type) => generateFallbackSection(type, dataProfile, udm));
  }

  const variables: Record<string, string> = {
    dataProfile,
    auditLog: JSON.stringify(udm.transformationAudit || [], null, 2),
    univariateStats: JSON.stringify({}),
    correlationMatrix: JSON.stringify({}),
    relationships: JSON.stringify(udm.relationships || [], null, 2),
    insights: "See analysis above",
    businessContext: "General business data analysis",
  };

  // Launch all 8 agents in parallel with retry + confidence gating
  const promises = AGENT_TYPES.map(async (agentType) => {
    return await callAgentWithRetry(agentType, apiKey!, dataProfile, udm, variables);
  });

  return await Promise.all(promises);
}

// ===== CONFIDENCE GATING: Retry logic with temperature escalation =====

async function callAgentWithRetry(
  agentType: string,
  apiKey: string,
  dataProfile: string,
  udm: any,
  variables: Record<string, string>
): Promise<{
  sectionType: string;
  title: string;
  content: string;
  confidence: number;
}> {
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const temperature = 0.1 + attempt * 0.2; // Escalate: 0.1, 0.3, 0.5
      const prompt = getReportAgentPrompt(agentType, variables);

      const response = await callLlm(
        apiKey,
        "You are an expert data analyst. Generate a professional report section.\n" +
        "CRITICAL: Your response MUST be valid JSON. Confidence score 0.0-1.0.",
        prompt,
        undefined,
        temperature
      );

      const result = parseJsonResponse<{
        title: string;
        content: string;
        confidence: number;
        keyFindings?: string[];
      }>(response.content);

      const confidence = Math.max(0, Math.min(1, result.confidence || 0.5));

      // CONFIDENCE GATE: >= 0.65 threshold
      if (confidence >= CONFIDENCE_THRESHOLD) {
        return {
          sectionType: agentType,
          title: result.title || defaultTitle(agentType),
          content: result.content || "Analysis in progress.",
          confidence,
        };
      }

      console.warn(
        `Sub-agent ${agentType} confidence ${confidence} < threshold ${CONFIDENCE_THRESHOLD}, retry ${attempt + 1}/${MAX_RETRIES}`
      );
    } catch (e) {
      console.warn(`Sub-agent ${agentType} attempt ${attempt + 1} failed:`, e);
    }
  }

  // Deterministic fallback after 3 retries
  console.warn(`Sub-agent ${agentType} failed after ${MAX_RETRIES} retries, using fallback`);
  return generateFallbackSection(agentType, dataProfile, udm);
}

function defaultTitle(agentType: string): string {
  return agentType
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ===== FALLBACK SECTIONS =====

function generateFallbackSection(
  agentType: string,
  dataProfile: string,
  udm: any
): {
  sectionType: string;
  title: string;
  content: string;
  confidence: number;
} {
  const profile = JSON.parse(dataProfile);
  const colCount = profile.columnCount || 0;
  const rowCount = profile.rowCount || 0;

  const titles: Record<string, string> = {
    business_understanding: "Business Context",
    data_collection: "Data Profiling",
    cleaning_analysis: "Data Quality",
    eda: "EDA",
    statistical_analysis: "Statistical Analysis",
    dashboard_viz: "Visualization",
    insights: "Insights",
    recommendations: "Recommendations",
  };

  const contents: Record<string, string> = {
    business_understanding: `## Business Context\n\nThis dataset contains **${colCount} columns** and approximately **${rowCount} rows**. The analysis covers key metrics and relationships that provide actionable business insights.\n\n**Key KPIs:** Derived from the numeric columns available in the dataset.`,
    data_collection: `## Data Profiling\n\nThe dataset comprises **${rowCount} records** across **${colCount} variables**.`,
    cleaning_analysis: `## Data Quality\n\nOverall data quality assessment based on available metrics.`,
    eda: `## EDA\n\nAnalysis reveals distribution patterns and relationships worth investigating further.`,
    statistical_analysis: `## Statistical Analysis\n\nDescriptive statistics provide initial understanding of data distributions.`,
    dashboard_viz: `## Visualization\n\nSuggested dashboard layout with interactive charts for key metrics.`,
    insights: `## Insights\n\nSeveral patterns and trends identified in the data that warrant attention.`,
    recommendations: `## Recommendations\n\nBased on the analysis, here are actionable recommendations:\n1. Explore key relationships further\n2. Create visual dashboards for monitoring\n3. Derive additional metrics from existing columns`,
  };

  return {
    sectionType: agentType,
    title: titles[agentType] || "Report Section",
    content: contents[agentType] || "Analysis in progress.",
    confidence: 0.55,
  };
}

// ===== REPORT EXPORT ACTIONS =====

export const exportReport = action({
  args: {
    reportId: v.id("reports"),
    format: v.union(v.literal("html"), v.literal("markdown"), v.literal("pdf"), v.literal("excel")),
  },
  handler: async (ctx, args) => {
    const report = (await ctx.runQuery(internal.reports.getReport, { reportId: args.reportId })) as any;
    if (!report) throw new Error("Report not found");

    switch (args.format) {
      case "html": {
        const { generateHtmlExport } = await import("./lib/export_templates");
        return { content: generateHtmlExport(report), mimeType: "text/html", extension: ".html" };
      }
      case "markdown": {
        const { generateMarkdownExport } = await import("./lib/export_templates");
        return { content: generateMarkdownExport(report), mimeType: "text/markdown", extension: ".md" };
      }
      case "pdf":
        return { content: JSON.stringify(report), mimeType: "application/pdf", extension: ".pdf", note: "PDF generation requires client-side @react-pdf/renderer" };
      case "excel":
        return { content: JSON.stringify(report), mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", extension: ".xlsx", note: "Excel generation requires client-side xlsx library" };
      default:
        throw new Error("Unsupported format");
    }
  },
});

// ===== V3: ML Service Integration =====

const ML_SERVICE_URL = process.env.ML_SERVICE_URL || "http://localhost:8000";

export const runMlAnalysis = action({
  args: {
    datasetId: v.id("datasets"),
    reportId: v.id("reports"),
  },
  handler: async (ctx, args) => {
    const dataset = await ctx.runQuery(internal.datasets.getDataset, {
      datasetId: args.datasetId,
    });

    if (!dataset?.data || !Array.isArray(dataset.data) || dataset.data.length === 0) {
      return { status: "skipped", reason: "No data available" };
    }

    const data = dataset.data as Record<string, any>[];
    const numericColumns = (dataset.columns as string[]).filter((c) =>
      data.some((r) => typeof r[c] === "number")
    );

    // Only run ML if there are at least 2 numeric columns
    if (numericColumns.length < 2) {
      return { status: "skipped", reason: "Need at least 2 numeric columns" };
    }

    try {
      // Check if ML service is healthy
      const healthResponse = await fetch(`${ML_SERVICE_URL}/health`, {
        signal: AbortSignal.timeout(5000),
      });

      if (!healthResponse.ok) {
        return { status: "unavailable", reason: "ML service not reachable" };
      }

      // Send data for training + prediction
      const response = await fetch(`${ML_SERVICE_URL}/predict-and-explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: data.slice(0, 1000) }),
        signal: AbortSignal.timeout(120000), // 2 min timeout for training
      });

      if (!response.ok) {
        throw new Error(`ML service returned ${response.status}`);
      }

      const result = await response.json();

      // Add ML insights as a new report section
      const mlSection = {
        sectionType: "ml_analysis",
        title: "🤖 ML-Powered Analysis",
        content: generateMlContent(result, numericColumns),
        confidence: 0.85,
      };

      const existingSections = await ctx.runQuery(internal.reports.getReportSections, {
        reportId: args.reportId,
      });

      const updatedSections = [...(existingSections || []), mlSection];
      const overallConfidence =
        updatedSections.length > 0
          ? Math.round(
              (updatedSections.reduce((sum: number, s: any) => sum + s.confidence, 0) /
                updatedSections.length) * 10000
            ) / 10000
          : 0;

      await ctx.runMutation(internal.reports.updateReportSections, {
        reportId: args.reportId,
        sections: updatedSections,
        overallConfidence,
      });

      return {
        status: "success",
        best_model: result.best_model,
        predictions_count: result.predictions?.length || 0,
        feature_importance: result.feature_importance,
      };
    } catch (err: any) {
      console.warn("ML service error:", err.message);
      return { status: "error", reason: err.message };
    }
  },
});

function generateMlContent(result: any, columns: string[]): string {
  const importance = result.feature_importance || {};
  const sortedFeatures = Object.entries(importance)
    .sort(([, a]: any, [, b]: any) => b - a)
    .slice(0, 5);

  let content = `## Automated ML Analysis\n\n`;
  content += `**Best Model:** ${result.best_model || "N/A"}\n\n`;
  content += `**Predictions Generated:** ${result.predictions_count || 0}\n\n`;

  if (sortedFeatures.length > 0) {
    content += `### Top Feature Importance\n\n`;
    content += `| Feature | Importance |\n`;
    content += `|---------|-----------|\n`;
    for (const [feature, score] of sortedFeatures) {
      content += `| ${feature} | ${(Number(score) * 100).toFixed(1)}% |\n`;
    }
    content += `\n`;
    content += `*SHAP values explain which factors most influence predictions.*\n`;
  }

  content += `\n> ⚡ Powered by PyCaret AutoML + SHAP \n`;
  return content;
}

export const getReportSections = query({
  args: { reportId: v.id("reports") },
  handler: async (ctx, args) => {
    const report = await ctx.db.get(args.reportId);
    return report?.sections || [];
  },
});

// ===== BUILD DATA PROFILE =====

function buildDataProfile(
  data: Record<string, any>[],
  columns: string[],
  udm: any
): string {
  const numericCols = columns.filter((col) =>
    data.some((row) => typeof row[col] === "number")
  );
  const categoricalCols = columns.filter(
    (col) => !numericCols.includes(col)
  );

  return JSON.stringify(
    {
      columnCount: columns.length,
      rowCount: data.length,
      numericColumns: numericCols.length,
      categoricalColumns: categoricalCols.length,
      columns: columns.map((col) => ({
        name: col,
        isNumeric: numericCols.includes(col),
      })),
      relationships: (udm.relationships || []).length,
      derivedColumns: (udm.derivedColumns || []).length,
    },
    null,
    2
  );
}

export const editReportSection = action({
  args: {
    reportId: v.id("reports"),
    sectionType: v.string(),
    editInstructions: v.string(),
    userId: v.optional(v.id("users")),
  },
  handler: async (ctx, args) => {
    const report = await ctx.runQuery(internal.reports.getReport, {
      reportId: args.reportId,
    });
    if (!report) throw new Error("Report not found");

    const section = report.sections.find((s: any) => s.sectionType === args.sectionType);
    if (!section) throw new Error("Section not found");

    const apiKey = process.env.OPENROUTER_API_KEY;
    if (!apiKey) throw new Error("OPENROUTER_API_KEY is not configured");

    const systemPrompt = 
      "You are an expert technical editor. Edit the provided report section according to the user's instructions.\n" +
      "Maintain the same Markdown format and return ONLY the edited markdown text. Do not add conversational intro/outro text.";

    const userPrompt = 
      `Original Section Content:\n${section.content}\n\nUser Instructions:\n${args.editInstructions}\n\nEdited Markdown:`;

    const response = await callLlm(apiKey, systemPrompt, userPrompt);
    const editedContent = response.content.trim();

    await ctx.runMutation(internal.reports.updateSingleReportSection, {
      reportId: args.reportId,
      sectionType: args.sectionType,
      content: editedContent,
      userId: args.userId,
      changedBy: "ai",
    });

    return { success: true, editedContent };
  },
});

export const listReportVersions = query({
  args: { reportId: v.id("reports") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("reportVersions")
      .withIndex("by_report", (q) => q.eq("reportId", args.reportId))
      .order("desc")
      .collect();
  },
});

export const revertToVersion = mutation({
  args: {
    reportId: v.id("reports"),
    versionId: v.id("reportVersions"),
    userId: v.id("users"),
  },
  handler: async (ctx, args) => {
    const report = await ctx.db.get(args.reportId);
    if (!report) throw new Error("Report not found");

    const version = await ctx.db.get(args.versionId);
    if (!version) throw new Error("Version not found");

    // Snapshot the current sections as a version so users can "undo" the revert
    await ctx.db.insert("reportVersions", {
      reportId: args.reportId,
      userId: args.userId,
      title: report.title,
      sections: report.sections,
      changedBy: "user",
      createdAt: Date.now(),
    });

    // Revert the main report sections
    await ctx.db.patch(args.reportId, {
      sections: version.sections,
    });

    return { success: true };
  },
});
