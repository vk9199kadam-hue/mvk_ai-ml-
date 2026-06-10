import { v } from "convex/values";
import { action, mutation, query } from "./_generated/server";
import { internal as internalRaw } from "./_generated/api";
const internal = internalRaw as any;

// ===== QUERIES =====

export const getRelation = query({
  args: { relationId: v.id("datasetRelations") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.relationId);
  },
});

export const listRelations = query({
  args: { userId: v.id("users") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("datasetRelations")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .order("desc")
      .collect();
  },
});

export const getJoinedDataset = query({
  args: { relationId: v.id("datasetRelations") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("joinedDatasets")
      .withIndex("by_relation", (q) => q.eq("relationId", args.relationId))
      .first();
  },
});

export const listJoinedDatasets = query({
  args: { userId: v.id("users") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("joinedDatasets")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .collect();
  },
});

// ===== MUTATIONS =====

export const createRelation = mutation({
  args: {
    userId: v.id("users"),
    name: v.string(),
    description: v.optional(v.string()),
    sourceUploadId: v.id("uploads"),
    targetUploadId: v.id("uploads"),
    sourceColumn: v.string(),
    targetColumn: v.string(),
    joinType: v.union(
      v.literal("inner"),
      v.literal("left"),
      v.literal("right"),
      v.literal("outer")
    ),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("datasetRelations", {
      userId: args.userId,
      name: args.name,
      description: args.description,
      sourceUploadId: args.sourceUploadId,
      targetUploadId: args.targetUploadId,
      sourceColumn: args.sourceColumn,
      targetColumn: args.targetColumn,
      joinType: args.joinType,
      createdAt: Date.now(),
    });
  },
});

export const deleteRelation = mutation({
  args: { relationId: v.id("datasetRelations") },
  handler: async (ctx, args) => {
    // Also delete any cached joined datasets
    const cached = await ctx.db
      .query("joinedDatasets")
      .withIndex("by_relation", (q) => q.eq("relationId", args.relationId))
      .first();
    if (cached) {
      await ctx.db.delete(cached._id);
    }
    await ctx.db.delete(args.relationId);
  },
});

// ===== JOIN ENGINE ACTION =====

export const executeJoin = action({
  args: {
    relationId: v.id("datasetRelations"),
    userId: v.id("users"),
  },
  handler: async (ctx, args) => {
    const relation = (await ctx.runQuery(internal.joins.getRelation, {
      relationId: args.relationId,
    })) as any;
    if (!relation) throw new Error("Relation not found");

    // Get both datasets
    const sourceDataset = await ctx.runQuery(internal.datasets.getDatasetByUpload, {
      uploadId: relation.sourceUploadId,
    });
    const targetDataset = await ctx.runQuery(internal.datasets.getDatasetByUpload, {
      uploadId: relation.targetUploadId,
    });

    if (!sourceDataset?.data || !targetDataset?.data) {
      throw new Error("One or both datasets not found");
    }

    const sourceData = sourceDataset.data as Record<string, any>[];
    const targetData = targetDataset.data as Record<string, any>[];
    const sourceCol = relation.sourceColumn;
    const targetCol = relation.targetColumn;
    const joinType = relation.joinType;

    // Build lookup index for target dataset
    const targetIndex = new Map<string, Record<string, any>[]>();
    for (const row of targetData) {
      const key = String(row[targetCol] ?? "");
      if (!targetIndex.has(key)) targetIndex.set(key, []);
      targetIndex.get(key)!.push(row);
    }

    // Determine output columns
    const sourceColumns = sourceDataset.columns as string[];
    const targetColumns = targetDataset.columns as string[];
    // Prefix target columns to avoid collisions (except the join column)
    const joinedColumns = [
      ...sourceColumns.map((c) => (c === sourceCol ? c : `source_${c}`)),
      ...targetColumns
        .filter((c) => c !== targetCol)
        .map((c) => `target_${c}`),
    ];

    const joinedData: Record<string, any>[] = [];
    const matchedKeys = new Set<string>();

    for (const sourceRow of sourceData) {
      const key = String(sourceRow[sourceCol] ?? "");
      const matches = targetIndex.get(key) || [];

      if (matches.length > 0) {
        matchedKeys.add(key);
        for (const match of matches) {
          const joinedRow: Record<string, any> = {};
          // Source columns
          for (const col of sourceColumns) {
            joinedRow[col === sourceCol ? col : `source_${col}`] = sourceRow[col];
          }
          // Target columns (skip the join key to avoid dup)
          for (const col of targetColumns) {
            if (col !== targetCol) {
              joinedRow[`target_${col}`] = match[col];
            }
          }
          joinedData.push(joinedRow);
        }
      } else if (joinType === "left" || joinType === "outer") {
        // Left join: include source row with null targets
        const joinedRow: Record<string, any> = {};
        for (const col of sourceColumns) {
          joinedRow[col === sourceCol ? col : `source_${col}`] = sourceRow[col];
        }
        for (const col of targetColumns) {
          if (col !== targetCol) {
            joinedRow[`target_${col}`] = null;
          }
        }
        joinedData.push(joinedRow);
      }
    }

    // Right / Outer join: include unmatched target rows
    if (joinType === "right" || joinType === "outer") {
      for (const targetRow of targetData) {
        const key = String(targetRow[targetCol] ?? "");
        if (!matchedKeys.has(key)) {
          const joinedRow: Record<string, any> = {};
          for (const col of sourceColumns) {
            joinedRow[col === sourceCol ? col : `source_${col}`] = null;
          }
          for (const col of targetColumns) {
            joinedRow[col === targetCol ? col : `target_${col}`] = targetRow[col];
          }
          joinedData.push(joinedRow);
        }
      }
    }

    // Cache the joined dataset
    const existing = await ctx.runQuery(internal.joins.getJoinedDataset, {
      relationId: args.relationId,
    });

    if (existing) {
      await ctx.runMutation(internal.joins.updateJoinedDataset, {
        joinedId: existing._id,
        columns: joinedColumns,
        rowCount: joinedData.length,
        data: joinedData,
      });
    } else {
      await ctx.runMutation(internal.joins.storeJoinedDataset, {
        relationId: args.relationId,
        userId: args.userId,
        columns: joinedColumns,
        rowCount: joinedData.length,
        data: joinedData,
      });
    }

    return {
      columns: joinedColumns,
      rowCount: joinedData.length,
      data: joinedData.slice(0, 100), // Return first 100 for preview
    };
  },
});

// ===== INTERNAL MUTATIONS =====

export const storeJoinedDataset = mutation({
  args: {
    relationId: v.id("datasetRelations"),
    userId: v.id("users"),
    columns: v.array(v.string()),
    rowCount: v.number(),
    data: v.any(),
  },
  handler: async (ctx, args) => {
    await ctx.db.insert("joinedDatasets", {
      relationId: args.relationId,
      userId: args.userId,
      columns: args.columns,
      rowCount: args.rowCount,
      data: args.data,
      createdAt: Date.now(),
    });
  },
});

export const updateJoinedDataset = mutation({
  args: {
    joinedId: v.id("joinedDatasets"),
    columns: v.array(v.string()),
    rowCount: v.number(),
    data: v.any(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.joinedId, {
      columns: args.columns,
      rowCount: args.rowCount,
      data: args.data,
      createdAt: Date.now(),
    });
  },
});
