"use client";

import React, { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { useMutation, useAction } from "convex/react";
import { api } from "../../../convex/_generated/api";
import Layout from "@/components/Layout";
import { cn } from "@/lib/utils";
import { useUploadConfig } from "@/store";
import type { Id } from "../../../convex/_generated/dataModel";
import toast from "react-hot-toast";

// ── Upload Progress Component ────────────────────────────────────────────

function UploadProgressCard({ filename, progress, status }: {
  filename: string; progress: number; status: string;
}) {
  return (
    <div className="card p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="font-medium text-gray-900">{filename}</p>
          <p className="text-sm text-gray-500 capitalize">{status}</p>
        </div>
        <span className="text-sm font-bold text-blue-600">{progress}%</span>
      </div>
      <div className="progress-bar">
        <div className={cn("progress-bar-fill", status === "completed" ? "bg-green-500" : status === "failed" ? "bg-red-500" : "bg-blue-500")} style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

function PipelineProgressCard({ progress }: { progress: number }) {
  const stages = [
    { key: "stage1", label: "CSV → Schema Inference" },
    { key: "stage2", label: "Data Cleaning" },
    { key: "stage3", label: "LangGraph Analysis" },
    { key: "stage4", label: "Column Engineering" },
  ];
  return (
    <div className="card p-6">
      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <svg className="w-5 h-5 text-blue-500 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        Pipeline Running — {progress}%
      </h3>
      <div className="space-y-3">
        <div className="progress-bar">
          <div className="progress-bar-fill bg-gradient-to-r from-blue-500 to-purple-500" style={{ width: `${progress}%` }} />
        </div>
        {stages.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-3">
            <span className={cn("w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold",
              progress > (i + 1) * 25 ? "bg-green-100 text-green-600" : progress > i * 25 ? "bg-blue-100 text-blue-600 animate-pulse" : "bg-gray-100 text-gray-400")}>
              {progress > (i + 1) * 25 ? "✓" : i + 1}
            </span>
            <span className={cn("text-sm flex-1", progress > (i + 1) * 25 ? "text-green-700" : progress > i * 25 ? "text-blue-700" : "text-gray-400")}>
              {stage.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function UploadPage() {
  const router = useRouter();
  const { skipCleaning, chunkSizeMB, setSkipCleaning, setChunkSizeMB } = useUploadConfig();
  const [uploadState, setUploadState] = useState<{
    status: "idle" | "uploading" | "pipeline" | "completed" | "failed";
    progress: number;
    filename: string;
    uploadId?: Id<"uploads">;
    pipelineId?: Id<"pipelineResults">;
    datasetId?: Id<"datasets">;
  }>({ status: "idle", progress: 0, filename: "" });

  // Convex mutations & actions
  const initiateUpload = useMutation(api.uploads.initiateUpload);
  const generateUploadUrl = useMutation(api.uploads.generateUploadUrl);
  const updateUploadStatus = useMutation(api.uploads.updateUploadStatus);
  const storeDataset = useMutation(api.datasets.storeDataset);
  const runPipeline = useAction(api.pipeline.index.runPipeline);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;
    if (!file.name.endsWith(".csv")) { toast.error("Only CSV files"); return; }

    setUploadState({ status: "uploading", progress: 0, filename: file.name });

    try {
      // 1. Get user ID from local state (simplified)
      const storedUser = localStorage.getItem("user");
      if (!storedUser) throw new Error("Must be logged in");
      const user = JSON.parse(storedUser);

      // 2. Initiate upload record in Convex
      const { uploadId } = await initiateUpload({
        userId: user._id || "" as any,
        fileName: file.name,
        fileSize: file.size,
      });

      // 3. Upload file to Convex Storage
      const uploadUrl = await generateUploadUrl();
      const uploadResponse = await fetch(uploadUrl, {
        method: "POST",
        headers: { "Content-Type": "text/csv" },
        body: file,
      });
      if (!uploadResponse.ok) throw new Error("Storage upload failed");
      const { storageId } = await uploadResponse.json();

      setUploadState((prev) => ({ ...prev, progress: 40, uploadId }));

      // 4. Parse CSV via Convex and store as dataset
      const text = await file.text();
      const lines = text.split("\n").filter((l: string) => l.trim());
      const headers = lines[0].split(",").map((h: string) => h.trim());
      const rows = lines.slice(1).map((line: string) => {
        const vals = line.split(",").map((v: string) => v.trim());
        const row: Record<string, any> = {};
        headers.forEach((h: string, i: number) => {
          const num = Number(vals[i]);
          row[h] = isNaN(num) ? (vals[i] || null) : num;
        });
        return row;
      });

      const { datasetId } = await storeDataset({
        uploadId,
        userId: user._id || "" as any,
        columns: headers,
        rowCount: rows.length,
        data: rows.slice(0, 10000), // limit to 10k rows for Convex
      });

      setUploadState((prev) => ({ ...prev, progress: 50, datasetId }));
      toast.success("File uploaded & stored!");

      // 5. Run pipeline
      setUploadState((prev) => ({ ...prev, status: "pipeline", progress: 55 }));

      const pipelineResult = await runPipeline({
        uploadId,
        datasetId,
        userId: user._id || "" as any,
        skipCleaning,
      });

      setUploadState((prev) => ({
        ...prev,
        status: pipelineResult.status === "completed" ? "completed" : "failed",
        progress: pipelineResult.status === "completed" ? 100 : 0,
        pipelineId: pipelineResult.pipelineId,
      }));

      if (pipelineResult.status === "completed") {
        toast.success("Pipeline completed!");
      } else {
        toast.error("Pipeline failed");
      }
    } catch (err: any) {
      setUploadState((prev) => ({ ...prev, status: "failed" }));
      toast.error(err?.message || "Upload failed");
    }
  }, [initiateUpload, generateUploadUrl, storeDataset, runPipeline]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    maxFiles: 1,
    disabled: uploadState.status !== "idle",
  });

  const handleReset = () => {
    setUploadState({ status: "idle", progress: 0, filename: "" });
  };

  return (
    <Layout>
      <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Upload Data</h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload CSV files for automated analysis
          </p>
        </div>

        {/* Upload Zone */}
        <div
          {...getRootProps()}
          className={cn(
            "card p-12 text-center cursor-pointer transition-all duration-200 border-2 border-dashed",
            isDragActive && "border-blue-500 bg-blue-50",
            uploadState.status === "idle" && "hover:border-blue-300 hover:bg-gray-50",
            uploadState.status !== "idle" && "cursor-not-allowed opacity-75"
          )}
        >
          <input {...getInputProps()} />
          <div className="space-y-4">
            <div
              className={cn(
                "w-16 h-16 rounded-2xl flex items-center justify-center mx-auto transition-all",
                uploadState.status === "idle" && "bg-blue-100",
                uploadState.status === "uploading" && "bg-blue-100 animate-pulse",
                uploadState.status === "pipeline" && "bg-purple-100 animate-pulse",
                uploadState.status === "completed" && "bg-green-100",
                uploadState.status === "failed" && "bg-red-100"
              )}
            >
              {uploadState.status === "idle" && (
                <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              )}
              {uploadState.status === "uploading" && (
                <svg className="w-8 h-8 text-blue-600 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              )}
              {uploadState.status === "pipeline" && (
                <svg className="w-8 h-8 text-purple-600 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              )}
              {uploadState.status === "completed" && (
                <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
              {uploadState.status === "failed" && (
                <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              )}
            </div>

            {uploadState.status === "idle" && (
              <>
                <p className="text-lg font-medium text-gray-700">
                  {isDragActive ? "Drop your CSV file here" : "Upload CSV File"}
                </p>
                <p className="text-sm text-gray-400">
                  Drag & drop or click to browse — CSV files only, up to 100MB
                </p>
              </>
            )}
            {uploadState.status !== "idle" && (
              <p className="text-sm font-medium text-gray-600">
                {uploadState.filename}
              </p>
            )}
          </div>
        </div>

        {/* Upload Progress */}
        {uploadState.status === "uploading" && (
          <UploadProgressCard
            filename={uploadState.filename}
            progress={uploadState.progress}
            status="uploading"
          />
        )}

        {/* Pipeline Progress */}
        {uploadState.status === "pipeline" && (
          <PipelineProgressCard progress={Math.round(((uploadState.progress - 55) / 45) * 100)} />
        )}

        {/* Completed State */}
        {uploadState.status === "completed" && (
          <div className="card p-6 text-center space-y-4">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Pipeline Complete!</h3>
              <p className="text-sm text-gray-500 mt-1">
                Your data has been processed. View the report now.
              </p>
            </div>
            <div className="flex items-center justify-center gap-3">
              <button onClick={handleReset} className="btn-secondary">
                Upload Another
              </button>
              <button
                onClick={() => router.push("/dashboard")}
                className="btn-primary"
              >
                View Dashboard
              </button>
            </div>
          </div>
        )}

        {/* Failed State */}
        {uploadState.status === "failed" && (
          <div className="card p-6 text-center space-y-4 border-red-200">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Upload Failed</h3>
              <p className="text-sm text-gray-500 mt-1">
                Something went wrong. Please try again.
              </p>
            </div>
            <button onClick={handleReset} className="btn-primary">
              Try Again
            </button>
          </div>
        )}

        {/* Config Panel */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Upload Configuration</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="label text-gray-400">LLM Provider</label>
              <div className="input-field text-sm bg-gray-100 flex items-center px-3 py-2 rounded-lg">
                <span className="text-blue-600 font-medium">OpenRouter (qwen/qwen3-coder:free)</span>
              </div>
            </div>
            <div>
              <label className="label">Chunk Size</label>
              <select
                value={chunkSizeMB}
                onChange={(e) => setChunkSizeMB(Number(e.target.value))}
                className="input-field text-sm"
                disabled={uploadState.status !== "idle"}
              >
                <option value={0.5}>512 KB</option>
                <option value={1}>1 MB</option>
                <option value={5}>5 MB</option>
                <option value={10}>10 MB</option>
              </select>
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={skipCleaning}
                  onChange={(e) => setSkipCleaning(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  disabled={uploadState.status !== "idle"}
                />
                <span className="text-sm text-gray-600">Skip cleaning (data is clean)</span>
              </label>
            </div>
          </div>
        </div>

        {/* Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card p-4">
            <h4 className="font-medium text-gray-900 text-sm">Stage 1: CSV Parsing</h4>
            <p className="text-xs text-gray-500 mt-1">chardet encoding + Polars parsing + Qwen schema inference</p>
          </div>
          <div className="card p-4">
            <h4 className="font-medium text-gray-900 text-sm">Stage 2: Cleaning</h4>
            <p className="text-xs text-gray-500 mt-1">Quality profiling + AI cleaning plan + transformations</p>
          </div>
          <div className="card p-4">
            <h4 className="font-medium text-gray-900 text-sm">Stage 3-4: Analysis</h4>
            <p className="text-xs text-gray-500 mt-1">LangGraph relationships + column engineering + UDM assembly</p>
          </div>
        </div>
      </div>
    </Layout>
  );
}
