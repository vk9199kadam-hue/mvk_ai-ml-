# =============================================================================
# AutoInsight AI — 4-Phase Report Generation Engine Package
# Phase 1: Foundation — Report Engine Stubs
# =============================================================================
"""
4-Phase Report Generation Engine Package.

Generates comprehensive analytical reports through 4 phases:

  Phase 1: Deterministic Profiling (Zero LLM — $0)
    - extract_schema_metadata()
    - compute_univariate_stats()
    - compute_bivariate_matrix()
    - detect_trends_seasonality()
    - infer_domain_context()
    Output: DataProfile object

  Phase 2: 8 Parallel Sub-Agents (LLM-powered)
    - Business Understanding
    - Data Collection
    - Cleaning & Analysis
    - EDA
    - Statistical Analysis
    - Dashboard & Visualization
    - Insights
    - Recommendations
    ALL 8 RUN IN PARALLEL via asyncio.gather

  Phase 3: Validation & Confidence Gating
    - Pydantic validation per report section
    - Confidence >= 0.70 for auto-approval
    - Retry loop (max 3 attempts)
    - Fallback: deterministic rule-based summary

  Phase 4: Assembly & Export
    - Merge into ReportBundle JSON
    - PDF (Puppeteer), HTML (Jinja2), Markdown (Jinja2), Excel (OpenPyXL)
    - S3 storage + PostgreSQL indexing
"""

from backend.report.phase1_profiling import Phase1_Profiling
from backend.report.phase2_sub_agents import Phase2_SubAgents
from backend.report.phase3_validation import Phase3_Validation
from backend.report.phase4_export import Phase4_Export
from backend.report.orchestrator import ReportOrchestrator

__all__ = [
    "Phase1_Profiling",
    "Phase2_SubAgents",
    "Phase3_Validation",
    "Phase4_Export",
    "ReportOrchestrator",
]
