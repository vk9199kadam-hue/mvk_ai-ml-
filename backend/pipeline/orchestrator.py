# =============================================================================
# AutoInsight AI — Pipeline Orchestrator (pipeline/orchestrator.py)
# Phase 2: Core Pipeline — End-to-End Pipeline Controller
# =============================================================================
"""
Pipeline orchestrator that coordinates the full 4-stage data pipeline.

Manages:
  - Sequential stage execution with state passing
  - Celery async task lifecycle
  - Progress tracking with SSE events
  - Error handling with retry logic
  - Caching between stages
  - Audit trail collection

Execution Flow:
  run_pipeline(file_path)
    ├── Stage 1: CSV → JSON (SchemaInferenceResponse)
    │     Input:  Raw CSV file
    │     Output: SchemaInferenceResponse + Structured JSON
    │     Cache:  Redis (file_hash)
    │
    ├── Stage 2: Data Cleaning (Cleaned DataFrame)
    │     Input:  Structured JSON
    │     Output: Cleaned Parquet + QualityProfile
    │     Cache:  Redis + S3 Parquet snapshot
    │
    ├── Stage 3: LangGraph Agent (UnifiedDataModel)
    │     Input:  Cleaned Parquet
    │     Output: UnifiedDataModel with relationships
    │     Cache:  Redis (UDM)
    │
    └── Stage 4: Column Engineering (Complete UDM)
          Input:  UnifiedDataModel
          Output: Complete UDM + Viz Schema
          Cache:  S3 + PostgreSQL

Usage:
    from backend.pipeline.orchestrator import PipelineOrchestrator
    
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run_pipeline("file_path.csv", "pipeline-uuid")
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from uuid import uuid4

import polars as pl

from backend.cache import cache_manager
from backend.pipeline.progress import ProgressTracker, StageContext
from backend.pipeline.stage1_csv_to_json import Stage1_CSVtoJSON
from backend.pipeline.stage2_data_clean import Stage2_DataClean
from backend.pipeline.stage3_langgraph_agent import Stage3_LangGraphAgent
from backend.pipeline.stage4_column_engine import Stage4_ColumnEngine
from backend.schemas import (
    CleaningPlan,
    PipelineResult,
    PipelineStatus,
    QualityProfile,
    SchemaInferenceResponse,
    TransformationAudit,
    UnifiedDataModel,
)
from backend.database import insert_one, serialize_model
from backend.storage import storage_manager

logger = logging.getLogger(__name__)

# Maximum retries per stage
MAX_STAGE_RETRIES = 3

# Retry delay in seconds (exponential backoff base)
RETRY_BASE_DELAY = 2


class PipelineError(Exception):
    """Base exception for pipeline errors."""
    pass


class StageError(PipelineError):
    """Raised when a specific stage fails after retries."""
    def __init__(self, stage_num: int, stage_name: str, error: str, retries: int):
        self.stage_num = stage_num
        self.stage_name = stage_name
        self.retries = retries
        super().__init__(f"Stage {stage_num} ({stage_name}) failed after {retries} retries: {error}")


class PipelineOrchestrator:
    """
    Coordinates the full 4-stage data pipeline execution.
    
    Features:
      - Sequential stage execution with progress tracking
      - Automatic retry with exponential backoff (max 3)
      - Redis cache check to skip re-processing cached files
      - S3 Parquet snapshots between stages
      - Complete audit trail collection
      - SSE event streaming for real-time frontend updates
    """
    
    def __init__(self, llm_provider: str = "groq"):
        """
        Initialize the orchestrator.
        
        Args:
            llm_provider: LLM provider to use ("groq" or "ollama")
        """
        self.llm_provider = llm_provider
        
        # Initialize stages
        self.stage1 = Stage1_CSVtoJSON(llm_provider=llm_provider)
        self.stage2 = Stage2_DataClean(llm_provider=llm_provider)
        self.stage3 = Stage3_LangGraphAgent(llm_provider=llm_provider)
        self.stage4 = Stage4_ColumnEngine()
        
        # Audit trail
        self.audit_trail: List[Dict[str, Any]] = []
    
    async def run_pipeline(
        self,
        file_path: str,
        pipeline_id: Optional[str] = None,
        skip_cleaning: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute the complete 4-stage pipeline.
        
        Args:
            file_path: Path to the CSV file to process
            pipeline_id: Optional pipeline UUID (auto-generated if None)
            skip_cleaning: If True, skip Stage 2 (for already-clean data)
        
        Returns:
            PipelineResult containing the complete UnifiedDataModel
        
        Raises:
            PipelineError: If any stage fails after all retries
        """
        pipeline_id = pipeline_id or str(uuid4())
        start_time = time.time()
        
        tracker = ProgressTracker(pipeline_id)
        stages_completed = []
        
        logger.info(
            f"╔══════════════════════════════════════════════════╗\n"
            f"║  Pipeline started: {pipeline_id[:8]}...                  ║\n"
            f"║  File: {file_path}                             ║\n"
            f"║  LLM: {self.llm_provider}                                    ║\n"
            f"╚══════════════════════════════════════════════════╝"
        )
        
        try:
            # ── Stage 1: CSV → JSON Schema Inference ─────────────────────
            schema_response = await self._run_stage_with_retry(
                stage_num=1,
                stage_name="CSV → JSON Schema Inference",
                tracker=tracker,
                fn=self._stage1_execute,
                file_path=file_path,
                pipeline_id=pipeline_id,
            )
            stages_completed.append("CSV → JSON")
            
            # Parse the CSV fully (now that we have schema info)
            df = self._parse_csv_with_schema(file_path, schema_response)
            
            # ── Stage 2: Data Cleaning ───────────────────────────────────-
            if not skip_cleaning:
                df, quality_profile, cleaning_plan = await self._run_stage_with_retry(
                    stage_num=2,
                    stage_name="Data Cleaning & Preprocessing",
                    tracker=tracker,
                    fn=self._stage2_execute,
                    df=df,
                    pipeline_id=pipeline_id,
                    tracker=tracker,
                )
                stages_completed.append("Data Cleaning")
            else:
                logger.info("Stage 2 skipped (skip_cleaning=True)")
                tracker.stages[2]["status"] = "skipped"
                stages_completed.append("Data Cleaning (skipped)")
            
            # ── Stage 3: LangGraph Agent ─────────────────────────────────
            unified_data_model = await self._run_stage_with_retry(
                stage_num=3,
                stage_name="LangGraph Relationship Discovery",
                tracker=tracker,
                fn=self._stage3_execute,
                df=df,
                tracker=tracker,
            )
            stages_completed.append("LangGraph Agent")
            
            # ── Stage 4: Column Engineering ──────────────────────────────
            complete_udm = await self._run_stage_with_retry(
                stage_num=4,
                stage_name="Column Engineering & UDM Assembly",
                tracker=tracker,
                fn=self._stage4_execute,
                df=df,
                udm=unified_data_model,
                tracker=tracker,
            )
            stages_completed.append("Column Engineering")
            
            # ── Finalize ──────────────────────────────────────────────────
            total_time_ms = (time.time() - start_time) * 1000
            
            # Persist result
            await self._persist_result(
                pipeline_id, complete_udm, stages_completed, total_time_ms
            )
            
            await tracker.complete_stage("completed")
            
            logger.info(
                f"╔══════════════════════════════════════════════════╗\n"
                f"║  Pipeline completed: {pipeline_id[:8]}...               ║\n"
                f"║  Duration: {total_time_ms:.0f}ms                               ║\n"
                f"║  Stages: {len(stages_completed)}/4 completed                      ║\n"
                f"╚══════════════════════════════════════════════════╝"
            )
            
            return PipelineResult(
                pipeline_id=pipeline_id,
                status=PipelineStatus.COMPLETED,
                unified_data_model=complete_udm,
                stages_completed=stages_completed,
                total_processing_time_ms=round(total_time_ms),
            ).model_dump()
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Pipeline failed: {error_msg}")
            
            await tracker.fail_stage(error_msg)
            
            # Persist failure
            await self._persist_failure(pipeline_id, error_msg, stages_completed)
            
            raise PipelineError(error_msg)
    
    async def _run_stage_with_retry(
        self,
        stage_num: int,
        stage_name: str,
        tracker: ProgressTracker,
        fn,
        **kwargs,
    ) -> Any:
        """
        Execute a stage with retry logic.
        
        Retry strategy:
          - Max 3 attempts per stage
          - Exponential backoff: 2s, 4s, 8s
          - Only retries on recoverable errors (timeouts, rate limits)
          - Non-recoverable errors (validation failures) fail immediately
        """
        last_error = None
        
        async with tracker.stage(stage_num):
            for attempt in range(1, MAX_STAGE_RETRIES + 1):
                try:
                    tracker.stages[stage_num]["retries"] = attempt - 1
                    
                    if attempt > 1:
                        delay = RETRY_BASE_DELAY * (2 ** (attempt - 2))
                        logger.info(
                            f"Stage {stage_num} retry {attempt - 1}/{MAX_STAGE_RETRIES - 1} "
                            f"(waiting {delay}s)"
                        )
                        await tracker.increment_retry(stage_num)
                        await asyncio.sleep(delay)
                    
                    return await fn(**kwargs)
                    
                except (asyncio.TimeoutError, ConnectionError, TimeoutError) as e:
                    # Recoverable errors — can retry
                    last_error = e
                    logger.warning(
                        f"Stage {stage_num} attempt {attempt} failed (recoverable): {e}"
                    )
                    
                    if attempt < MAX_STAGE_RETRIES:
                        continue
                    
                    # All retries exhausted
                    error_msg = f"Stage {stage_num} failed after {MAX_STAGE_RETRIES} attempts: {e}"
                    await tracker.fail_stage(str(e), attempt - 1)
                    raise StageError(stage_num, stage_name, str(e), attempt - 1)
                    
                except (ValueError, TypeError, AssertionError) as e:
                    # Non-recoverable errors — fail immediately
                    error_msg = f"Stage {stage_num} failed (non-recoverable): {e}"
                    logger.error(error_msg)
                    await tracker.fail_stage(str(e), attempt - 1)
                    raise StageError(stage_num, stage_name, str(e), attempt - 1)
                    
                except Exception as e:
                    # Unknown errors — try once more, then fail
                    last_error = e
                    logger.error(
                        f"Stage {stage_num} attempt {attempt} failed (unknown): {e}"
                    )
                    
                    if attempt < MAX_STAGE_RETRIES:
                        continue
                    
                    await tracker.fail_stage(str(e), attempt - 1)
                    raise StageError(stage_num, stage_name, str(e), attempt - 1)

    async def _stage1_execute(
        self,
        file_path: str,
        pipeline_id: str,
    ) -> SchemaInferenceResponse:
        """Execute Stage 1: CSV → JSON Schema Inference."""
        return await self.stage1.run(file_path, pipeline_id=pipeline_id)

    async def _stage2_execute(
        self,
        df: pl.DataFrame,
        pipeline_id: str,
        tracker: ProgressTracker,
    ) -> Tuple[pl.DataFrame, QualityProfile, CleaningPlan]:
        """Execute Stage 2: Data Cleaning."""
        return await self.stage2.run(df, pipeline_id=pipeline_id)

    async def _stage3_execute(
        self,
        df: pl.DataFrame,
        tracker: ProgressTracker,
    ) -> UnifiedDataModel:
        """Execute Stage 3: LangGraph Agent."""
        return await self.stage3.run(df)

    async def _stage4_execute(
        self,
        df: pl.DataFrame,
        udm: UnifiedDataModel,
        tracker: ProgressTracker,
    ) -> UnifiedDataModel:
        """Execute Stage 4: Column Engineering."""
        return await self.stage4.run(df, udm)
    
    def _parse_csv_with_schema(
        self,
        file_path: str,
        schema: SchemaInferenceResponse,
    ) -> pl.DataFrame:
        """
        Parse CSV file respecting the inferred schema.
        
        Args:
            file_path: Path to CSV file
            schema: Inferred schema from Stage 1
        
        Returns:
            Polars DataFrame with typed columns
        """
        from backend.tools import parse_csv
        
        df = parse_csv(file_path, encoding=schema.encoding, infer_schema_length=10000)
        
        # Apply type overrides from schema inference
        for col_inference in schema.columns:
            col_name = col_inference.column_name
            if col_name not in df.columns:
                continue
            
            detected_type = col_inference.detected_type
            try:
                if detected_type.value == "int":
                    df = df.with_columns(pl.col(col_name).cast(pl.Int64, strict=False))
                elif detected_type.value == "float":
                    df = df.with_columns(pl.col(col_name).cast(pl.Float64, strict=False))
                elif detected_type.value in ("date", "datetime"):
                    fmt = col_inference.format_spec
                    if fmt:
                        df = df.with_columns(
                            pl.col(col_name).str.strptime(pl.Datetime, fmt, strict=False)
                        )
            except Exception as e:
                logger.warning(f"Type cast failed for '{col_name}': {e}")
        
        logger.info(f"CSV parsed: {len(df)} rows, {len(df.columns)} columns")
        return df
    
    async def _persist_result(
        self,
        pipeline_id: str,
        udm: UnifiedDataModel,
        stages_completed: List[str],
        total_time_ms: float,
    ) -> None:
        """Persist pipeline result to PostgreSQL and S3."""
        try:
            # Store in PostgreSQL
            await insert_one("pipelines", {
                "pipeline_id": pipeline_id,
                "status": "completed",
                "stages_completed": stages_completed,
                "total_processing_time_ms": round(total_time_ms),
                "unified_data_model": udm.model_dump_json(),
                "created_at": datetime.utcnow().isoformat(),
            }, returning="pipeline_id")
            
            # Store UDM as JSON in S3
            import json
            udm_json = udm.model_dump_json(indent=2)
            s3_key = f"autoinsight/{pipeline_id}/unified_data_model.json"
            
            if hasattr(storage_manager, '_s3_client') and storage_manager._s3_client:
                storage_manager._s3_client.put_object(
                    Bucket=storage_manager._bucket,
                    Key=s3_key,
                    Body=udm_json.encode(),
                    ContentType="application/json",
                )
            
            logger.info(f"Pipeline result persisted: {pipeline_id}")
            
        except Exception as e:
            logger.warning(f"Failed to persist pipeline result: {e}")
    
    async def _persist_failure(
        self,
        pipeline_id: str,
        error: str,
        stages_completed: List[str],
    ) -> None:
        """Persist pipeline failure to PostgreSQL."""
        try:
            await insert_one("pipelines", {
                "pipeline_id": pipeline_id,
                "status": "failed",
                "stages_completed": stages_completed,
                "error": error,
                "created_at": datetime.utcnow().isoformat(),
            }, returning="pipeline_id")
        except Exception as e:
            logger.warning(f"Failed to persist failure: {e}")
    
    async def get_pipeline_status(
        self,
        pipeline_id: str,
    ) -> Dict[str, Any]:
        """
        Get current pipeline status from cache or PostgreSQL.
        
        Args:
            pipeline_id: Pipeline execution UUID
        
        Returns:
            Pipeline state dict
        """
        # Check cache first
        state = await cache_manager.get_pipeline_state(pipeline_id)
        if state:
            return state
        
        # Check PostgreSQL
        from backend.database import fetch_one
        row = await fetch_one("pipelines", {"pipeline_id": pipeline_id})
        if row:
            return {
                "pipeline_id": row["pipeline_id"],
                "status": row["status"],
                "progress": 100.0 if row["status"] == "completed" else 0.0,
                "stages_completed": row.get("stages_completed", []),
                "error": row.get("error"),
            }
        
        return {
            "pipeline_id": pipeline_id,
            "status": "not_found",
            "progress": 0.0,
        }
    
    async def event_stream(
        self,
        pipeline_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        SSE event stream for real-time pipeline progress.
        
        Usage:
            async for event in orchestrator.event_stream("pipeline-uuid"):
                yield f"data: {event}\n\n"
        """
        tracker = ProgressTracker(pipeline_id)
        async for event in tracker.event_stream():
            yield event


# Global orchestrator instance
orchestrator = PipelineOrchestrator()
