import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

// ===== QUERIES =====

export const getDataset = query({
  args: { datasetId: v.id("datasets") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.datasetId);
  },
});

export const getDatasetByUpload = query({
  args: { uploadId: v.id("uploads") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("datasets")
      .withIndex("by_upload", (q) => q.eq("uploadId", args.uploadId))
      .first();
  },
});

export const listDatasets = query({
  args: { userId: v.id("users") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("datasets")
      .filter((q) => q.eq(q.field("userId"), args.userId))
      .collect();
  },
});

// ===== MUTATIONS =====

export const storeDataset = mutation({
  args: {
    uploadId: v.id("uploads"),
    userId: v.id("users"),
    columns: v.array(v.string()),
    rowCount: v.number(),
    data: v.any(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("datasets")
      .withIndex("by_upload", (q) => q.eq("uploadId", args.uploadId))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        columns: args.columns,
        rowCount: args.rowCount,
        data: args.data,
        createdAt: Date.now(),
      });
      return { datasetId: existing._id };
    }

    const datasetId = await ctx.db.insert("datasets", {
      uploadId: args.uploadId,
      userId: args.userId,
      columns: args.columns,
      rowCount: args.rowCount,
      data: args.data,
      createdAt: Date.now(),
    });
    return { datasetId };
  },
});

export const deleteDataset = mutation({
  args: { datasetId: v.id("datasets") },
  handler: async (ctx, args) => {
    await ctx.db.delete(args.datasetId);
  },
});
