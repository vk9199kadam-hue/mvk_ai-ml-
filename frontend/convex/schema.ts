import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  // ===== Users & Authentication =====
  users: defineTable({
    email: v.string(),
    name: v.string(),
    passwordHash: v.string(),
    role: v.union(
      v.literal("admin"),
      v.literal("analyst"),
      v.literal("viewer")
    ),
    createdAt: v.number(),
    lastLogin: v.optional(v.number()),
  }).index("by_email", ["email"]),

  // ===== File Uploads =====
  uploads: defineTable({
    userId: v.id("users"),
    fileName: v.string(),
    fileSize: v.number(),
    fileStorageId: v.optional(v.string()),
    status: v.union(
      v.literal("pending"),
      v.literal("uploading"),
      v.literal("processing"),
      v.literal("completed"),
      v.literal("failed")
    ),
    rowCount: v.optional(v.number()),
    columnCount: v.optional(v.number()),
    createdAt: v.number(),
    completedAt: v.optional(v.number()),
  }).index("by_user", ["userId"]),

  // ===== Pipeline Results =====
  pipelineResults: defineTable({
    uploadId: v.id("uploads"),
    userId: v.id("users"),
    status: v.union(
      v.literal("queued"),
      v.literal("running"),
      v.literal("completed"),
      v.literal("failed")
    ),
    schemaInference: v.optional(v.any()),
    cleaningPlan: v.optional(v.any()),
    unifiedDataModel: v.optional(v.any()),
    processingTimeMs: v.optional(v.number()),
    error: v.optional(v.string()),
    createdAt: v.number(),
  }).index("by_upload", ["uploadId"]),

  // ===== Reports =====
  reports: defineTable({
    uploadId: v.id("uploads"),
    userId: v.id("users"),
    title: v.string(),
    sections: v.array(v.object({
      sectionType: v.string(),
      title: v.string(),
      content: v.string(),
      confidence: v.number(),
    })),
    overallConfidence: v.number(),
    exportFormats: v.optional(v.array(v.string())),
    createdAt: v.number(),
  }).index("by_user", ["userId"]),

  // ===== Dashboards =====
  dashboards: defineTable({
    uploadId: v.id("uploads"),
    userId: v.id("users"),
    title: v.string(),
    layout: v.array(v.object({
      i: v.string(),
      x: v.number(),
      y: v.number(),
      w: v.number(),
      h: v.number(),
    })),
    widgets: v.any(),
    createdAt: v.number(),
  }).index("by_user", ["userId"]),

  // ===== NLQ Chat Conversations =====
  conversations: defineTable({
    userId: v.id("users"),
    uploadId: v.id("uploads"),
    messages: v.array(v.object({
      role: v.union(v.literal("user"), v.literal("assistant")),
      content: v.string(),
      sqlGenerated: v.optional(v.string()),
      chartConfig: v.optional(v.any()),
      timestamp: v.number(),
    })),
    createdAt: v.number(),
    updatedAt: v.number(),
  }).index("by_user_upload", ["userId", "uploadId"]),

  // ===== Raw Data Storage =====
  datasets: defineTable({
    uploadId: v.id("uploads"),
    userId: v.id("users"),
    columns: v.array(v.string()),
    rowCount: v.number(),
    data: v.any(),
    createdAt: v.number(),
  }).index("by_upload", ["uploadId"]),

  // ===== Audit Log (Enterprise Compliance) =====
  auditLog: defineTable({
    userId: v.id("users"),
    action: v.string(),
    resourceType: v.string(),
    resourceId: v.optional(v.string()),
    details: v.optional(v.any()),
    ip: v.optional(v.string()),
    timestamp: v.number(),
  }).index("by_user", ["userId"])
    .index("by_resource", ["resourceType", "resourceId"])
    .index("by_timestamp", ["timestamp"]),

  // ===== Prompt Templates (Versioned) =====
  prompts: defineTable({
    name: v.string(),
    version: v.number(),
    template: v.string(),
    provider: v.string(),
    createdAt: v.number(),
  }).index("by_name", ["name"]),

  // ===== V4: Dataset Relationships for Multi-Dataset Joins =====
  datasetRelations: defineTable({
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
    createdAt: v.number(),
  }).index("by_user", ["userId"]),

  // ===== V4: Joined Dataset Cache =====
  joinedDatasets: defineTable({
    userId: v.id("users"),
    relationId: v.id("datasetRelations"),
    columns: v.array(v.string()),
    rowCount: v.number(),
    data: v.any(),
    createdAt: v.number(),
  }).index("by_user", ["userId"])
    .index("by_relation", ["relationId"]),

  // ===== V5: Scheduled Email Reports =====
  scheduledReports: defineTable({
    userId: v.id("users"),
    reportId: v.id("reports"),
    email: v.string(),
    frequency: v.union(
      v.literal("daily"),
      v.literal("weekly"),
      v.literal("monthly")
    ),
    nextSend: v.number(),
    lastSent: v.optional(v.number()),
    createdAt: v.number(),
  }).index("by_user", ["userId"]),

  // ===== V5: Report Version History =====
  reportVersions: defineTable({
    reportId: v.id("reports"),
    userId: v.id("users"),
    title: v.string(),
    sections: v.array(
      v.object({
        sectionType: v.string(),
        title: v.string(),
        content: v.string(),
        confidence: v.number(),
      })
    ),
    changedBy: v.union(v.literal("user"), v.literal("ai")),
    createdAt: v.number(),
  }).index("by_report", ["reportId"]),
});
