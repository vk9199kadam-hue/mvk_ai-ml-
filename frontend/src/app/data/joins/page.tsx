"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useAction } from "convex/react";
import { api } from "../../../../convex/_generated/api";
import Layout from "@/components/Layout";
import toast from "react-hot-toast";
import type { Id } from "../../../../convex/_generated/dataModel";

// ── Join Type Options ────────────────────────────────────────────────────

const JOIN_TYPES = [
  { value: "inner", label: "INNER JOIN", desc: "Only matching rows from both datasets" },
  { value: "left", label: "LEFT JOIN", desc: "All source rows + matching target rows" },
  { value: "right", label: "RIGHT JOIN", desc: "All target rows + matching source rows" },
  { value: "outer", label: "FULL OUTER JOIN", desc: "All rows from both datasets" },
] as const;

// ── Props ─────────────────────────────────────────────────────────────────

interface UploadOption {
  _id: Id<"uploads">;
  fileName: string;
}

// ── Main Page ─────────────────────────────────────────────────────────────

export default function DataJoinsPage() {
  const [storedUser, setStoredUser] = useState(() => {
    if (typeof window !== "undefined") {
      const u = localStorage.getItem("user");
      return u ? JSON.parse(u) : null;
    }
    return null;
  });
  const userId = storedUser?._id as Id<"users"> | undefined;

  // Queries
  const uploads = useQuery(api.uploads.listUploads, userId ? { userId } : "skip");
  const relations = useQuery(api.joins.listRelations, userId ? { userId } : "skip");

  // Mutations
  const createRelation = useMutation(api.joins.createRelation);
  const deleteRelation = useMutation(api.joins.deleteRelation);
  const executeJoin = useAction(api.joins.executeJoin);
  const discoverRelations = useAction(api.cross_relations.discoverCrossRelations);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    sourceUploadId: "",
    targetUploadId: "",
    sourceColumn: "",
    targetColumn: "",
    joinType: "inner" as string,
  });
  const [creating, setCreating] = useState(false);
  const [executingId, setExecutingId] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [joinedPreview, setJoinedPreview] = useState<{
    columns: string[];
    rowCount: number;
    data: Record<string, any>[];
  } | null>(null);

  // Get all uploads as options
  const uploadList = (uploads || []) as UploadOption[];



  const handleCreateRelation = async () => {
    if (!userId) { toast.error("Please log in"); return; }
    if (!form.name || !form.sourceUploadId || !form.targetUploadId || !form.sourceColumn || !form.targetColumn) {
      toast.error("Please fill all required fields");
      return;
    }
    setCreating(true);
    try {
      await createRelation({
        userId,
        name: form.name,
        description: form.description || undefined,
        sourceUploadId: form.sourceUploadId as Id<"uploads">,
        targetUploadId: form.targetUploadId as Id<"uploads">,
        sourceColumn: form.sourceColumn,
        targetColumn: form.targetColumn,
        joinType: form.joinType as any,
      });
      toast.success(`Relation "${form.name}" created!`);
      setShowForm(false);
      setForm({ name: "", description: "", sourceUploadId: "", targetUploadId: "", sourceColumn: "", targetColumn: "", joinType: "inner" });
    } catch (err: any) {
      toast.error(err?.message || "Failed to create relation");
    } finally {
      setCreating(false);
    }
  };

  const handleExecuteJoin = async (relationId: Id<"datasetRelations">) => {
    if (!userId) return;
    setExecutingId(relationId);
    setJoinedPreview(null);
    try {
      const result = await executeJoin({ relationId, userId });
      toast.success(`Joined! ${result.rowCount} rows, ${result.columns.length} columns`);
      setJoinedPreview(result as any);
    } catch (err: any) {
      toast.error(err?.message || "Join failed");
    } finally {
      setExecutingId(null);
    }
  };

  const handleDiscoverRelations = async () => {
    if (!userId) { toast.error("Please log in"); return; }
    setDiscovering(true);
    try {
      const res = await discoverRelations({ userId });
      if (res.success) {
        toast.success(`Discovered and created ${res.found} suggested relations!`);
      } else {
        toast.error(res.message || "Failed to discover relations");
      }
    } catch (err: any) {
      toast.error(err?.message || "Failed to discover relations");
    } finally {
      setDiscovering(false);
    }
  };

  const handleDeleteRelation = async (relationId: Id<"datasetRelations">) => {
    try {
      await deleteRelation({ relationId });
      toast.success("Relation deleted");
    } catch (err: any) {
      toast.error(err?.message || "Delete failed");
    }
  };

  return (
    <Layout>
      <div className="space-y-6 animate-fade-in max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Data Joins</h1>
            <p className="text-sm text-gray-500 mt-1">
              Combine multiple datasets using SQL-style joins
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDiscoverRelations}
              disabled={discovering}
              className="px-4 py-2 border border-blue-200 text-blue-600 rounded-lg hover:bg-blue-50 text-sm font-medium transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              {discovering ? "Discovering..." : "✨ Auto-Discover"}
            </button>
            <button
              onClick={() => setShowForm(!showForm)}
              className="btn-primary flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              New Relation
            </button>
          </div>
        </div>

        {/* Create Relation Form */}
        {showForm && (
          <div className="card p-6 border-2 border-blue-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Define Dataset Relation</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="label">Relation Name *</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="input-field"
                  placeholder="e.g. Sales + Customers"
                />
              </div>
              <div>
                <label className="label">Description</label>
                <input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="input-field"
                  placeholder="Optional description"
                />
              </div>
              <div>
                <label className="label">Source Dataset *</label>
                <select
                  value={form.sourceUploadId}
                  onChange={(e) => setForm({ ...form, sourceUploadId: e.target.value, sourceColumn: "" })}
                  className="input-field"
                >
                  <option value="">Select source...</option>
                  {uploadList.map((u) => (
                    <option key={u._id} value={u._id}>{u.fileName}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Target Dataset *</label>
                <select
                  value={form.targetUploadId}
                  onChange={(e) => setForm({ ...form, targetUploadId: e.target.value, targetColumn: "" })}
                  className="input-field"
                >
                  <option value="">Select target...</option>
                  {uploadList.map((u) => (
                    <option key={u._id} value={u._id}>{u.fileName}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Source Column (Join Key) *</label>
                <input
                  value={form.sourceColumn}
                  onChange={(e) => setForm({ ...form, sourceColumn: e.target.value })}
                  className="input-field"
                  placeholder="Column name in source"
                />
              </div>
              <div>
                <label className="label">Target Column (Join Key) *</label>
                <input
                  value={form.targetColumn}
                  onChange={(e) => setForm({ ...form, targetColumn: e.target.value })}
                  className="input-field"
                  placeholder="Column name in target"
                />
              </div>
              <div>
                <label className="label">Join Type</label>
                <select
                  value={form.joinType}
                  onChange={(e) => setForm({ ...form, joinType: e.target.value })}
                  className="input-field"
                >
                  {JOIN_TYPES.map((jt) => (
                    <option key={jt.value} value={jt.value}>{jt.label}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-400 mt-1">
                  {JOIN_TYPES.find((jt) => jt.value === form.joinType)?.desc}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 mt-6 pt-4 border-t border-gray-100">
              <button
                onClick={handleCreateRelation}
                disabled={creating}
                className="btn-primary disabled:opacity-50"
              >
                {creating ? "Creating..." : "Create Relation"}
              </button>
              <button
                onClick={() => setShowForm(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Joins Info Card */}
        <div className="p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl border border-blue-100">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center shrink-0">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
            </div>
            <div>
              <h3 className="font-medium text-gray-900">How Joins Work</h3>
              <p className="text-sm text-gray-600 mt-1">
                Define a relation between two datasets by specifying the columns that contain matching keys.
                The join engine combines them using the selected join type. Results are cached for fast access.
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                {JOIN_TYPES.map((jt) => (
                  <span key={jt.value} className="text-xs bg-white px-2.5 py-1 rounded-full border border-gray-200 text-gray-600">
                    {jt.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Relations List */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Defined Relations {relations && relations.length > 0 && `(${relations.length})`}
          </h2>
          {(!relations || relations.length === 0) ? (
            <div className="card p-12 text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900">No Relations Yet</h3>
              <p className="text-sm text-gray-500 mt-2 mb-6">
                Upload at least two datasets, then define a relation to join them.
              </p>
              <button
                onClick={() => setShowForm(true)}
                className="btn-primary"
              >
                + Create Your First Relation
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {relations.map((rel: any) => (
                <div key={rel._id} className="card p-5 hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="font-semibold text-gray-900">{rel.name}</h3>
                        <span className="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full border border-blue-200">
                          {rel.joinType.toUpperCase()} JOIN
                        </span>
                      </div>
                      {rel.description && (
                        <p className="text-sm text-gray-500 mt-1">{rel.description}</p>
                      )}
                      <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                        <span>📄 {rel.sourceUploadId?.slice(0, 8)}... <strong>{rel.sourceColumn}</strong></span>
                        <span>→</span>
                        <span>📄 {rel.targetUploadId?.slice(0, 8)}... <strong>{rel.targetColumn}</strong></span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleExecuteJoin(rel._id)}
                        disabled={executingId === rel._id}
                        className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                      >
                        {executingId === rel._id ? "Joining..." : "▶ Execute Join"}
                      </button>
                      <button
                        onClick={() => handleDeleteRelation(rel._id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Joined Dataset Preview */}
      {joinedPreview && (
        <div className="card p-6 border border-green-200 bg-white space-y-4 animate-fade-in max-w-5xl mx-auto mt-6">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <span className="text-green-500">✓</span> Joined Result Preview
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Showing first 10 rows of {joinedPreview.rowCount} total rows · {joinedPreview.columns.length} columns
              </p>
            </div>
            <button
              onClick={() => setJoinedPreview(null)}
              className="text-xs font-semibold text-gray-500 hover:text-gray-700 bg-gray-50 hover:bg-gray-100 px-2.5 py-1.5 rounded-lg border border-gray-200 transition-all"
            >
              Close Preview
            </button>
          </div>

          {/* Table Container */}
          <div className="overflow-x-auto border border-gray-200 rounded-lg max-h-96">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 font-medium text-gray-500 sticky top-0">
                <tr>
                  {joinedPreview.columns.map((col) => (
                    <th key={col} className="px-4 py-2 text-left text-xs font-mono select-all whitespace-nowrap bg-gray-50 border-b border-gray-200">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200 text-gray-700">
                {joinedPreview.data.slice(0, 10).map((row, i) => (
                  <tr key={i} className="hover:bg-gray-50/50">
                    {joinedPreview.columns.map((col) => (
                      <td key={col} className="px-4 py-2 font-mono text-xs whitespace-nowrap">
                        {row[col] === null ? (
                          <span className="text-gray-300 italic">null</span>
                        ) : typeof row[col] === "object" ? (
                          JSON.stringify(row[col])
                        ) : (
                          String(row[col])
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Layout>
  );
}
