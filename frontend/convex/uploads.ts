import { v } from "convex/values";
import { mutation, query } from "./_generated/server";
import { internal } from "./_generated/api";

// ===== QUERIES =====

export const getUpload = query({
  args: { uploadId: v.id("uploads") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.uploadId);
  },
});

export const listUploads = query({
  args: { userId: v.id("users") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("uploads")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .order("desc")
      .collect();
  },
});

// ===== MUTATIONS =====

export const initiateUpload = mutation({
  args: {
    userId: v.id("users"),
    fileName: v.string(),
    fileSize: v.number(),
  },
  handler: async (ctx, args) => {
    const uploadId = await ctx.db.insert("uploads", {
      userId: args.userId,
      fileName: args.fileName,
      fileSize: args.fileSize,
      status: "pending",
      createdAt: Date.now(),
    });
    return { uploadId };
  },
});

export const updateUploadStatus = mutation({
  args: {
    uploadId: v.id("uploads"),
    status: v.union(
      v.literal("pending"),
      v.literal("uploading"),
      v.literal("processing"),
      v.literal("completed"),
      v.literal("failed")
    ),
    fileStorageId: v.optional(v.string()),
    rowCount: v.optional(v.number()),
    columnCount: v.optional(v.number()),
    error: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const patch: Record<string, any> = { status: args.status };
    if (args.fileStorageId) patch.fileStorageId = args.fileStorageId;
    if (args.rowCount !== undefined) patch.rowCount = args.rowCount;
    if (args.columnCount !== undefined) patch.columnCount = args.columnCount;
    if (args.error) patch.error = args.error;
    if (args.status === "completed") patch.completedAt = Date.now();
    await ctx.db.patch(args.uploadId, patch);
  },
});

// ===== UPLOAD URL (mutation returns a string) =====

export const generateUploadUrl = mutation({
  args: {},
  handler: async (ctx) => {
    return await ctx.storage.generateUploadUrl();
  },
});
