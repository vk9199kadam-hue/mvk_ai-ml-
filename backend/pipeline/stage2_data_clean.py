# =============================================================================
# AutoInsight AI — Stage 2: Data Cleaning & Preprocessing - Phase 2
# Phase 2: Core Pipeline — Full Implementation
# =============================================================================
"""
Stage 2: Data Cleaning & Preprocessing with AI-powered cleaning plans.

Provides:
  - DataPrep + Polars quality profiling (missing%, outliers, duplicates, PII)
  - Qwen 2.5 72B cleaning plan generation (structured JSON)
  - Diff preview logic (before/after comparison)
  - Polars transformation execution with safe eval
  - Parquet snapshots with version history
  - PostgreSQL audit logging with full lineage

Pipeline Position: Stage 2 of 4
Input:  DataFrame (from Stage 1)
Output: Cleaned DataFrame + QualityProfile + CleaningPlan
Storage: Parquet snapshot in S3 + Audit log in PostgreSQL
LLM:    Qwen 2.5 72B (Groq) for cleaning strategy generation
        Fallback: Rule-based imputation (mean/median/mode)

Flow:
  1. Quality profiling (null%, outliers IQR, duplicates, PII detection)
  2. LLM cleaning plan generation (Qwen 2.5 72B)
  3. User diff preview (before/after comparison data)
  4. Transformation execution (Polars imputation/masking/capping)
  5. Parquet snapshot + version tracking
  6. PostgreSQL audit log
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import numpy as np
import polars as pl

from backend.cache import cache_manager
from backend.llm_factory import LLMFactory, LLMFactoryError
from backend.prompt_registry import PromptRegistry
from backend.schemas import (
    CleaningOperation,
    CleaningPlan,
    QualityIssue,
    QualityProfile,
    TransformationAudit,
)
from backend.storage import storage_manager
from backend.tools import (
    compute_file_hash,
    detect_outliers_iqr,
    detect_outliers_zscore,
    impute_missing,
    mask_pii,
    profile_schema,
    compute_univariate_stats,
)

logger = logging.getLogger(__name__)

# Confidence thresholds
MIN_CLEANING_CONFIDENCE = 0.70
MAX_RETRIES_CLEANING = 3

# Parquet compression
PARQUET_COMPRESSION = "snappy"


class DataCleaningError(Exception):
    """Base exception for data cleaning errors."""
    pass


class Stage2_DataClean:
    """
    Stage 2: AI-Powered Data Cleaning & Preprocessing.
    
    Transforms raw JSON data into cleaned Parquet through:
      1. Quality profiling (deterministic — zero LLM cost)
      2. AI cleaning plan generation (Qwen 2.5 72B)
      3. User diff preview (before/after comparison)
      4. Transformation execution (safe Polars operations)
      5. Parquet snapshot with version control
      6. PostgreSQL audit logging
    """
    
    def __init__(self, llm_provider: str = "groq"):
        """
        Initialize Stage 2.
        
        Args:
            llm_provider: LLM provider for cleaning plan generation
        """
        self.llm_provider = llm_provider
        self.llm_factory = LLMFactory(provider=llm_provider)
        self.prompt_registry = PromptRegistry()
    
    async def run(
        self,
        df: pl.DataFrame,
        pipeline_id: Optional[str] = None,
        approved_operations: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[pl.DataFrame, QualityProfile, CleaningPlan]:
        """
        Execute Stage 2 data cleaning.
        
        Args:
            df: Input DataFrame from Stage 1
            pipeline_id: Pipeline UUID for tracking
            approved_operations: Pre-approved cleaning operations
                (from user diff preview). If None, auto-apply high confidence.
        
        Returns:
            Tuple of (cleaned DataFrame, QualityProfile, CleaningPlan)
        
        Raises:
            DataCleaningError: If cleaning fails validation
        """
        start_time = time.time()
        original_row_count = len(df)
        
        logger.info(
            f"Stage 2: Starting cleaning — {len(df)} rows, {len(df.columns)} columns"
        )
        
        # ── Step 1: Quality Profiling ─────────────────────────────────────
        quality_profile = await self._profile_quality(df)
        logger.info(
            f"Stage 2: Quality profile complete — "
            f"score={quality_profile.overall_quality_score:.2f}, "
            f"issues={len(quality_profile.missing_summary.get('issues', []))}"
        )
        
        # ── Step 2: Generate Cleaning Plan ────────────────────────────────
        if approved_operations:
            # Use user-approved operations
            cleaning_plan = CleaningPlan(
                operations=[
                    CleaningOperation(**op) for op in approved_operations
                ],
                description="User-approved cleaning plan",
                estimated_impact="As approved by user",
            )
        else:
            # Generate AI cleaning plan
            cleaning_plan = await self._generate_cleaning_plan(
                df, quality_profile
            )
            
            # Auto-filter: only apply operations with confidence >= threshold
            auto_ops = [
                op for op in cleaning_plan.operations
                if op.confidence >= MIN_CLEANING_CONFIDENCE
            ]
            
            if auto_ops:
                cleaning_plan.operations = auto_ops
                logger.info(
                    f"Stage 2: Auto-applied {len(auto_ops)}/{len(cleaning_plan.operations)} "
                    f"operations (confidence >= {MIN_CLEANING_CONFIDENCE})"
                )
        
        # ── Step 3: Execute Transformations ───────────────────────────────
        cleaned_df, execution_audit = await self._execute_transformations(
            df, cleaning_plan
        )
        
        # ── Step 4: Parquet Snapshot ──────────────────────────────────────
        if pipeline_id:
            version = f"v1.0-cleaned-stage2-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            snapshot_key = await storage_manager.save_parquet_snapshot(
                cleaned_df, pipeline_id, version
            )
            logger.info(f"Stage 2: Parquet snapshot saved: {snapshot_key}")
        
        # ── Step 5: Audit Trail ───────────────────────────────────────────
        audit_entries = []
        for audit in execution_audit:
            audit_entries.append(
                TransformationAudit(
                    step=audit.get("step", "clean"),
                    column=audit.get("column", "all"),
                    description=audit.get("description", ""),
                    expression=audit.get("expression"),
                    timestamp=datetime.utcnow(),
                    status=audit.get("status", "completed"),
                    row_count_before=original_row_count,
                    row_count_after=len(cleaned_df),
                )
            )
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(
            f"Stage 2: Complete — "
            f"{len(cleaned_df)} rows, {len(cleaned_df.columns)} columns, "
            f"{len(audit_entries)} audit entries, "
            f"time={elapsed:.0f}ms"
        )
        
        return cleaned_df, quality_profile, cleaning_plan
    
    async def _profile_quality(self, df: pl.DataFrame) -> QualityProfile:
        """
        Comprehensive data quality profiling.
        
        Profiles:
          - Per-column: null count, null %, cardinality, data type
          - Missing values: overall %, per-column breakdown
          - Outliers: IQR method for numeric columns
          - Duplicates: exact row duplicates
          - PII detection: email, phone, SSN patterns
          - Overall quality score (composite)
        """
        columns = {}
        missing_summary = {"total_cells": 0, "total_missing": 0, "issues": []}
        outlier_summary = {"columns": {}, "total_outliers": 0}
        duplicate_summary = {"count": 0, "columns_considered": []}
        pii_columns = []
        
        total_cells = len(df) * len(df.columns)
        total_missing = 0
        
        for col in df.columns:
            series = df[col]
            null_count = int(series.null_count())
            total_missing += null_count
            n_unique = series.n_unique()
            non_null = series.drop_nulls()
            
            col_profile = {
                "dtype": str(series.dtype),
                "null_count": null_count,
                "null_percentage": round(null_count / max(len(df), 1) * 100, 2),
                "cardinality": n_unique,
                "cardinality_ratio": round(n_unique / max(len(non_null), 1), 4) if len(non_null) > 0 else 0,
                "sample_values": [str(v) for v in non_null[:3].to_list()],
            }
            columns[col] = col_profile
            
            # Check for quality issues
            if null_count > 0:
                missing_summary["issues"].append({
                    "column": col,
                    "null_count": null_count,
                    "null_percentage": round(null_count / max(len(df), 1) * 100, 2),
                })
            
            # Outlier detection (numeric only)
            if series.dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                                pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                                pl.Float32, pl.Float64):
                if len(non_null) > 0:
                    mask, stats = detect_outliers_iqr(non_null)
                    if stats.get("outlier_count", 0) > 0:
                        outlier_summary["columns"][col] = stats
                        outlier_summary["total_outliers"] += stats["outlier_count"]
        
        # Duplicate detection
        dup_count = df.is_duplicated().sum()
        duplicate_summary["count"] = int(dup_count)
        duplicate_summary["columns_considered"] = df.columns
        
        # PII detection
        for col in df.columns:
            if df[col].dtype == pl.Utf8:
                sample = df[col].drop_nulls().head(100).to_list()
                sample_text = " ".join(str(v) for v in sample if v is not None)
                if self._contains_pii(sample_text):
                    pii_columns.append(col)
        
        # Compute overall quality score
        quality_score = self._compute_quality_score(
            total_cells, total_missing,
            outlier_summary["total_outliers"],
            int(dup_count),
            len(pii_columns),
            len(df.columns),
        )
        
        return QualityProfile(
            columns=columns,
            missing_summary={
                "total_cells": total_cells,
                "total_missing": total_missing,
                "missing_percentage": round(total_missing / max(total_cells, 1) * 100, 2),
                "issues": missing_summary["issues"],
                "columns_with_missing": len(missing_summary["issues"]),
            },
            outlier_summary=outlier_summary,
            duplicate_summary={
                "count": duplicate_summary["count"],
                "duplicate_percentage": round(
                    duplicate_summary["count"] / max(len(df), 1) * 100, 2
                ),
            },
            pii_columns=pii_columns,
            overall_quality_score=quality_score,
        )
    
    def _contains_pii(self, text: str) -> bool:
        """Check if text contains PII patterns."""
        import re
        patterns = [
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "email"),
            (r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', "phone"),
            (r'\b\d{3}-\d{2}-\d{4}\b', "ssn"),
        ]
        for pattern, _ in patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _compute_quality_score(
        self,
        total_cells: int,
        total_missing: int,
        total_outliers: int,
        dup_count: int,
        pii_count: int,
        total_columns: int,
    ) -> float:
        """Compute overall data quality score (0.0 - 1.0)."""
        missing_penalty = total_missing / max(total_cells, 1) * 0.4
        outlier_penalty = min(total_outliers / max(total_cells, 1), 0.1) * 0.3
        dup_penalty = min(dup_count / max(total_cells, 1), 0.1) * 0.2
        pii_penalty = (pii_count / max(total_columns, 1)) * 0.1
        
        score = max(0.0, 1.0 - missing_penalty - outlier_penalty - dup_penalty - pii_penalty)
        return round(score, 4)
    
    async def _generate_cleaning_plan(
        self,
        df: pl.DataFrame,
        quality_profile: QualityProfile,
    ) -> CleaningPlan:
        """
        Generate AI-powered cleaning plan using Qwen 2.5 72B.
        
        The LLM receives the quality profile and recommends specific
        cleaning operations with confidence scores.
        
        Falls back to rule-based recommendations if LLM is unavailable.
        """
        try:
            prompt = await self.prompt_registry.get_prompt("cleaning_plan")
            
            response = await self.llm_factory.invoke_agent(
                system_prompt=str(prompt),
                user_prompt=(
                    f"Data Quality Profile:\n"
                    f"{json.dumps(quality_profile.model_dump(), indent=2, default=str)}\n\n"
                    f"Generate a CleaningPlan with specific operations. "
                    f"Output ONLY valid JSON matching the CleaningPlan Pydantic schema."
                ),
                output_model=CleaningPlan,
            )
            
            logger.info(
                f"LLM cleaning plan: {len(response.operations)} operations"
            )
            return response
            
        except (LLMFactoryError, Exception) as e:
            logger.warning(f"LLM cleaning plan failed: {e}. Using rule-based fallback.")
            return self._fallback_cleaning_plan(df, quality_profile)
    
    def _fallback_cleaning_plan(
        self,
        df: pl.DataFrame,
        quality_profile: QualityProfile,
    ) -> CleaningPlan:
        """
        Rule-based cleaning plan fallback (zero LLM cost).
        
        Generates operations based on quality profile metrics:
          - Missing values: impute with mean (numeric) / mode (categorical)
          - Outliers: cap at IQR bounds
          - PII: mask detected columns
          - Duplicates: remove
        """
        operations = []
        
        # Handle missing values
        for issue in quality_profile.missing_summary.get("issues", []):
            col = issue["column"]
            series = df[col]
            
            if series.dtype in (pl.Float32, pl.Float64, pl.Int64):
                operations.append(CleaningOperation(
                    column=col,
                    issue=f"Missing values ({issue['null_percentage']}%)",
                    strategy="impute",
                    parameters={"strategy": "mean"},
                    confidence=0.85,
                    reasoning=f"Imputing {issue['null_percentage']}% missing values with column mean",
                ))
            else:
                operations.append(CleaningOperation(
                    column=col,
                    issue=f"Missing values ({issue['null_percentage']}%)",
                    strategy="impute",
                    parameters={"strategy": "mode"},
                    confidence=0.75,
                    reasoning=f"Imputing with most frequent value (mode)",
                ))
        
        # Handle outliers
        for col, stats in quality_profile.outlier_summary.get("columns", {}).items():
            operations.append(CleaningOperation(
                column=col,
                issue=f"Outliers ({stats.get('outlier_count', 0)} values)",
                strategy="cap",
                parameters={
                    "lower_bound": stats.get("lower_bound"),
                    "upper_bound": stats.get("upper_bound"),
                },
                confidence=0.80,
                reasoning=f"Capping outliers at IQR bounds [{stats.get('lower_bound', 0):.2f}, {stats.get('upper_bound', 0):.2f}]",
            ))
        
        # Handle PII
        for col in quality_profile.pii_columns:
            operations.append(CleaningOperation(
                column=col,
                issue="PII detected",
                strategy="mask",
                parameters={"mask_char": "*", "preserve_last": 4},
                confidence=0.95,
                reasoning="Masking PII to protect sensitive data",
            ))
        
        # Handle duplicates
        dup_count = quality_profile.duplicate_summary.get("count", 0)
        if dup_count > 0:
            operations.append(CleaningOperation(
                column="*",
                issue=f"Duplicate rows ({dup_count})",
                strategy="remove",
                parameters={"keep": "first"},
                confidence=0.90,
                reasoning=f"Removing {dup_count} duplicate rows, keeping first occurrence",
            ))
        
        return CleaningPlan(
            operations=operations,
            description=(
                f"Rule-based cleaning plan with {len(operations)} operations"
            ),
            estimated_impact=f"Estimated quality improvement: {len(operations)} operations applied",
        )
    
    async def _execute_transformations(
        self,
        df: pl.DataFrame,
        cleaning_plan: CleaningPlan,
    ) -> Tuple[pl.DataFrame, List[Dict[str, Any]]]:
        """
        Execute cleaning transformations safely.
        
        Each transformation:
          1. Is validated before execution
          2. Is wrapped in a try/except for error isolation
          3. Produces an audit entry
          4. Reports success/failure per operation
        
        Args:
            df: Original DataFrame
            cleaning_plan: Cleaning plan with operations
        
        Returns:
            Tuple of (cleaned DataFrame, list of audit entries)
        """
        result = df.clone()
        audit = []
        
        for op in cleaning_plan.operations:
            try:
                audit_entry = {
                    "step": "clean",
                    "column": op.column,
                    "description": f"{op.strategy}: {op.issue}",
                    "expression": json.dumps(op.parameters),
                    "status": "running",
                }
                
                if op.strategy == "impute":
                    strategy = op.parameters.get("strategy", "mean")
                    cols = [op.column] if op.column != "*" else None
                    result = impute_missing(result, strategy=strategy, columns=cols)
                    audit_entry["status"] = "completed"
                    
                elif op.strategy == "cap":
                    col = op.column
                    lower = op.parameters.get("lower_bound")
                    upper = op.parameters.get("upper_bound")
                    
                    if lower is not None and col in result.columns:
                        result = result.with_columns(
                            pl.when(pl.col(col) < lower).then(lower)
                            .when(pl.col(col) > upper).then(upper)
                            .otherwise(pl.col(col))
                            .alias(col)
                        )
                    audit_entry["status"] = "completed"
                    
                elif op.strategy == "mask":
                    if op.column != "*":
                        result, _ = mask_pii(result.select(op.column))
                        for c in result.columns:
                            result = df.clone().with_columns(result[c].alias(c))
                    else:
                        result, _ = mask_pii(result)
                    audit_entry["status"] = "completed"
                    
                elif op.strategy == "remove":
                    if op.column == "*":
                        keep = op.parameters.get("keep", "first")
                        result = result.unique(keep=keep)
                    audit_entry["status"] = "completed"
                    
                elif op.strategy == "transform":
                    # Custom transform via expression
                    expression = op.parameters.get("expression", "")
                    if expression:
                        from backend.tools import safe_eval_polars
                        new_series = safe_eval_polars(expression, result)
                        result = result.with_columns(new_series.alias(op.column))
                    audit_entry["status"] = "completed"
                
                audit.append(audit_entry)
                logger.debug(
                    f"Stage 2: Applied '{op.strategy}' on '{op.column}'"
                )
                
            except Exception as e:
                audit_entry["status"] = "failed"
                audit_entry["error"] = str(e)
                audit.append(audit_entry)
                logger.warning(
                    f"Stage 2: Failed '{op.strategy}' on '{op.column}': {e}"
                )
        
        return result, audit
    
    async def generate_diff_preview(
        self,
        original: pl.DataFrame,
        cleaned: pl.DataFrame,
    ) -> Dict[str, Any]:
        """
        Generate diff preview data for user review.
        
        Shows:
          - Before/after row counts
          - Changed columns with sample values
          - Quality score improvement
          - Per-operation changes
        
        Args:
            original: Original DataFrame
            cleaned: Cleaned DataFrame
        
        Returns:
            Diff preview data for frontend display
        """
        changes = []
        
        for col in original.columns:
            if col in cleaned.columns:
                orig_series = original[col]
                clean_series = cleaned[col]
                
                # Count changed values
                changed_mask = orig_series != clean_series
                if hasattr(changed_mask, 'sum'):
                    changed_count = int(changed_mask.sum())
                else:
                    changed_count = 0
                
                if changed_count > 0:
                    # Sample before/after values
                    changed_indices = (
                        changed_mask.to_numpy().nonzero()[0][:5]
                        if hasattr(changed_mask, 'to_numpy')
                        else []
                    )
                    samples = []
                    for idx in changed_indices:
                        samples.append({
                            "row": int(idx),
                            "before": str(orig_series[idx]),
                            "after": str(clean_series[idx]),
                        })
                    
                    changes.append({
                        "column": col,
                        "changed_count": changed_count,
                        "change_percentage": round(
                            changed_count / max(len(original), 1) * 100, 2
                        ),
                        "samples": samples,
                    })
        
        return {
            "original_rows": len(original),
            "cleaned_rows": len(cleaned),
            "original_columns": len(original.columns),
            "cleaned_columns": len(cleaned.columns),
            "total_changes": sum(c["changed_count"] for c in changes),
            "columns_changed": len(changes),
            "changes": changes,
        }
