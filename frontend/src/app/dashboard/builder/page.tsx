"use client";

import React, { useState, Suspense } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "convex/react";
import { api } from "../../../../convex/_generated/api";
import type { Id } from "../../../../convex/_generated/dataModel";
import Layout from "@/components/Layout";
import ConvexChartBuilder from "@/components/ConvexChartBuilder";

function BuilderContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Load user info
  const [storedUser] = useState(() => {
    if (typeof window !== "undefined") {
      const u = localStorage.getItem("user");
      return u ? JSON.parse(u) : null;
    }
    return null;
  });
  const userId = storedUser?._id as Id<"users"> | undefined;

  // Load user uploads
  const uploads = useQuery(api.uploads.listUploads, userId ? { userId } : "skip");
  const [selectedUploadId, setSelectedUploadId] = useState<string>(
    typeof window !== "undefined" ? (new URLSearchParams(window.location.search).get("uploadId") || "") : ""
  );

  const uploadList = (uploads || []) as Array<{ _id: string; fileName: string; status: string }>;
  const completedUploads = uploadList.filter((u) => u.status === "completed");

  return (
    <Layout>
      <div className="space-y-4 animate-fade-in min-h-[calc(100vh-10rem)]">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => router.push("/dashboard")}
                className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
              </button>
              <h1 className="text-2xl font-bold text-gray-900">Dashboard Builder</h1>
            </div>
            <p className="text-sm text-gray-500 mt-1 ml-9">
              Drag, drop, and customize charts to build your perfect dashboard
            </p>
          </div>
          
          {/* Dataset Selector */}
          <div className="flex items-center gap-3 shrink-0 ml-9 md:ml-0">
            <label className="text-xs font-semibold text-gray-600 uppercase tracking-wider shrink-0">Dataset:</label>
            <select
              value={selectedUploadId}
              onChange={(e) => setSelectedUploadId(e.target.value)}
              className="input-field py-1.5 text-sm w-64 bg-white border border-gray-200 rounded-lg shadow-sm"
            >
              <option value="">Select a dataset...</option>
              {completedUploads.map((u) => (
                <option key={u._id} value={u._id}>
                  {u.fileName}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Builder Canvas */}
        <div className="flex-1 min-h-[600px]">
          {selectedUploadId ? (
            <ConvexChartBuilder uploadId={selectedUploadId} userId={userId} />
          ) : (
            <div className="h-96 flex flex-col items-center justify-center text-center p-12 bg-white border border-gray-200 rounded-xl shadow-sm">
              <div className="w-20 h-20 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mb-4">
                <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Select a Dataset to Start</h3>
              <p className="text-sm text-gray-500 max-w-sm mb-6">
                Choose one of your uploaded CSV datasets from the dropdown menu above to begin building custom drag-and-drop visualizations.
              </p>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}

export default function DashboardBuilderPage() {
  return (
    <Suspense fallback={
      <Layout>
        <div className="h-96 flex items-center justify-center">
          <div className="text-center">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl mx-auto mb-4 animate-pulse" />
            <p className="text-gray-500">Loading builder...</p>
          </div>
        </div>
      </Layout>
    }>
      <BuilderContent />
    </Suspense>
  );
}
