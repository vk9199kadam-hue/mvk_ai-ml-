// =============================================================================
// AutoInsight AI — Convex API Adapter
// Provides typed hooks wrapping Convex queries/mutations/actions
// Drop-in replacement for the old Axios-based lib/api.ts
// =============================================================================

"use client";

import { useQuery, useMutation, useAction } from "convex/react";
import { api } from "../../convex/_generated/api";
import type { Doc, Id } from "../../convex/_generated/dataModel";

// =============================================================================
// Typed Convex Response Helpers (mirrors old ApiResponse envelope)
// =============================================================================

export interface ConvexApiResponse<T> {
  status: "success" | "error";
  data: T | null;
  errors: string[];
}

function wrapSuccess<T>(data: T): ConvexApiResponse<T> {
  return { status: "success", data, errors: [] };
}

function wrapError<T>(error: string): ConvexApiResponse<T> {
  return { status: "error", data: null, errors: [error] };
}

// =============================================================================
// Auth Adapter — using Convex queries/mutations
// =============================================================================

export function useUserQuery(email: string | undefined) {
  return useQuery(api.users.getUser, email ? { email } : "skip");
}

export function useUserByIdQuery(userId: Id<"users"> | undefined) {
  return useQuery(api.users.getUserById, userId ? { userId } : "skip");
}

export function useListUsers() {
  return useQuery(api.users.listUsers);
}

export function useCreateUserMutation() {
  return useMutation(api.users.createUser);
}

export function useUpdateUserRoleMutation() {
  return useMutation(api.users.updateUserRole);
}

export function useDeleteUserMutation() {
  return useMutation(api.users.deleteUser);
}

// =============================================================================
// Upload Adapter
// =============================================================================

export function useUploadsQuery(userId: Id<"users"> | undefined) {
  return useQuery(api.uploads.listUploads, userId ? { userId } : "skip");
}

export function useUploadQuery(uploadId: Id<"uploads"> | undefined) {
  return useQuery(api.uploads.getUpload, uploadId ? { uploadId } : "skip");
}

export function useInitiateUploadMutation() {
  return useMutation(api.uploads.initiateUpload);
}

export function useGenerateUploadUrlMutation() {
  return useMutation(api.uploads.generateUploadUrl);
}

export function useUpdateUploadStatusMutation() {
  return useMutation(api.uploads.updateUploadStatus);
}

// =============================================================================
// Dataset Adapter
// =============================================================================

export function useDatasetQuery(datasetId: Id<"datasets"> | undefined) {
  return useQuery(api.datasets.getDataset, datasetId ? { datasetId } : "skip");
}

export function useDatasetByUploadQuery(uploadId: Id<"uploads"> | undefined) {
  return useQuery(api.datasets.getDatasetByUpload, uploadId ? { uploadId } : "skip");
}

export function useStoreDatasetMutation() {
  return useMutation(api.datasets.storeDataset);
}

// =============================================================================
// Pipeline Adapter
// =============================================================================

export function usePipelineResultQuery(pipelineId: Id<"pipelineResults"> | undefined) {
  return useQuery(api.pipeline.index.getPipelineResult, pipelineId ? { pipelineId } : "skip");
}

export function usePipelineResultsQuery(userId: Id<"users"> | undefined) {
  return useQuery(api.pipeline.index.listPipelineResults, userId ? { userId } : "skip");
}

export function useRunPipelineAction() {
  return useAction(api.pipeline.index.runPipeline);
}

// =============================================================================
// NLQ Adapter
// =============================================================================

export function useConversationQuery(conversationId: Id<"conversations"> | undefined) {
  return useQuery(api.nlq.getConversation, conversationId ? { conversationId } : "skip");
}

export function useConversationsQuery(userId: Id<"users"> | undefined, uploadId: Id<"uploads"> | undefined) {
  return useQuery(
    api.nlq.listConversations,
    userId && uploadId ? { userId, uploadId } : "skip"
  );
}

export function useCreateConversationMutation() {
  return useMutation(api.nlq.createConversation);
}

export function useNlqQueryAction() {
  return useAction(api.nlq.query);
}

// =============================================================================
// Reports Adapter
// =============================================================================

export function useReportQuery(reportId: Id<"reports"> | undefined) {
  return useQuery(api.reports.getReport, reportId ? { reportId } : "skip");
}

export function useReportsQuery(userId: Id<"users"> | undefined) {
  return useQuery(api.reports.listReports, userId ? { userId } : "skip");
}

export function useGenerateReportAction() {
  return useAction(api.reports.generateReport);
}

// =============================================================================
// Dashboards Adapter
// =============================================================================

export function useDashboardQuery(dashboardId: string | undefined) {
  return useQuery(api.dashboards.getDashboard, dashboardId ? { dashboardId: dashboardId as Id<"dashboards"> } : "skip");
}

export function useDashboardsQuery(userId: Id<"users"> | undefined) {
  return useQuery(api.dashboards.listDashboards, userId ? { userId } : "skip");
}

export function useDashboardByUploadQuery(uploadId: Id<"uploads"> | undefined) {
  return useQuery(api.dashboards.getDashboardByUpload, uploadId ? { uploadId } : "skip");
}

export function useCreateDashboardMutation() {
  return useMutation(api.dashboards.createDashboard);
}

export function useUpdateDashboardMutation() {
  return useMutation(api.dashboards.updateDashboard);
}

export function useDeleteDashboardMutation() {
  return useMutation(api.dashboards.deleteDashboard);
}
