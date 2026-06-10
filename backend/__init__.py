# =============================================================================
# AutoInsight AI — Backend Package
# Phase 1: Foundation
# =============================================================================
"""
AutoInsight AI Backend — Agentic Data Analysis & Report Generation Platform.

Architecture:
  5-Layer System:
    1. Presentation Layer — React/Next.js PWA (Frontend)
    2. API Gateway Layer — FastAPI + JWT + RBAC
    3. AI Orchestration Layer — LangGraph Agents
    4. Data Processing Engine — Polars + DuckDB + DataPrep
    5. Storage Layer — PostgreSQL + Redis + MinIO

Key Design Principles:
  - Deterministic-First: LLM only for reasoning, not computation
  - Confidence Gating: All AI outputs scored ≥0.65
  - Zero-Cost LLM: Groq Free Tier + Ollama local = $0
  - Full Audit Trail: Every transformation logged
"""

__version__ = "1.0.0"
__author__ = "AutoInsight AI Team"

from backend.config import settings
