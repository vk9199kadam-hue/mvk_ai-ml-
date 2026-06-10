"use client";

import React, { useState } from "react";
import toast from "react-hot-toast";
import { useMutation } from "convex/react";
import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";

// PDF Export — uses @react-pdf/renderer
// Excel Export — uses xlsx library
// Both libraries are installed as dependencies

interface ReportExportProps {
  reportId: string;
  reportTitle: string;
  sections: Array<{
    title: string;
    content: string;
    confidence: number;
  }>;
  overallConfidence: number;
  createdAt: number;
}

export default function ReportExport({
  reportId,
  reportTitle,
  sections,
  overallConfidence,
  createdAt,
}: ReportExportProps) {
  const [exporting, setExporting] = useState<string | null>(null);
  const createScheduledReport = useMutation(api.scheduled_reports.createScheduledReport);

  // ── HTML Export ─────────────────────────────────────────────────────
  const handleHtmlExport = async () => {
    setExporting("html");
    try {
      const html = generateClientHtml(reportTitle, sections, overallConfidence, createdAt);
      downloadFile(html, `${reportTitle.replace(/[^a-zA-Z0-9]/g, "_")}.html`, "text/html");
      toast.success("HTML report downloaded!");
    } catch (err: any) {
      toast.error(err?.message || "Export failed");
    } finally {
      setExporting(null);
    }
  };

  // ── Markdown Export ─────────────────────────────────────────────────
  const handleMarkdownExport = async () => {
    setExporting("markdown");
    try {
      let md = `# ${reportTitle}\n\n`;
      md += `> **Overall Confidence:** ${Math.round(overallConfidence * 100)}%\n`;
      md += `> **Generated:** ${new Date(createdAt).toLocaleString()}\n\n`;
      md += "---\n\n";
      for (const section of sections) {
        md += `## ${section.title}\n\n`;
        md += `> Confidence: ${Math.round(section.confidence * 100)}%\n\n`;
        md += `${section.content}\n\n---\n\n`;
      }
      downloadFile(md, `${reportTitle.replace(/[^a-zA-Z0-9]/g, "_")}.md`, "text/markdown");
      toast.success("Markdown report downloaded!");
    } catch (err: any) {
      toast.error(err?.message || "Export failed");
    } finally {
      setExporting(null);
    }
  };

  // ── PDF Export (client-side with @react-pdf/renderer) ───────────────
  const handlePdfExport = async () => {
    setExporting("pdf");
    try {
      const { pdf, Document, Page, Text, View, StyleSheet } = await import("@react-pdf/renderer");

      const styles = StyleSheet.create({
        page: { padding: 40, fontFamily: "Helvetica" },
        title: { fontSize: 24, marginBottom: 10, fontWeight: "bold" },
        meta: { fontSize: 10, color: "#666", marginBottom: 20 },
        sectionTitle: { fontSize: 16, marginTop: 15, marginBottom: 8, fontWeight: "bold" },
        sectionContent: { fontSize: 11, lineHeight: 1.6, marginBottom: 10 },
        confidence: { fontSize: 9, color: "#888", marginBottom: 15 },
        separator: { borderBottomWidth: 1, borderBottomColor: "#ddd", marginVertical: 10 },
      });

      const PdfDocument = (
        <Document>
          <Page size="A4" style={styles.page}>
            <Text style={styles.title}>{reportTitle}</Text>
            <Text style={styles.meta}>
              Confidence: {Math.round(overallConfidence * 100)}% | Generated: {new Date(createdAt).toLocaleString()}
            </Text>
            <View style={styles.separator} />
            {sections.map((section, i) => (
              <View key={i} wrap={false}>
                <Text style={styles.sectionTitle}>{section.title}</Text>
                <Text style={styles.confidence}>Confidence: {Math.round(section.confidence * 100)}%</Text>
                <Text style={styles.sectionContent}>{stripMarkdown(section.content)}</Text>
              </View>
            ))}
          </Page>
        </Document>
      );

      const blob = await pdf(PdfDocument).toBlob();
      downloadFile(blob, `${reportTitle.replace(/[^a-zA-Z0-9]/g, "_")}.pdf`, "application/pdf");
      toast.success("PDF report downloaded!");
    } catch (err: any) {
      console.warn("PDF export error:", err);
      toast.error("PDF export requires client-side rendering. Try HTML or Markdown instead.");
    } finally {
      setExporting(null);
    }
  };

  // ── Excel Export (client-side with xlsx) ────────────────────────────
  const handleExcelExport = async () => {
    setExporting("excel");
    try {
      const XLSX = await import("xlsx");

      // Create workbook with multiple sheets
      const wb = XLSX.utils.book_new();

      // Sheet 1: Overview
      const overviewData = [
        ["Field", "Value"],
        ["Report Title", reportTitle],
        ["Overall Confidence", `${Math.round(overallConfidence * 100)}%`],
        ["Sections", sections.length],
        ["Generated", new Date(createdAt).toLocaleString()],
      ];
      const ws1 = XLSX.utils.aoa_to_sheet(overviewData);
      XLSX.utils.book_append_sheet(wb, ws1, "Overview");

      // Sheet 2: Sections
      const sectionData = [
        ["Section", "Title", "Confidence (%)", "Content"],
        ...sections.map((s, i) => [
          `Section ${i + 1}`,
          s.title,
          Math.round(s.confidence * 100),
          stripMarkdown(s.content).slice(0, 32767),
        ]),
      ];
      const ws2 = XLSX.utils.aoa_to_sheet(sectionData);
      XLSX.utils.book_append_sheet(wb, ws2, "Sections");

      // Write and download
      const wbout = XLSX.write(wb, { bookType: "xlsx", type: "array" });
      downloadFile(
        new Blob([wbout], { type: "application/octet-stream" }),
        `${reportTitle.replace(/[^a-zA-Z0-9]/g, "_")}.xlsx`,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      );
      toast.success("Excel report downloaded!");
    } catch (err: any) {
      console.warn("Excel export error:", err);
      toast.error("Excel export error. Try a different format.");
    } finally {
      setExporting(null);
    }
  };

  // ── Email Scheduling ────────────────────────────────────────────────
  const [showSchedule, setShowSchedule] = useState(false);
  const [scheduleEmail, setScheduleEmail] = useState("");
  const [scheduleFreq, setScheduleFreq] = useState<"daily" | "weekly" | "monthly">("weekly");
  const [scheduling, setScheduling] = useState(false);

  const handleScheduleReport = async () => {
    if (!scheduleEmail) { toast.error("Please enter an email address"); return; }
    setScheduling(true);
    try {
      // Get user ID from localStorage
      const storedUser = localStorage.getItem("user");
      if (!storedUser) throw new Error("Must be logged in to schedule reports");
      const user = JSON.parse(storedUser);
      const userId = user._id as Id<"users">;

      await createScheduledReport({
        userId,
        reportId: reportId as Id<"reports">,
        email: scheduleEmail,
        frequency: scheduleFreq,
      });

      toast.success(`Report scheduled! Will send ${scheduleFreq} to ${scheduleEmail}`);
      setShowSchedule(false);
      setScheduleEmail("");
    } catch (err: any) {
      toast.error(err?.message || "Scheduling failed");
    } finally {
      setScheduling(false);
    }
  };

  // ── Helpers ─────────────────────────────────────────────────────────
  function downloadFile(content: Blob | string, filename: string, mimeType: string) {
    const blob = typeof content === "string" ? new Blob([content], { type: mimeType }) : content;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function stripMarkdown(md: string): string {
    return md
      .replace(/#{1,6}\s/g, "")
      .replace(/\*\*(.+?)\*\*/g, "$1")
      .replace(/\*(.+?)\*/g, "$1")
      .replace(/`(.+?)`/g, "$1")
      .replace(/\[(.+?)\]\(.+?\)/g, "$1")
      .replace(/>{1}\s/g, "")
      .replace(/[-*]{3,}/g, "")
      .replace(/\n{3,}/g, "\n\n");
  }

  function generateClientHtml(title: string, sections: any[], confidence: number, created: number): string {
    return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>${escapeHtml(title)} — AutoInsight Report</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1f2937;background:#f9fafb;line-height:1.6;padding:40px;max-width:900px;margin:0 auto}
header{background:linear-gradient(135deg,#2563eb,#7c3aed);color:white;padding:40px;border-radius:16px;margin-bottom:32px}
header h1{font-size:28px;margin:0 0 8px 0}
.section{background:white;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,0.08)}
.section h2{margin:0 0 8px 0;color:#111827}
.badge{display:inline-block;padding:4px 12px;border-radius:12px;font-size:12px;margin-bottom:12px}
.high{border:1px solid #d1fae5;color:#065f46}
.med{border:1px solid #fef3c7;color:#92400e}
.low{border:1px solid #fee2e2;color:#991b1b}
.content p{margin:0 0 12px 0}
footer{text-align:center;color:#9ca3af;font-size:13px;padding:32px 0}
</style></head><body>
<header><h1>${escapeHtml(title)}</h1><p>Generated: ${new Date(created).toLocaleDateString()} | ${sections.length} sections | Confidence: ${Math.round(confidence * 100)}%</p></header>
${sections.map((s: any) => {
  const cls = s.confidence >= 0.7 ? "high" : s.confidence >= 0.5 ? "med" : "low";
  return `<div class="section"><h2>${escapeHtml(s.title)}</h2><div class="badge ${cls}">${Math.round(s.confidence * 100)}% Confidence</div><div class="content"><p>${escapeHtml(s.content || "").replace(/\n/g, "</p><p>")}</p></div></div>`;
}).join("\n")}
<footer><p>AutoInsight AI — AI-Powered Data Analysis Platform</p></footer>
</body></html>`;
  }

  function escapeHtml(text: string): string {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  const isExporting = exporting !== null;

  return (
    <div className="space-y-3">
      <h3 className="font-semibold text-gray-900 mb-2">Export Report</h3>
      <div className="grid grid-cols-2 gap-3">
        <button onClick={handleHtmlExport} disabled={isExporting} className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700 disabled:opacity-50">
          <span className="text-orange-500">🌐</span> HTML {exporting === "html" && "..."}
        </button>
        <button onClick={handleMarkdownExport} disabled={isExporting} className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700 disabled:opacity-50">
          <span className="text-blue-500">📝</span> Markdown {exporting === "markdown" && "..."}
        </button>
        <button onClick={handlePdfExport} disabled={isExporting} className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700 disabled:opacity-50">
          <span className="text-red-500">📄</span> PDF {exporting === "pdf" && "..."}
        </button>
        <button onClick={handleExcelExport} disabled={isExporting} className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-sm font-medium text-gray-700 disabled:opacity-50">
          <span className="text-green-500">📊</span> Excel {exporting === "excel" && "..."}
        </button>
      </div>
      <p className="text-xs text-gray-400 mt-2">
        Exports are generated in your browser. Large reports may take a moment.
      </p>

      {/* Schedule Button */}
      <button
        onClick={() => setShowSchedule(!showSchedule)}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-lg hover:from-blue-600 hover:to-purple-600 text-sm font-medium transition-all"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        📅 Schedule Email Delivery
      </button>

      {/* Schedule Form */}
      {showSchedule && (
        <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
          <h4 className="text-sm font-medium text-gray-900">Schedule Report</h4>
          <div>
            <label className="text-xs text-gray-500">Email Address</label>
            <input
              type="email"
              value={scheduleEmail}
              onChange={(e) => setScheduleEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full input-field text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500">Frequency</label>
            <select
              value={scheduleFreq}
              onChange={(e) => setScheduleFreq(e.target.value as any)}
              className="w-full input-field text-sm mt-1"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <button
            onClick={handleScheduleReport}
            disabled={scheduling}
            className="w-full btn-primary text-sm py-2 disabled:opacity-50"
          >
            {scheduling ? "Scheduling..." : "📅 Schedule"}
          </button>
        </div>
      )}
    </div>
  );
}
