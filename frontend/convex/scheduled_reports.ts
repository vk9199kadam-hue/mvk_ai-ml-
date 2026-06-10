import { v } from "convex/values";
import { mutation, query, action } from "./_generated/server";
import { internal as internalRaw } from "./_generated/api";
const internal = internalRaw as any;
import { Resend } from "resend";

export const createScheduledReport = mutation({
  args: {
    userId: v.id("users"),
    reportId: v.id("reports"),
    email: v.string(),
    frequency: v.union(
      v.literal("daily"),
      v.literal("weekly"),
      v.literal("monthly")
    ),
  },
  handler: async (ctx, args) => {
    const nextSend = Date.now() + (
      args.frequency === "daily" ? 86400000 : 
      args.frequency === "weekly" ? 604800000 : 
      2592000000
    );

    return await ctx.db.insert("scheduledReports", {
      userId: args.userId,
      reportId: args.reportId,
      email: args.email,
      frequency: args.frequency,
      nextSend,
      createdAt: Date.now(),
    });
  },
});

export const listScheduledReports = query({
  args: { userId: v.id("users") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("scheduledReports")
      .withIndex("by_user", (q) => q.eq("userId", args.userId))
      .order("desc")
      .collect();
  },
});

export const listSchedulesForReport = query({
  args: { reportId: v.id("reports") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("scheduledReports")
      .filter((q) => q.eq(q.field("reportId"), args.reportId))
      .order("desc")
      .collect();
  },
});

export const deleteScheduledReport = mutation({
  args: { scheduledId: v.id("scheduledReports") },
  handler: async (ctx, args) => {
    await ctx.db.delete(args.scheduledId);
  },
});

// ===== INTERNAL QUERIES & MUTATIONS =====

export const getScheduledReportRecord = query({
  args: { scheduledId: v.id("scheduledReports") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.scheduledId);
  },
});

export const updateScheduledReportSent = mutation({
  args: {
    scheduledId: v.id("scheduledReports"),
    lastSent: v.number(),
    nextSend: v.number(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.scheduledId, {
      lastSent: args.lastSent,
      nextSend: args.nextSend,
    });
  },
});

// ===== ACTION: SEND SCHEDULED REPORT (RESEND) =====

export const sendScheduledReport = action({
  args: { scheduledId: v.id("scheduledReports") },
  handler: async (ctx, args) => {
    const scheduled = await ctx.runQuery(
      internal.scheduled_reports.getScheduledReportRecord,
      { scheduledId: args.scheduledId }
    );
    if (!scheduled) throw new Error("Scheduled report not found");

    const report = await ctx.runQuery(internal.reports.getReport, {
      reportId: scheduled.reportId,
    });
    if (!report) throw new Error("Report not found");

    // Generate HTML export content using the report template
    const { generateHtmlExport } = await import("./lib/export_templates");
    const htmlBody = generateHtmlExport(report as any);

    const resendApiKey = process.env.RESEND_API_KEY;
    
    // We send to the email specified in scheduled.email.
    // In production Resend requires a verified domain unless sending to the account owner.
    // Resend's free tier allows sending to the owner's email.
    if (resendApiKey) {
      const resend = new Resend(resendApiKey);
      await resend.emails.send({
        from: "AutoInsight AI <onboarding@resend.dev>",
        to: [scheduled.email],
        subject: `📊 Scheduled Report: ${report.title}`,
        html: htmlBody,
      });
      console.log(`Successfully sent email via Resend to ${scheduled.email}`);
    } else {
      console.warn("RESEND_API_KEY is not set. Simulating scheduled email send (mock mode).");
    }

    const lastSent = Date.now();
    const nextSend =
      lastSent +
      (scheduled.frequency === "daily"
        ? 86400000
        : scheduled.frequency === "weekly"
          ? 604800000
          : 2592000000);

    await ctx.runMutation(internal.scheduled_reports.updateScheduledReportSent, {
      scheduledId: args.scheduledId,
      lastSent,
      nextSend,
    });

    return { success: true, emailSentTo: scheduled.email };
  },
});
