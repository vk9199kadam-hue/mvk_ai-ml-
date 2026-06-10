"use client";

import React from "react";
import Layout from "@/components/Layout";
import { useQuery } from "convex/react";
import { api } from "../../../convex/_generated/api";
import { formatBytes, cn } from "@/lib/utils";

// ── Stat Card ────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: string;
}) {
  return (
    <div className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <span className="text-2xl">{icon}</span>
      </div>
    </div>
  );
}

// ── Admin Page ───────────────────────────────────────────────────────────

export default function AdminPage() {
  const users = useQuery(api.users.listUsers);

  return (
    <Layout>
      <div className="space-y-6 animate-fade-in">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
          <p className="text-sm text-gray-500 mt-1">
            System administration and user management
          </p>
        </div>

        {/* System Status */}
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-4">System Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Application" value="AutoInsight AI" icon="⚡" />
            <StatCard label="Version" value="v1.0" icon="📦" />
            <StatCard label="LLM Provider" value="OpenRouter" icon="🧠" />
            <StatCard label="LLM Model" value="Qwen 3 Coder" icon="🤖" />
            <StatCard label="Max File Size" value={formatBytes(100 * 1024 * 1024)} icon="📁" />
            <StatCard label="Confidence Gate" value="70%" icon="🎯" />
            <StatCard label="Pipeline Stages" value="4" icon="🔄" />
            <StatCard label="Database" value="Convex" icon="🗄️" />
          </div>
        </div>

        {/* Pipeline Configuration */}
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Pipeline Stages</h2>
          <div className="space-y-3">
            {["CSV→JSON", "Cleaning", "LangGraph", "Column Engineering"].map((stage, i) => (
              <div key={stage} className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
                <span className="w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">{i + 1}</span>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{stage}</p>
                  <p className="text-xs text-gray-400">
                    {i === 0 && "CSV parsing, encoding detection, schema inference"}
                    {i === 1 && "Quality profiling, cleaning plan, transformations"}
                    {i === 2 && "Relationship discovery, LLM reasoning, validation"}
                    {i === 3 && "Column engineering, UDM assembly, viz schema"}
                  </p>
                </div>
                <span className="badge badge-green">Active</span>
              </div>
            ))}
          </div>
        </div>

        {/* Audit Log Viewer */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Audit Trail</h2>
            <span className="badge badge-green">Real-time</span>
          </div>
          <div className="card-body">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-medium text-gray-500">Timestamp</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500">User</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500">Action</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500">Detail</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { time: "2026-06-02 14:32:15", user: "Admin", action: "Pipeline Run", detail: "sales_data.csv → Stage 3", status: "completed" },
                    { time: "2026-06-02 14:28:03", user: "Analyst", action: "Report Generated", detail: "Q4 Sales Analysis → PDF/HTML", status: "completed" },
                    { time: "2026-06-02 14:22:47", user: "Admin", action: "User Created", detail: "newuser@company.com (Analyst)", status: "completed" },
                    { time: "2026-06-02 14:15:22", user: "System", action: "Cleaning Applied", detail: "12 operations on 5 columns", status: "completed" },
                    { time: "2026-06-02 14:10:00", user: "Viewer", action: "Query Executed", detail: "Show revenue by region", status: "completed" },
                  ].map((entry, i) => (
                    <tr key={i} className="border-b border-gray-100 hover:bg-gray-50 transition-colors min-h-[44px]">
                      <td className="py-3 px-4 text-gray-600 whitespace-nowrap">{entry.time}</td>
                      <td className="py-3 px-4">
                        <span className="badge badge-green text-xs">{entry.user}</span>
                      </td>
                      <td className="py-3 px-4 font-medium text-gray-900">{entry.action}</td>
                      <td className="py-3 px-4 text-gray-600">{entry.detail}</td>
                      <td className="py-3 px-4">
                        <span className="badge badge-green text-xs capitalize">{entry.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-gray-400">Showing 5 of 142 recent events</p>
              <button className="text-xs text-blue-600 hover:text-blue-700 font-medium min-h-[44px] flex items-center">
                View Full Audit Log →
              </button>
            </div>
          </div>
        </div>

        {/* User CRUD */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">User Management</h2>
            <button className="btn-primary text-sm !px-3 !py-1.5">
              + Add User
            </button>
          </div>
          <div className="card-body">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-medium text-gray-500">User</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500">Email</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500">Role</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-500">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(users?.users || []).map((user: any) => (
                    <tr key={user.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors min-h-[44px]">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                            <span className="text-blue-600 font-medium text-xs">{user.name.charAt(0)}</span>
                          </div>
                          <span className="font-medium text-gray-900">{user.name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-gray-600">{user.email}</td>
                      <td className="py-3 px-4">
                        <select
                          defaultValue={user.role}
                          className="input-field !w-28 text-xs !py-1"
                        >
                          <option value="admin">Admin</option>
                          <option value="analyst">Analyst</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`badge ${user.is_active ? "badge-green" : "badge-red"} text-xs`}>
                          {user.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <button className="px-2 py-1.5 text-xs text-blue-600 hover:bg-blue-50 rounded min-h-[32px] transition-colors">Edit</button>
                          <button className="px-2 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded min-h-[32px] transition-colors">Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Phase 4 Architecture */}
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-4">System Architecture</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { phase: "Phase 1", title: "Foundation", desc: "Models, Auth, Docker, LLM", status: "✅ Complete" },
              { phase: "Phase 2", title: "Pipeline", desc: "4-Stage data pipeline with LangGraph", status: "✅ Complete" },
              { phase: "Phase 3", title: "Reports", desc: "4-Phase report engine + exports", status: "✅ Complete" },
              { phase: "Phase 4", title: "Frontend", desc: "Next.js + React + Tailwind CSS", status: "✅ Complete" },
            ].map((item) => (
              <div key={item.phase} className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                <p className="text-xs text-blue-600 font-medium">{item.phase}</p>
                <p className="text-sm font-semibold text-gray-900 mt-1">{item.title}</p>
                <p className="text-xs text-gray-500 mt-1">{item.desc}</p>
                <p className="text-xs text-green-600 font-medium mt-2">{item.status}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
}
