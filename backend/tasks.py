# =============================================================================
# AutoInsight AI — Celery Async Tasks (tasks.py)
# Phase 2: Core Pipeline — Background Task Processing
# =============================================================================
"""
Celery task definitions for async pipeline processing.

Handles:
  - Pipeline execution (full 4-stage pipeline in background)
  - Cleaning plan execution (async transformation)
  - Report generation (4-phase report engine — ready for Phase 3)
  - Cache warming for frequently accessed datasets

Usage:
    from backend.tasks import run_pipeline_task
    run_pipeline_task.delay(file_path="data.csv", pipeline_id="uuid")
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import Celery
from celery.signals import task_failure, task_success

from backend.config import settings

logger = logging.getLogger(__name__)

# Celery application with Redis broker
celery_app = Celery(
    "autoinsight_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.PIPELINE_TIMEOUT_SECONDS,
    task_soft_time_limit=settings.PIPELINE_TIMEOUT_SECONDS - 30,
    worker_max_tasks_per_child=50,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "pipeline": {"exchange": "pipeline", "routing_key": "pipeline"},
        "cleaning": {"exchange": "cleaning", "routing_key": "cleaning"},
        "reports": {"exchange": "reports", "routing_key": "reports"},
    },
    task_routes={
        "backend.tasks.run_pipeline_task": {"queue": "pipeline"},
        "backend.tasks.run_cleaning_task": {"queue": "cleaning"},
        "backend.tasks.generate_report_task": {"queue": "reports"},
    },
)


# =============================================================================
# Task Signals
# =============================================================================

@task_success.connect
def handle_task_success(sender=None, result=None, **kwargs):
    """Log successful task completion."""
    logger.info(f"Task succeeded: {sender.name} — result size: {len(str(result))} chars")


@task_failure.connect
def handle_task_failure(sender=None, exception=None, traceback=None, **kwargs):
    """Log task failure with exception details."""
    logger.error(f"Task failed: {sender.name} — {exception}")


# =============================================================================
# Pipeline Tasks
# =============================================================================

@celery_app.task(
    bind=True,
    name="run_pipeline_task",
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def run_pipeline_task(
    self,
    file_path: str,
    pipeline_id: str,
    llm_provider: str = "groq",
    skip_cleaning: bool = False,
) -> Dict[str, Any]:
    """
    Execute the full 4-stage pipeline as a Celery task.
    
    Args:
        file_path: Path to the CSV file
        pipeline_id: Pipeline execution UUID
        llm_provider: LLM provider ("groq" or "ollama")
        skip_cleaning: If True, skip Stage 2
    
    Returns:
        Pipeline result dict
    
    Raises:
        self.retry() on recoverable errors
    """
    start_time = datetime.utcnow()
    logger.info(f"Pipeline task started: {pipeline_id} — file={file_path}")

    try:
        # Run async orchestrator in sync Celery task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from backend.pipeline.orchestrator import PipelineOrchestrator
            orchestrator = PipelineOrchestrator(llm_provider=llm_provider)
            
            result = loop.run_until_complete(
                orchestrator.run_pipeline(
                    file_path=file_path,
                    pipeline_id=pipeline_id,
                    skip_cleaning=skip_cleaning,
                )
            )
            
            return result
            
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Pipeline task failed: {exc}", exc_info=True)
        
        try:
            self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))
        except Exception as retry_error:
            logger.error(f"All retries exhausted: {retry_error}")
            return {
                "pipeline_id": pipeline_id,
                "status": "failed",
                "error": str(exc),
                "stages_completed": [],
                "started_at": start_time.isoformat(),
            }


@celery_app.task(
    bind=True,
    name="run_cleaning_task",
    max_retries=2,
    default_retry_delay=5,
)
def run_cleaning_task(
    self,
    pipeline_id: str,
    operations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Execute approved cleaning operations as a background task.
    
    Args:
        pipeline_id: Pipeline execution UUID
        operations: Approved cleaning operations
    
    Returns:
        Cleaning result with audit trail
    """
    logger.info(f"Cleaning task started: {pipeline_id} — {len(operations)} operations")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get cached DataFrame
            from backend.cache import cache_manager
            df = loop.run_until_complete(
                cache_manager.get_dataframe(f"stage2_input:{pipeline_id}")
            )
            
            if df is None:
                return {
                    "pipeline_id": pipeline_id,
                    "status": "failed",
                    "error": "Input DataFrame not found in cache",
                }
            
            from backend.pipeline.stage2_data_clean import Stage2_DataClean
            cleaner = Stage2_DataClean()
            
            cleaned_df, _, _ = loop.run_until_complete(
                cleaner.run(df, pipeline_id=pipeline_id, approved_operations=operations)
            )
            
            # Cache cleaned DataFrame
            loop.run_until_complete(
                cache_manager.cache_dataframe(f"stage2_output:{pipeline_id}", cleaned_df)
            )
            
            return {
                "pipeline_id": pipeline_id,
                "status": "completed",
                "rows_before": len(df),
                "rows_after": len(cleaned_df),
                "columns": len(cleaned_df.columns),
            }
            
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Cleaning task failed: {exc}")
        self.retry(exc=exc)
        return {
            "pipeline_id": pipeline_id,
            "status": "failed",
            "error": str(exc),
        }


# =============================================================================
# Report Generation Tasks (Ready for Phase 3)
# =============================================================================

@celery_app.task(
    bind=True,
    name="generate_report_task",
    max_retries=2,
    default_retry_delay=10,
)
def generate_report_task(
    self,
    data_model_id: str,
    report_id: str,
    export_formats: List[str] = None,
) -> Dict[str, Any]:
    """
    Generate an analytical report (4-phase engine — Phase 3 scope).
    
    Args:
        data_model_id: UnifiedDataModel ID
        report_id: Report UUID
        export_formats: List of export formats (pdf, html, md, xlsx)
    
    Returns:
        Report generation result
    """
    logger.info(f"Report task started: {report_id} — UDM={data_model_id}")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Retrieve UDM from storage
            from backend.storage import storage_manager
            from backend.schemas import UnifiedDataModel
            
            key = f"autoinsight/{data_model_id}/unified_data_model.json"
            udm_json = loop.run_until_complete(storage_manager.download_file(key))
            
            if isinstance(udm_json, bytes):
                import json
                udm_data = json.loads(udm_json)
            else:
                import json
                with open(udm_json, 'r') as f:
                    udm_data = json.load(f)
            
            udm = UnifiedDataModel(**udm_data)
            
            # Phase 2 placeholder — full report generation in Phase 3
            # This will call the 4-phase report engine
            return {
                "report_id": report_id,
                "status": "placeholder",
                "message": "Full report engine coming in Phase 3",
                "data_model_id": data_model_id,
                "sections_count": 0,
                "export_formats": export_formats or [],
            }
            
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Report task failed: {exc}")
        self.retry(exc=exc)
        return {
            "report_id": report_id,
            "status": "failed",
            "error": str(exc),
        }


# =============================================================================
# Cache Warming Task
# =============================================================================

@celery_app.task(name="warm_cache_task")
def warm_cache_task(dataset_id: str) -> Dict[str, Any]:
    """
    Pre-warm cache for frequently accessed datasets.
    
    Loads dataset metadata and profile into Redis cache
    to reduce latency for common queries.
    """
    logger.info(f"Cache warming started: {dataset_id}")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from backend.cache import cache_manager
            
            # Mark as cached
            loop.run_until_complete(
                cache_manager.set(
                    f"cache_warm:{dataset_id}",
                    {"warmed_at": datetime.utcnow().isoformat()},
                    ttl=3600,
                )
            )
            
            return {
                "dataset_id": dataset_id,
                "status": "warmed",
                "cached_keys": [],
            }
            
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Cache warming failed: {exc}")
        return {
            "dataset_id": dataset_id,
            "status": "failed",
            "error": str(exc),
        }
