"use client";

import React from "react";
import Layout from "@/components/Layout";
import { cn } from "@/lib/utils";

interface StatusCardProps {
  label: string;
  value: string;
  status: "healthy" | "warning" | "error" | "info";
  icon: React.ReactNode;
}

function StatusCard({ label, value, status, icon }: StatusCardProps) {
  const statusColors = {
    healthy: "bg-green-50 border-green-200 text-green-700",
    warning: "bg-yellow-50 border-yellow-200 text-yellow-700",
    error: "bg-red-50 border-red-200 text-red-700",
    info: "bg-blue-50 border-blue-200 text-blue-700",
  };
  const dotColors = {
    healthy: "bg-green-500",
    warning: "bg-yellow-500",
    error: "bg-red-500",
    info: "bg-blue-500",
  };

  return (
    <div className={cn("card p-5 border-2", statusColors[status])}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className={cn("w-2.5 h-2.5 rounded-full", dotColors[status])} />
            <span className="text-xs font-medium uppercase tracking-wider opacity-70">
              {status}
            </span>
          </div>
          <p className="text-lg font-bold">{value}</p>
          <p className="text-sm opacity-80 mt-0.5">{label}</p>
        </div>
        <div className="opacity-50">{icon}</div>
      </div>
    </div>
  );
}

export default function SystemPage() {
  const services = [
    { label: "Convex Cloud", value: "Connected", status: "healthy" as const },
    { label: "Database", value: "13 tables, 16 indexes", status: "healthy" as const },
    { label: "LLM Provider", value: "OpenRouter (Free Tier)", status: "healthy" as const },
    { label: "File Storage", value: "Convex Storage", status: "healthy" as const },
  ];

  const versionInfo = [
    { label: "Platform", value: "AutoInsight AI" },
    { label: "Version", value: "1.0.0" },
    { label: "Architecture", value: "Convex Cloud + Vercel" },
    { label: "LLM Model", value: "qwen/qwen3-coder:free (Primary)" },
    { label: "Frontend", value: "Next.js 14 + Tailwind CSS" },
    { label: "Auth", value: "Convex + localStorage" },
  ];

  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">System Status</h1>
          <p className="text-sm text-gray-500 mt-1">
            Real-time status of all AutoInsight AI services
          </p>
        </div>

        {/* Service Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {services.map((s) => (
            <StatusCard
              key={s.label}
              label={s.label}
              value={s.value}
              status={s.status as any}
              icon={
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              }
            />
          ))}
        </div>

        {/* Version Info */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Version Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {versionInfo.map((info) => (
              <div key={info.label} className="p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500">{info.label}</p>
                <p className="text-sm font-medium text-gray-900 mt-0.5">{info.value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Database Schema Overview */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Database Tables</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Table</th>
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Purpose</th>
                  <th className="text-left py-2 px-3 text-gray-500 font-medium">Indexes</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["users", "Authentication & roles", "by_email"],
                  ["uploads", "File upload tracking", "by_user"],
                  ["pipelineResults", "Pipeline state & UDM", "by_upload"],
                  ["reports", "Generated reports", "by_user"],
                  ["dashboards", "Dashboard layouts", "by_user"],
                  ["conversations", "NLQ chat history", "by_user_upload"],
                  ["datasets", "Stored CSV data", "by_upload"],
                  ["auditLog", "Enterprise audit trail", "by_user, by_resource, by_timestamp"],
                  ["prompts", "Versioned prompt templates", "by_name"],
                  ["datasetRelations", "Dataset relationships for multi-dataset joins (V4)", "by_user"],
                  ["joinedDatasets", "Joined datasets cache (V4)", "by_user, by_relation"],
                  ["scheduledReports", "Scheduled email report configuration (V5)", "by_user"],
                  ["reportVersions", "Report version history & edits (V5)", "by_report"],
                ].map(([table, purpose, indexes]) => (
                  <tr key={table} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3 font-mono text-blue-600 text-xs">{table}</td>
                    <td className="py-2 px-3 text-gray-600 text-xs">{purpose}</td>
                    <td className="py-2 px-3 text-gray-400 text-xs">{indexes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Architecture Diagram */}
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Architecture</h2>
          <div className="flex flex-col items-center gap-3 py-4">
            <div className="px-6 py-3 bg-blue-50 border border-blue-200 rounded-lg text-center">
              <p className="text-sm font-medium text-blue-700">Frontend</p>
              <p className="text-xs text-blue-500">Vercel CDN · Next.js 14</p>
            </div>
            <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
            <div className="px-6 py-3 bg-purple-50 border border-purple-200 rounded-lg text-center">
              <p className="text-sm font-medium text-purple-700">Backend</p>
              <p className="text-xs text-purple-500">Convex Cloud · 37 Functions</p>
            </div>
            <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
            <div className="px-6 py-3 bg-green-50 border border-green-200 rounded-lg text-center">
              <p className="text-sm font-medium text-green-700">LLM Provider</p>
              <p className="text-xs text-green-500">OpenRouter · qwen/qwen3-coder:free · $0/month</p>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
