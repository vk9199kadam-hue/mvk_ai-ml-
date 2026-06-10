# =============================================================================
# AutoInsight AI — 4-Stage Data Pipeline Package
# Phase 1: Foundation — Pipeline Stubs
# =============================================================================
"""
4-Stage Data Pipeline Package.

The pipeline transforms raw CSV data into a complete UnifiedDataModel
through 4 sequential stages:

  Stage 1: CSV → JSON (Schema Inference)
    Input: Raw CSV file
    Output: SchemaInferenceResponse + Structured JSON
    LLM: Qwen 2.5 72B (Groq)
    
  Stage 2: Data Cleaning
    Input: Structured JSON
    Output: Cleaned Parquet + Audit Log
    LLM: Qwen 2.5 72B (Groq)
    
  Stage 3: LangGraph Core Agent (Relationship Discovery)
    Input: Cleaned Parquet
    Output: UnifiedDataModel (relationships + derived_columns)
    LLM: Qwen 2.5 72B (reason_step only)
    
  Stage 4: Column Engineering
    Input: UnifiedDataModel
    Output: Enriched Viz-Ready Dataset + Complete UDM
    LLM: None (fully deterministic)

Each stage can be independently:
  - Developed and tested
  - Configured via environment variables
  - Monitored via the audit trail
  - Re-run with different parameters
"""

from backend.pipeline.stage1_csv_to_json import Stage1_CSVtoJSON
from backend.pipeline.stage2_data_clean import Stage2_DataClean
from backend.pipeline.stage3_langgraph_agent import Stage3_LangGraphAgent
from backend.pipeline.stage4_column_engine import Stage4_ColumnEngine

__all__ = [
    "Stage1_CSVtoJSON",
    "Stage2_DataClean",
    "Stage3_LangGraphAgent",
    "Stage4_ColumnEngine",
]
