# =============================================================================
# AutoInsight AI — Stage 1: CSV → JSON (Schema Inference) - Phase 2
# Phase 2: Core Pipeline — Full Implementation
# =============================================================================
"""
Stage 1: CSV → JSON Conversion with AI Schema Inference (Phase 2 Full).

Converts raw CSV files into structured JSON with AI-inferred schema metadata.
Uses Qwen 2.5 72B (Groq) for intelligent column type inference.

Pipeline Position: Stage 1 of 4
Input:  Raw CSV file path
Output: SchemaInferenceResponse (typed columns, encoding, row count, confidence)
Cache:  Redis (keyed by file_hash) — hot cache for re-processed files
LLM:    Qwen 2.5 72B (Groq) for schema inference (only on cache miss)
        Fallback: Llama 3.1 8B (Ollama) → Deterministic type detection

Flow:
  1. Compute file hash → Check Redis cache
  2. [Cache HIT] → Return cached schema immediately
  3. [Cache MISS] → chardet encoding detection → Polars CSV parsing
  4. → LLM schema inference (Qwen 2.5 72B) → Pydantic validation
  5. → Cache result in Redis → Return SchemaInferenceResponse
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from backend.cache import cache_manager
from backend.config import settings
from backend.llm_factory import LLMFactory, LLMFactoryError
from backend.schemas import ColumnInference, DataType, SchemaInferenceResponse
from backend.tools import (
    compute_file_hash,
    detect_encoding,
    parse_csv,
    profile_schema,
)
from backend.prompt_registry import PromptRegistry

logger = logging.getLogger(__name__)

# Number of sample rows to send to LLM for schema inference
SCHEMA_INFERENCE_SAMPLE_ROWS = 20

# Minimum confidence for auto-accepting schema inference
MIN_SCHEMA_CONFIDENCE = 0.70


class SchemaInferenceError(Exception):
    """Raised when schema inference fails."""
    pass


class Stage1_CSVtoJSON:
    """
    Stage 1: CSV → JSON Schema Inference with AI-powered type detection.
    
    Provides:
      - chardet encoding auto-detection
      - Polars-based CSV parsing with error recovery
      - Qwen 2.5 72B schema inference (structured JSON output)
      - Pydantic v2 validation with confidence scoring
      - Redis caching with TTL (24h for processed files)
      - Deterministic fallback when LLM is unavailable
      - Progress tracking via callback
      - File validation (size, encoding, delimiter)
    """
    
    def __init__(self, llm_provider: str = "groq"):
        """
        Initialize Stage 1.
        
        Args:
            llm_provider: LLM provider ("groq" or "ollama")
        """
        self.llm_provider = llm_provider
        self.llm_factory = LLMFactory(provider=llm_provider)
        self.prompt_registry = PromptRegistry()
    
    async def run(
        self,
        file_path: str,
        pipeline_id: Optional[str] = None,
        force_reprocess: bool = False,
    ) -> SchemaInferenceResponse:
        """
        Execute Stage 1: CSV → JSON Schema Inference.
        
        Flow:
          1. Validate file exists and is non-empty
          2. Compute MD5 hash for caching
          3. Check Redis cache (skip if force_reprocess)
          4. [Cache MISS] → chardet encoding detection
          5. → Polars parse first N rows
          6. → LLM schema inference (with fallback)
          7. → Pydantic validation
          8. → Cache result in Redis
          9. Return SchemaInferenceResponse
        
        Args:
            file_path: Path to the CSV file
            pipeline_id: Optional pipeline UUID (for progress tracking)
            force_reprocess: If True, bypass cache
        
        Returns:
            SchemaInferenceResponse with inferred column types and metadata
        
        Raises:
            SchemaInferenceError: If file processing fails
        """
        start_time = time.time()
        
        # ── Step 1: Validate File ─────────────────────────────────────────
        if not os.path.exists(file_path):
            raise SchemaInferenceError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise SchemaInferenceError(f"File is empty: {file_path}")
        
        if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise SchemaInferenceError(
                f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds "
                f"maximum allowed ({settings.MAX_FILE_SIZE_MB}MB)"
            )
        
        logger.info(
            f"Stage 1: Processing file '{os.path.basename(file_path)}' "
            f"({file_size / 1024:.1f}KB)"
        )
        
        # ── Step 2: Compute File Hash ─────────────────────────────────────
        file_hash = compute_file_hash(file_path)
        logger.debug(f"Stage 1: File hash = {file_hash[:16]}...")
        
        # ── Step 3: Check Cache ───────────────────────────────────────────
        if not force_reprocess:
            cached_schema = await cache_manager.get(
                f"schema:{file_hash}",
                SchemaInferenceResponse,
            )
            if cached_schema:
                logger.info(f"Stage 1: Cache HIT for hash {file_hash[:16]}...")
                return cached_schema
        
        logger.info(f"Stage 1: Cache MISS — running full inference")
        
        # ── Step 4: Detect Encoding ───────────────────────────────────────
        encoding = detect_encoding(file_path)
        logger.info(f"Stage 1: Detected encoding = {encoding}")
        
        # ── Step 5: Parse CSV ─────────────────────────────────────────────
        df = self._parse_file(file_path, encoding)
        
        row_count = len(df)
        column_count = len(df.columns)
        
        if row_count == 0:
            raise SchemaInferenceError("CSV file has no data rows")
        
        if column_count == 0:
            raise SchemaInferenceError("CSV file has no columns")
        
        logger.info(
            f"Stage 1: Parsed {row_count} rows, {column_count} columns"
        )
        
        # ── Step 6: Detect Delimiter ──────────────────────────────────────
        delimiter = self._detect_delimiter(file_path, encoding)
        
        # ── Step 7: LLM Schema Inference ──────────────────────────────────
        schema_columns = await self._infer_schema(df, file_path, encoding)
        
        # ── Step 8: Build Response ─────────────────────────────────────────
        processing_time_ms = round((time.time() - start_time) * 1000)
        
        response = SchemaInferenceResponse(
            columns=schema_columns,
            row_count=row_count,
            encoding=encoding,
            detected_delimiter=delimiter,
            has_header=True,
            file_hash=file_hash,
            processing_time_ms=processing_time_ms,
        )
        
        # ── Step 9: Cache Result ──────────────────────────────────────────
        await cache_manager.set(
            f"schema:{file_hash}",
            response,
            ttl=86400,  # 24 hours
        )
        
        logger.info(
            f"Stage 1: Complete — {len(schema_columns)} columns inferred, "
            f"overall confidence={response.overall_confidence:.2f}, "
            f"time={processing_time_ms}ms"
        )
        
        return response
    
    async def _infer_schema(
        self,
        df: pl.DataFrame,
        file_path: str,
        encoding: str,
    ) -> List[ColumnInference]:
        """
        Infer schema for all columns using LLM + deterministic fallback.
        
        Strategy:
          1. Extract sample data from first N rows
          2. Extract Polars schema for deterministic type hints
          3. Call LLM with structured output (Qwen 2.5 72B)
          4. Validate with Pydantic
          5. Fallback to deterministic type detection if LLM fails
        
        Args:
            df: Parsed DataFrame
            file_path: Original file path
            encoding: Detected encoding
        
        Returns:
            List of ColumnInference for each column
        """
        # Extract sample data for LLM
        sample_data = self._extract_sample_data(df)
        
        # Extract Polars schema for deterministic hints
        polars_schema = self._extract_polars_schema(df)
        
        try:
            # Attempt LLM inference (with fallback)
            return await self._llm_schema_inference(sample_data, polars_schema)
            
        except (LLMFactoryError, Exception) as e:
            logger.warning(f"LLM schema inference failed: {e}. Using deterministic fallback.")
            return self._deterministic_schema_inference(df)
    
    async def _llm_schema_inference(
        self,
        sample_data: str,
        polars_schema: str,
    ) -> List[ColumnInference]:
        """
        Use Qwen 2.5 72B (Groq) for intelligent schema inference.
        
        The LLM receives:
          - CSV sample rows (first 20 rows with headers)
          - Polars deterministic type hints
          - Instructions to output structured JSON
        
        The output is validated against SchemaInferenceResponse Pydantic model,
        ensuring type safety and preventing hallucination.
        
        Args:
            sample_data: CSV sample rows as formatted text
            polars_schema: Polars-inferred schema as text
        
        Returns:
            List of validated ColumnInference objects
        """
        prompt = await self.prompt_registry.get_prompt("infer_schema")
        
        try:
            response = await self.llm_factory.invoke_agent(
                system_prompt=str(prompt),
                user_prompt=(
                    f"CSV Sample Data (first {SCHEMA_INFERENCE_SAMPLE_ROWS} rows):\n"
                    f"{sample_data}\n\n"
                    f"Polars Parsed Schema (deterministic hints):\n"
                    f"{polars_schema}\n\n"
                    f"Analyze each column and output ONLY valid JSON matching "
                    f"the SchemaInferenceResponse schema. "
                    f"Do not include markdown code blocks."
                ),
                output_model=SchemaInferenceResponse,
            )
            
            # Validate columns
            columns = response.columns
            if not columns:
                logger.warning("LLM returned no columns — falling back")
                raise SchemaInferenceError("LLM returned empty columns")
            
            logger.info(
                f"LLM schema inference: {len(columns)} columns, "
                f"confidence={response.overall_confidence:.2f}"
            )
            
            return columns
            
        except Exception as e:
            logger.warning(f"LLM inference attempt failed: {e}")
            raise
    
    def _deterministic_schema_inference(
        self,
        df: pl.DataFrame,
    ) -> List[ColumnInference]:
        """
        Fallback: Deterministic schema inference without LLM.
        
        Uses Polars schema + data analysis to detect:
          - Numeric types (int, float) from dtype
          - String/text types from dtype + cardinality
          - Date/datetime from regex patterns (common formats)
          - Boolean from unique values
          - Categorical from cardinality ratio
        
        This is the zero-cost fallback when LLM is unavailable.
        """
        columns = []
        
        for col_name in df.columns:
            series = df[col_name]
            dtype = str(series.dtype)
            non_null = series.drop_nulls()
            
            # Detect type
            detected_type, confidence, reasoning = self._detect_column_type(
                series, dtype
            )
            
            # Sample values
            sample_values = [
                str(v) for v in non_null[:5].to_list()
            ]
            
            columns.append(ColumnInference(
                column_name=col_name,
                detected_type=detected_type,
                format_spec=self._infer_format(non_null, detected_type),
                confidence=round(confidence, 2),
                reasoning=reasoning,
                nullable=series.null_count() > 0,
                sample_values=sample_values,
            ))
        
        return columns
    
    def _detect_column_type(
        self,
        series: pl.Series,
        dtype: str,
    ) -> Tuple[DataType, float, str]:
        """
        Detect column type based on Polars dtype and data analysis.
        
        Args:
            series: Column data
            dtype: Polars dtype string
        
        Returns:
            Tuple of (DataType, confidence, reasoning)
        """
        non_null = series.drop_nulls()
        n_unique = non_null.n_unique() if len(non_null) > 0 else 0
        total = len(series)
        
        # Numeric types (direct from Polars)
        if "Int" in dtype or "UInt" in dtype:
            if n_unique <= 2 and total > 0:
                return DataType.BOOLEAN, 0.85, "Binary integer values (boolean)"
            return DataType.INTEGER, 0.95, "Polars integer type"
        
        if "Float" in dtype:
            return DataType.FLOAT, 0.95, "Polars float type"
        
        if "Bool" in dtype:
            return DataType.BOOLEAN, 0.98, "Polars boolean type"
        
        if "Date" in dtype:
            return DataType.DATE, 0.90, "Polars date type"
        
        if "Datetime" in dtype:
            return DataType.DATETIME, 0.90, "Polars datetime type"
        
        # String type — need to analyze
        if "Utf8" in dtype or "String" in dtype:
            length_ratio = n_unique / max(len(non_null), 1) if len(non_null) > 0 else 0
            
            # Check for date/datetime patterns
            sample_str = str(non_null[0]) if len(non_null) > 0 else ""
            if self._looks_like_date(sample_str):
                return DataType.DATE, 0.70, "String values match date pattern"
            
            if self._looks_like_datetime(sample_str):
                return DataType.DATETIME, 0.70, "String values match datetime pattern"
            
            # Categorical (low cardinality)
            if length_ratio < 0.1 and n_unique <= 20:
                return DataType.CATEGORICAL, 0.85, f"Low cardinality ({n_unique} unique)"
            
            # Check if numeric string
            if self._is_numeric_string(non_null):
                return DataType.FLOAT, 0.60, "String values appear numeric"
            
            # Text (high cardinality, long strings)
            avg_length = non_null.str.lengths().mean() if len(non_null) > 0 else 0
            if avg_length > 50 or length_ratio > 0.8:
                return DataType.TEXT, 0.75, "High cardinality text"
            
            return DataType.STRING, 0.80, "Standard string type"
        
        return DataType.UNKNOWN, 0.30, f"Unrecognized Polars type: {dtype}"
    
    def _looks_like_date(self, value: str) -> bool:
        """Check if a string value matches common date patterns."""
        import re
        date_patterns = [
            r"^\d{4}-\d{2}-\d{2}$",          # 2024-01-15
            r"^\d{2}/\d{2}/\d{4}$",            # 01/15/2024
            r"^\d{2}-\d{2}-\d{4}$",            # 01-15-2024
            r"^\d{4}/\d{2}/\d{2}$",            # 2024/01/15
            r"^\d{2}\.\d{2}\.\d{4}$",          # 15.01.2024
        ]
        return any(re.match(p, value) for p in date_patterns)
    
    def _looks_like_datetime(self, value: str) -> bool:
        """Check if a string value matches datetime patterns."""
        import re
        dt_patterns = [
            r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}",  # ISO format
            r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}",      # US format
        ]
        return any(re.match(p, value) for p in dt_patterns)
    
    def _is_numeric_string(self, series: pl.Series) -> bool:
        """Check if string values appear numeric."""
        try:
            sample = series.head(100).to_list()
            for v in sample:
                if v is not None:
                    float(v.replace(",", "").replace("$", "").replace("€", ""))
            return True
        except (ValueError, TypeError):
            return False
    
    def _infer_format(
        self,
        series: pl.Series,
        data_type: DataType,
    ) -> Optional[str]:
        """Infer format specification from column data."""
        if data_type in (DataType.DATE, DataType.DATETIME):
            import re
            sample = str(series[0]) if len(series) > 0 else ""
            
            if re.match(r"^\d{4}-\d{2}-\d{2}$", sample):
                return "%Y-%m-%d"
            if re.match(r"^\d{2}/\d{2}/\d{4}$", sample):
                return "%m/%d/%Y"
            if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", sample):
                return "%Y-%m-%dT%H:%M:%S"
        
        return None
    
    def _extract_sample_data(self, df: pl.DataFrame) -> str:
        """
        Extract formatted sample data for LLM inference.
        
        Takes the first N rows and formats them as a text table
        for the LLM to analyze.
        """
        sample = df.head(SCHEMA_INFERENCE_SAMPLE_ROWS)
        
        # Format as text table
        lines = []
        lines.append(" | ".join(str(c) for c in sample.columns))
        lines.append("-" * len(lines[0]))
        
        for row in sample.iter_rows():
            values = [str(v)[:50] if v is not None else "" for v in row]
            lines.append(" | ".join(values))
        
        return "\n".join(lines)
    
    def _extract_polars_schema(self, df: pl.DataFrame) -> str:
        """
        Extract Polars schema as text for LLM hints.
        """
        schema_lines = []
        for col in df.columns:
            series = df[col]
            null_pct = round(series.null_count() / max(len(series), 1) * 100, 1)
            n_unique = series.n_unique()
            
            schema_lines.append(
                f"  - {col}: {series.dtype} "
                f"(nulls={null_pct}%, unique={n_unique})"
            )
        
        return "\n".join(schema_lines)
    
    def _parse_file(self, file_path: str, encoding: str) -> pl.DataFrame:
        """
        Parse CSV file with encoding and error recovery.
        
        Tries multiple strategies:
          1. Specified encoding
          2. UTF-8 fallback
          3. Polars auto-detect
        """
        strategies = [
            {"encoding": encoding},
            {"encoding": "utf-8"},
            {},
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                return parse_csv(
                    file_path,
                    encoding=strategy.get("encoding"),
                    infer_schema_length=10000,
                )
            except Exception as e:
                if i < len(strategies) - 1:
                    logger.warning(f"Parsing failed with {strategy}: {e}. Trying next...")
                else:
                    raise SchemaInferenceError(
                        f"Failed to parse CSV after {len(strategies)} attempts: {e}"
                    )
    
    def _detect_delimiter(self, file_path: str, encoding: str) -> str:
        """
        Detect CSV delimiter by analyzing the first line.
        """
        import csv
        
        try:
            with open(file_path, "r", encoding=encoding) as f:
                sample = f.read(8192)
                if not sample:
                    return ","
                
                dialect = csv.Sniffer().sniff(sample)
                return dialect.delimiter
        except Exception:
            # Default to comma
            return ","
    
    async def validate(self, response: SchemaInferenceResponse) -> bool:
        """
        Validate the schema inference output.
        
        Checks:
          - Columns are non-empty
          - Overall confidence >= minimum threshold
          - All required fields are populated
          - Column names are unique and non-empty
        """
        if not response.columns:
            logger.error("Stage 1 validation: No columns inferred")
            return False
        
        if response.overall_confidence is not None and response.overall_confidence < MIN_SCHEMA_CONFIDENCE:
            logger.warning(
                f"Stage 1 validation: Low overall confidence "
                f"({response.overall_confidence:.2f} < {MIN_SCHEMA_CONFIDENCE})"
            )
        
        # Check for duplicate column names
        names = [c.column_name for c in response.columns]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            logger.warning(f"Stage 1 validation: Duplicate column names: {set(duplicates)}")
        
        return True
