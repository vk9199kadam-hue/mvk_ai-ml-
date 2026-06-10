import { v } from "convex/values";
import { action, mutation, query } from "../_generated/server";
import { internal as internalRaw } from "../_generated/api";
const internal = internalRaw as any;

// ===== DIRECT IMPORTS OF STAGE RUNNER FUNCTIONS =====
import { runStage1 } from "./stage1";
import { runStage2 } from "./stage2";
import { runStage3 } from "./stage3";
import { runStage4 } from "./stage4";

// ===== MAIN PIPELINE ORCHESTRATOR =====

export const runPipeline = action({
  args: {
    uploadId: v.id("uploads"),
    datasetId: v.id("datasets"),
    userId: v.id("users"),
    skipCleaning: v.optional(v.boolean()),
  },
  handler: async (ctx, args) => {
    const startTime = Date.now();

    // Create pipeline result
    const pipelineId = (await ctx.runMutation(internal.pipeline.initPipeline, {
      uploadId: args.uploadId,
      userId: args.userId,
    })) as any;

    try {
      // Get the dataset
      const dataset = await ctx.runQuery(internal.datasets.getDataset, {
        datasetId: args.datasetId,
      });
      if (!dataset || !dataset.data) throw new Error("Dataset not found");

      let data = dataset.data as Record<string, any>[];
      const columns = dataset.columns as string[];

      // Stage 1: Schema Inference (call directly — plain async function)
      const schemaResult = await runStage1(ctx, {
        data: data.slice(0, 100),
        allColumns: columns,
      });

      await ctx.runMutation(internal.pipeline.updatePipelineStage, {
        pipelineId,
        stageNum: 1,
        stageName: "Schema Inference",
        result: schemaResult,
      });

      // Stage 2: Data Cleaning (skip if user opted out)
      let cleaningResult;
      if (!args.skipCleaning) {
        cleaningResult = await runStage2(ctx, {
          data,
          schema: schemaResult,
        });

        // *** PROPAGATE CLEANED DATA TO DOWNSTREAM STAGES ***
        if (cleaningResult.cleanedData && cleaningResult.cleanedData.length > 0) {
          data = cleaningResult.cleanedData;
        }
      } else {
        // User skipped cleaning — use original data as-is
        cleaningResult = { skipped: true, cleanedData: data, qualityProfile: {}, cleaningPlan: {}, rowCountBefore: data.length, rowCountAfter: data.length };
      }

      await ctx.runMutation(internal.pipeline.updatePipelineStage, {
        pipelineId,
        stageNum: 2,
        stageName: args.skipCleaning ? "Data Cleaning (skipped)" : "Data Cleaning",
        result: cleaningResult,
      });

      // Stage 3: LangGraph Relationship Discovery (call directly)
      const langGraphResult = await runStage3(ctx, {
        data,
        columns,
        schema: schemaResult,
      });

      await ctx.runMutation(internal.pipeline.updatePipelineStage, {
        pipelineId,
        stageNum: 3,
        stageName: "LangGraph Agent",
        result: langGraphResult,
      });

      // Stage 4: Column Engineering — fully deterministic (call directly)
      const columnEngineResult = await runStage4(ctx, {
        data,
        relationships: langGraphResult.relationships || [],
        derivedColumns: langGraphResult.derivedColumns || [],
      });

      // Build final UnifiedDataModel
      const unifiedDataModel = {
        originalColumns: columns,
        cleanedColumns: columns,
        derivedColumns: columnEngineResult.derivedColumns || [],
        relationships: langGraphResult.relationships || [],
        transformationAudit: [
          { step: "pipeline", column: "all", description: "Pipeline completed", status: "completed" },
        ],
        finalVizSchema: columnEngineResult.vizSchema || {},
        recommendedDashboardLayout: columnEngineResult.dashboardLayout || {},
      };

      // Save pipeline result
      const processingTimeMs = Date.now() - startTime;
      await ctx.runMutation(internal.pipeline.completePipeline, {
        pipelineId,
        unifiedDataModel,
        processingTimeMs,
      });

      // Update upload status
      await ctx.runMutation(internal.uploads.updateUploadStatus, {
        uploadId: args.uploadId,
        status: "completed",
        rowCount: data.length,
        columnCount: columns.length,
      });

      return {
        pipelineId,
        status: "completed",
        unifiedDataModel,
        processingTimeMs,
      };
    } catch (error: any) {
      await ctx.runMutation(internal.pipeline.failPipeline, {
        pipelineId,
        error: error.message,
      });
      await ctx.runMutation(internal.uploads.updateUploadStatus, {
        uploadId: args.uploadId,
        status: "failed",
        error: error.message,
      });
      return { pipelineId, status: "failed", error: error.message };
    }
  },
});

// ===== MUTATIONS =====

export const initPipeline = mutation({
  args: {
    uploadId: v.id("uploads"),
    userId: v.id("users"),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("pipelineResults", {
      uploadId: args.uploadId,
      userId: args.userId,
      status: "running",
      createdAt: Date.now(),
    });
  },
});

export const updatePipelineStage = mutation({
  args: {
    pipelineId: v.id("pipelineResults"),
    stageNum: v.number(),
    stageName: v.string(),
    result: v.any(),
  },
  handler: async (ctx, args) => {
    const current = await ctx.db.get(args.pipelineId);
    if (!current) throw new Error("Pipeline not found");

    const patch: Record<string, any> = {};
    if (args.stageNum === 1) patch.schemaInference = args.result;
    if (args.stageNum === 2) patch.cleaningPlan = args.result;
    if (args.stageNum === 3 || args.stageNum === 4) {
      const existing = current.unifiedDataModel || {};
      patch.unifiedDataModel = {
        ...existing,
        ...(args.stageNum === 3 ? { relationships: args.result } : {}),
        ...(args.stageNum === 4 ? { derivedColumns: args.result } : {}),
      };
    }
    await ctx.db.patch(args.pipelineId, patch);
  },
});

export const completePipeline = mutation({
  args: {
    pipelineId: v.id("pipelineResults"),
    unifiedDataModel: v.any(),
    processingTimeMs: v.number(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.pipelineId, {
      status: "completed",
      unifiedDataModel: args.unifiedDataModel,
      processingTimeMs: args.processingTimeMs,
    });
  },
});

export const failPipeline = mutation({
  args: {
    pipelineId: v.id("pipelineResults"),
    error: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.pipelineId, {
      status: "failed",
      error: args.error,
    });
  },
});

export const getPipelineResult = query({
  args: { pipelineId: v.id("pipelineResults") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.pipelineId);
  },
});

export const listPipelineResults = query({
  args: { userId: v.id("users") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("pipelineResults")
      .filter((q) => q.eq(q.field("userId"), args.userId))
      .order("desc")
      .collect();
  },
});
