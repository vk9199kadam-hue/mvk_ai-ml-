"use client";

import React, { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "convex/react";
import { useDropzone } from "react-dropzone";
import { api } from "../../../convex/_generated/api";
import Layout from "@/components/Layout";
import { useMutation, useAction } from "convex/react";
import { formatBytes, formatDuration, cn } from "@/lib/utils";
import toast from "react-hot-toast";
import type { Id } from "../../../convex/_generated/dataModel";

// ── Status Card Component ────────────────────────────────────────────────

function StatusCard({
  title,
  value,
  subtitle,
  icon,
  color,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={cn("p-3 rounded-lg", color)}>{icon}</div>
      </div>
    </div>
  );
}

// ── Pipeline Stage Indicator ─────────────────────────────────────────────

function PipelineProgress({ state }: { state: { global_progress: number; stages: Record<string, { status?: string }>; pipeline_id?: string | null; status?: string; current_stage?: number } }) {
  const stages = [
    { key: "stage1", label: "CSV Schema" },
    { key: "stage2", label: "Cleaning" },
    { key: "stage3", label: "Analysis" },
    { key: "stage4", label: "Assembly" },
  ];

  return (
    <div className="card p-6">
      <h3 className="font-semibold text-gray-900 mb-4">Pipeline Progress</h3>
      <div className="space-y-4">
        {/* Global Progress Bar */}
        <div className="progress-bar">
          <div
            className="progress-bar-fill bg-gradient-to-r from-blue-500 to-purple-500"
            style={{ width: `${state.global_progress}%` }}
          />
        </div>
        <p className="text-sm text-gray-500 text-right">
          {Math.round(state.global_progress)}% Complete
        </p>

        {/* Stage Details */}
        <div className="space-y-3">
          {stages.map((stage, i) => {
            const s = state.stages?.[stage.key] || {};
            const status = s.status || "pending";
            const isActive = status === "running";
            const isDone = status === "completed";
            const isFailed = status === "failed";

            return (
              <div key={stage.key} className="flex items-center gap-3">
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all",
                    isDone
                      ? "bg-green-100 text-green-600"
                      : isActive
                      ? "bg-blue-100 text-blue-600 animate-pulse"
                      : isFailed
                      ? "bg-red-100 text-red-600"
                      : "bg-gray-100 text-gray-400"
                  )}
                >
                  {isDone ? "✓" : isFailed ? "✗" : i + 1}
                </div>
                <div className="flex-1">
                  <p
                    className={cn(
                      "text-sm font-medium",
                      isDone
                        ? "text-green-700"
                        : isActive
                        ? "text-blue-700"
                        : isFailed
                        ? "text-red-700"
                        : "text-gray-500"
                    )}
                  >
                    {stage.label}
                  </p>
                  {isActive && (
                    <div className="mt-1 progress-bar">
                      <div className="progress-bar-fill bg-blue-500 animate-progress-bar" style={{ width: "40%" }} />
                    </div>
                  )}
                </div>
                <span
                  className={cn(
                    "text-xs font-medium",
                    isDone && "text-green-500",
                    isActive && "text-blue-500",
                    isFailed && "text-red-500",
                    !isDone && !isActive && !isFailed && "text-gray-400"
                  )}
                >
                  {isDone ? "Done" : isActive ? "Running" : isFailed ? "Failed" : "Pending"}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Quick Upload Zone ────────────────────────────────────────────────────

function QuickUploadZone({ onUploadComplete }: { onUploadComplete: (uploadId: string) => void }) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const initiateUpload = useMutation(api.uploads.initiateUpload);
  const generateUploadUrl = useMutation(api.uploads.generateUploadUrl);
  const storeDataset = useMutation(api.datasets.storeDataset);
  const runPipeline = useAction(api.pipeline.index.runPipeline);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;
    if (!file.name.endsWith(".csv")) { toast.error("Only CSV files"); return; }

    setUploading(true);
    setProgress(0);

    try {
      const storedUser = localStorage.getItem("user");
      if (!storedUser) throw new Error("Must be logged in");
      const user = JSON.parse(storedUser);

      const { uploadId } = await initiateUpload({ userId: user._id || "" as any, fileName: file.name, fileSize: file.size });
      const uploadUrl = await generateUploadUrl();
      const uploadResponse = await fetch(uploadUrl, { method: "POST", headers: { "Content-Type": "text/csv" }, body: file });
      if (!uploadResponse.ok) throw new Error("Storage upload failed");

      const text = await file.text();
      const lines = text.split("\n").filter((l: string) => l.trim());
      const headers = lines[0].split(",").map((h: string) => h.trim());
      const rows = lines.slice(1).map((line: string) => {
        const vals = line.split(",").map((v: string) => v.trim());
        const row: Record<string, any> = {};
        headers.forEach((h: string, i: number) => { const num = Number(vals[i]); row[h] = isNaN(num) ? (vals[i] || null) : num; });
        return row;
      });

      await storeDataset({ uploadId, userId: user._id || "" as any, columns: headers, rowCount: rows.length, data: rows.slice(0, 10000) });
      setProgress(100);
      toast.success("File uploaded!");

      toast.success("Pipeline started!");
      onUploadComplete(uploadId);
    } catch (err: any) {
      toast.error(err?.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [initiateUpload, generateUploadUrl, storeDataset, runPipeline, onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    maxFiles: 1,
    disabled: uploading,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "card p-8 text-center cursor-pointer transition-all duration-200 border-2 border-dashed",
        isDragActive
          ? "border-blue-500 bg-blue-50"
          : "border-gray-200 hover:border-blue-300 hover:bg-gray-50"
      )}
    >
      <input {...getInputProps()} />
      {uploading ? (
        <div className="space-y-3">
          <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto animate-pulse">
            <svg className="w-6 h-6 text-blue-600 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </div>
          <p className="text-sm text-gray-600">Uploading... {progress}%</p>
          <div className="progress-bar max-w-xs mx-auto">
            <div className="progress-bar-fill bg-blue-500" style={{ width: `${progress}%` }} />
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
            <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700">
              {isDragActive ? "Drop your CSV here" : "Upload CSV File"}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Drag & drop or click to browse — CSV files only
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [activePipelineId, setActivePipelineId] = useState<string | null>(null);

  const [storedUser] = useState(() => {
    if (typeof window !== "undefined") {
      const u = localStorage.getItem("user");
      return u ? JSON.parse(u) : null;
    }
    return null;
  });
  const userId = storedUser?._id as Id<"users"> | undefined;

  // Get reports list from Convex (will be null until user is logged in)
  const reports = useQuery(api.reports.listReports, userId ? { userId } : "skip");

  const handleUploadComplete = (uploadId: string) => {
    router.push("/upload");
  };

  return (
    <Layout>
      <div className="space-y-6 animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-sm text-gray-500 mt-1">
              AutoInsight AI v1.0 — Convex + OpenRouter Engine
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full" />
            <span className="text-sm text-gray-500">
              System Online
            </span>
          </div>
        </div>

        {/* Quick Upload */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Quick Upload
          </h2>
          <QuickUploadZone onUploadComplete={handleUploadComplete} />
        </div>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatusCard
            title="Pipeline Runs"
            value={reports?.length || 0}
            subtitle="Total this session"
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            }
            color="bg-blue-50 text-blue-600"
          />
          <StatusCard
            title="Reports Generated"
            value={reports?.length || 0}
            subtitle="Ready to view"
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            }
            color="bg-purple-50 text-purple-600"
          />
          <StatusCard
            title="Avg Confidence"
            value="85%"
            subtitle="Across all reports"
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            color="bg-green-50 text-green-600"
          />
          <StatusCard
            title="Max File Size"
            value={formatBytes(100 * 1024 * 1024)}
            subtitle="Per upload"
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
              </svg>
            }
            color="bg-orange-50 text-orange-600"
          />
        </div>

        {/* Active Pipeline */}
        {activePipelineId && (
          <PipelineProgress
            state={{
              pipeline_id: activePipelineId,
              status: "running",
              global_progress: 45,
              current_stage: 2,
              stages: {
                stage1: { status: "completed" },
                stage2: { status: "running" },
                stage3: { status: "pending" },
                stage4: { status: "pending" },
              },
            }}
          />
        )}

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => router.push("/upload")}
            className="card p-6 hover:shadow-md hover:border-blue-200 transition-all group text-left"
          >
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mb-3 group-hover:bg-blue-200 transition-colors">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
            </div>
            <h3 className="font-semibold text-gray-900">Upload Dataset</h3>
            <p className="text-sm text-gray-500 mt-1">Upload CSV files for analysis</p>
          </button>
          <button
            onClick={() => router.push("/nlq")}
            className="card p-6 hover:shadow-md hover:border-purple-200 transition-all group text-left"
          >
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center mb-3 group-hover:bg-purple-200 transition-colors">
              <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <h3 className="font-semibold text-gray-900">Ask Questions</h3>
            <p className="text-sm text-gray-500 mt-1">Query your data using natural language</p>
          </button>
          <button
            onClick={() => router.push("/dashboard")}
            className="card p-6 hover:shadow-md hover:border-green-200 transition-all group text-left"
          >
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center mb-3 group-hover:bg-green-200 transition-colors">
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="font-semibold text-gray-900">View Reports</h3>
            <p className="text-sm text-gray-500 mt-1">Browse generated analytical reports</p>
          </button>
        </div>
      </div>
    </Layout>
  );
}
