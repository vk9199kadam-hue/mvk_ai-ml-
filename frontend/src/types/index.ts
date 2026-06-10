// =============================================================================
// AutoInsight AI — Frontend Type Definitions
// Phase 4: React/Next.js Frontend — Types matching backend API
// =============================================================================

// ── API Response Envelope ────────────────────────────────────────────────

export interface ApiResponse<T = any> {
  status: "success" | "error";
  data: T | null;
  meta: {
    timestamp: string;
    request_id: string;
    version: string;
  };
  errors: string[];
}

// ── Auth ─────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "analyst" | "viewer";
  created_at: string;
  is_active: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

// ── Upload ───────────────────────────────────────────────────────────────

export interface UploadInitiateRequest {
  filename: string;
  file_size: number;
  content_type?: string;
}

export interface UploadSession {
  upload_id: string;
  status: string;
  filename: string;
  file_size: number;
  staging_path: string;
  expires_at: string;
}

export interface UploadProgress {
  upload_id: string;
  filename: string;
  progress: number;
  bytes_received: number;
  total_bytes: number;
  status: string;
}

export interface UploadComplete {
  upload_id: string;
  status: string;
  file_hash: string;
  encoding: string;
  storage_key: string;
}

// ── Pipeline ─────────────────────────────────────────────────────────────

export interface PipelineRunRequest {
  upload_id: string;
  llm_provider?: string;
  skip_cleaning?: boolean;
}

export interface PipelineRun {
  pipeline_id: string;
  status: string;
  upload_id: string;
  message: string;
  events_url: string;
  stages: PipelineStage[];
}

export interface PipelineStage {
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  progress?: number;
}

export interface PipelineState {
  pipeline_id: string;
  status: string;
  global_progress: number;
  current_stage: number;
  stages: Record<string, any>;
  error?: string;
  result?: {
    unified_data_model_id: string;
    processing_time_ms: number;
  };
}

export interface PipelineEvent {
  event: string;
  data: string;
}

export interface CleaningDiff {
  pipeline_id: string;
  original_rows: number;
  cleaned_rows: number;
  changes: CleaningChange[];
  quality_improvement: number;
}

export interface CleaningChange {
  column: string;
  changed_count: number;
  change_percentage: number;
  samples: { row: number; before: string; after: string }[];
}

// ── Reports ──────────────────────────────────────────────────────────────

export interface ReportGenerateRequest {
  data_model_id: string;
  title?: string;
}

export interface ReportSectionData {
  section_type: string;
  title: string;
  content: string;
  confidence: number;
  chart_hints?: Record<string, any>[];
}

export interface Report {
  report_id: string;
  title: string;
  status: string;
  overall_confidence: number;
  sections_count: number;
  sections?: ReportSectionData[];
  export_urls: {
    html?: string;
    md?: string;
    pdf?: string;
    xlsx?: string;
  };
  validation?: ReportValidation;
  phase_times_ms?: Record<string, number>;
  total_duration_ms?: number;
  generated_at?: string;
}

export interface ReportValidation {
  total_sections: number;
  auto_approved: number;
  manual_approval: number;
  review_required: number;
  advisory_only: number;
  fallback_used: number;
  retries_performed: number;
  sections: ReportSectionValidation[];
}

export interface ReportSectionValidation {
  section_type: string;
  title: string;
  confidence: number;
  level: string;
  badge: string;
  content_length: number;
  passed_validation: boolean;
  retries: number;
  fallback_used: boolean;
  issues: string[];
}

// ── NLQ ─────────────────────────────────────────────────────────────────

export interface NLQQueryRequest {
  query: string;
  dataset_id: string;
  conversation_id?: string;
}

export interface NLQResponse {
  natural_language_response: string;
  sql_generated?: string;
  chart_config?: Record<string, any>;
  results: Record<string, any>[];
  row_count: number;
  processing_time_ms?: number;
  confidence: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  confidence?: number;
  chart_config?: Record<string, any>;
}

// ── Dashboard ────────────────────────────────────────────────────────────

export interface Dashboard {
  dashboard_id: string;
  title: string;
  charts: ChartConfig[];
  layout: { columns: number };
}

export interface ChartConfig {
  id: string;
  type: string;
  title: string;
  data?: Record<string, any>[];
  layout?: Record<string, any>;
}

// ── Admin ────────────────────────────────────────────────────────────────

export interface UserListResponse {
  users: User[];
  total: number;
}

// ── System ───────────────────────────────────────────────────────────────

export interface SystemInfo {
  application: {
    name: string;
    version: string;
    phase: string;
    debug: boolean;
  };
  llm: {
    provider: string;
    primary_model: string;
    fallback_model: string;
    max_retries: number;
  };
  pipeline: {
    stages: string[];
    max_file_size_mb: number;
    confidence_gate: number;
    retry_base_delay_s: number;
  };
}
