"use client";

import React, { useState, useMemo } from "react";
import { useQuery, useAction } from "convex/react";
import { api } from "../../../../convex/_generated/api";
import Layout from "@/components/Layout";
import toast from "react-hot-toast";
import type { Id } from "../../../../convex/_generated/dataModel";
import { cn } from "@/lib/utils";

interface UploadOption {
  _id: Id<"uploads">;
  fileName: string;
}

export default function MlInsightsPage() {
  const [storedUser] = useState(() => {
    if (typeof window !== "undefined") {
      const u = localStorage.getItem("user");
      return u ? JSON.parse(u) : null;
    }
    return null;
  });
  const userId = storedUser?._id as Id<"users"> | undefined;

  // Queries
  const uploads = useQuery(api.uploads.listUploads, userId ? { userId } : "skip");

  // Actions
  const runMlAnalysis = useAction(api.ml.generateMlInsights);

  // Form state
  const [selectedUploadId, setSelectedUploadId] = useState("");
  const [targetColumn, setTargetColumn] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<{
    recommendedModel: string;
    reasoning: string;
    problemType: string;
    shapValues: Array<{ feature: string; importance: number; impactDirection: string }>;
  } | null>(null);

  // Load columns for selected upload
  const dataset = useQuery(
    api.datasets.getDatasetByUpload,
    selectedUploadId ? { uploadId: selectedUploadId as Id<"uploads"> } : "skip"
  );

  const columns = useMemo(() => (dataset?.columns || []) as string[], [dataset]);

  const uploadList = (uploads || []) as UploadOption[];

  const handleRunAnalysis = async () => {
    if (!selectedUploadId) {
      toast.error("Please select a dataset");
      return;
    }
    if (!targetColumn) {
      toast.error("Please select a target column");
      return;
    }

    setLoading(true);
    setResults(null);
    try {
      const res = await runMlAnalysis({
        uploadId: selectedUploadId as Id<"uploads">,
        targetColumn,
      });

      if (res.success) {
        setResults(res as any);
        toast.success("ML Analysis Completed!");
      } else {
        toast.error("ML analysis failed");
      }
    } catch (err: any) {
      toast.error(err?.message || "ML analysis failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Advanced ML & SHAP Insights</h1>
          <p className="text-sm text-gray-500 mt-1">
            Analyze target variables, auto-select optimal ML models, and discover SHAP feature contributions
          </p>
        </div>

        {/* Configuration Panel */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">ML Configuration</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Select Dataset *</label>
              <select
                value={selectedUploadId}
                onChange={(e) => {
                  setSelectedUploadId(e.target.value);
                  setTargetColumn("");
                  setResults(null);
                }}
                className="input-field"
              >
                <option value="">Choose dataset...</option>
                {uploadList.map((u) => (
                  <option key={u._id} value={u._id}>
                    {u.fileName}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Target Column (Predict Variable) *</label>
              <select
                value={targetColumn}
                onChange={(e) => {
                  setTargetColumn(e.target.value);
                  setResults(null);
                }}
                disabled={!selectedUploadId || columns.length === 0}
                className="input-field disabled:opacity-50"
              >
                <option value="">Choose target...</option>
                {columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-100 flex justify-end">
            <button
              onClick={handleRunAnalysis}
              disabled={loading || !selectedUploadId || !targetColumn}
              className="btn-primary flex items-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <svg className="w-4 h-4 animate-spin text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Running SHAP Engine...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Run ML Analysis
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results Presentation */}
        {results && (
          <div className="space-y-6">
            {/* Model Card */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="card p-5 bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-100 md:col-span-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-600">Recommended Model</p>
                <h3 className="text-xl font-bold text-gray-900 mt-1">{results.recommendedModel}</h3>
                <p className="text-sm text-gray-700 mt-3 leading-relaxed">{results.reasoning}</p>
              </div>

              <div className="card p-5 flex flex-col justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-purple-600">Problem Type</p>
                  <span className={cn(
                    "inline-block px-3 py-1 rounded-full text-xs font-semibold border mt-2 capitalize",
                    results.problemType === "classification" 
                      ? "bg-purple-50 text-purple-700 border-purple-200" 
                      : "bg-blue-50 text-blue-700 border-blue-200"
                  )}>
                    {results.problemType}
                  </span>
                </div>
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <p className="text-xs text-gray-400">Target Column:</p>
                  <p className="text-sm font-mono font-medium text-gray-800 mt-1">{targetColumn}</p>
                </div>
              </div>
            </div>

            {/* SHAP Chart Card */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <span className="text-blue-500">📊</span> SHAP Feature Importances
              </h3>
              <p className="text-xs text-gray-400 mb-6">
                Features are ranked by their average absolute SHAP value, showing overall model contribution.
              </p>

              <div className="space-y-4">
                {results.shapValues.map((val) => (
                  <div key={val.feature} className="space-y-1">
                    <div className="flex justify-between text-xs font-medium">
                      <span className="font-mono text-gray-700">{val.feature}</span>
                      <span className="text-gray-500">{Math.round(val.importance * 100)}% contribution</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="progress-bar flex-1">
                        <div
                          className={cn(
                            "progress-bar-fill transition-all duration-500",
                            val.impactDirection === "positive" 
                              ? "bg-green-500" 
                              : val.impactDirection === "negative" 
                              ? "bg-red-500" 
                              : "bg-blue-500"
                          )}
                          style={{ width: `${val.importance * 100}%` }}
                        />
                      </div>
                      <span className={cn(
                        "text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border shrink-0",
                        val.impactDirection === "positive" 
                          ? "bg-green-50 border-green-200 text-green-700" 
                          : val.impactDirection === "negative" 
                          ? "bg-red-50 border-red-200 text-red-700" 
                          : "bg-blue-50 border-blue-200 text-blue-700"
                      )}>
                        {val.impactDirection}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
