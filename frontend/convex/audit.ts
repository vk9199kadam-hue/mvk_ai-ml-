import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

// ===== AUDIT LOG MUTATION =====
// Callable from any Convex function via internal.audit.logAction

export const logAction = mutation({
  args: {
    userId: v.id("users"),
    action: v.string(),
    resourceType: v.string(),
    resourceId: v.optional(v.string()),
    details: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    await ctx.db.insert("auditLog", {
      userId: args.userId,
      action: args.action,
      resourceType: args.resourceType,
      resourceId: args.resourceId,
      details: args.details,
      timestamp: Date.now(),
    });
  },
});

export const listAuditLogs = query({
  args: {
    userId: v.optional(v.id("users")),
    resourceType: v.optional(v.string()),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    let q;

    if (args.userId) {
      q = ctx.db.query("auditLog").withIndex("by_user", (qIdx) => qIdx.eq("userId", args.userId!));
    } else if (args.resourceType) {
      q = ctx.db.query("auditLog").withIndex("by_resource", (qIdx) => qIdx.eq("resourceType", args.resourceType!));
    } else {
      q = ctx.db.query("auditLog");
    }

    return await q.order("desc").take(args.limit || 50);
  },
});
