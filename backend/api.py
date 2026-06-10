# =============================================================================
# AutoInsight AI — FastAPI Application Entry Point (api.py)
# Phase 2: Core Pipeline — Enhanced API with Upload, SSE & Pipeline Status
# =============================================================================
"""
FastAPI application — Phase 2 Enhanced with upload handlers, SSE streaming,
and full pipeline status tracking.

New Endpoints (Phase 2):
  POST   /api/v1/upload/initiate    — Start file upload session
  POST   /api/v1/upload/chunk       — Upload file chunk
  GET    /api/v1/upload/progress     — SSE upload progress stream
  POST   /api/v1/upload/complete    — Finalize upload
  GET    /api/v1/pipeline/events     — SSE pipeline progress stream
  POST   /api/v1/pipeline/cleaning/approve  — Approve cleaning plan
  GET    /api/v1/pipeline/diff       — Get cleaning diff preview

Updated Endpoints (Phase 2):
  POST   /api/v1/pipeline/run       — Full 4-stage pipeline execution
  GET    /api/v1/pipeline/status    — Real pipeline status from Redis/DB
"""

from __future__ import annotations

import json
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from backend.config import settings
from backend.database import get_pool, close_pool, health_check
from backend.middleware.auth import AuthMiddleware, log_request_middleware
from backend.middleware.register import register_middleware, get_middleware_stats
from backend.upload import upload_handler, UploadHandler, UploadError
from backend.cache import cache_manager
from backend.pipeline.orchestrator import PipelineOrchestrator, PipelineError
from backend.pipeline.progress import ProgressTracker
from backend.schemas import PipelineResult, PipelineStatus, CleaningPlan

logger = logging.getLogger(__name__)


# =============================================================================
# Application Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    logger.info(
        f"╔══════════════════════════════════════════════════╗\n"
        f"║  {settings.APP_NAME} v{settings.APP_VERSION} — Phase 2       ║\n"
        f"║  Starting up...                                   ║\n"
        f"║  LLM Provider: {settings.LLM_PROVIDER:<30} ║\n"
        f"║  Debug Mode: {str(settings.DEBUG):>30} ║\n"
        f"╚══════════════════════════════════════════════════╝"
    )

    try:
        pool = await get_pool()
        db_health = await health_check()
        logger.info(f"Database: {db_health}")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")

    yield

    logger.info("Shutting down AutoInsight AI Phase 2...")
    await close_pool()


# =============================================================================
# FastAPI Application Instance
# =============================================================================

app = FastAPI(
    title=f"{settings.APP_NAME} — Phase 2",
    version=settings.APP_VERSION,
    description="""
    AutoInsight AI — Phase 2: Core Pipeline Implementation.
    
    ## Phase 2 Features
    - **Stage 1:** Full CSV parser with chardet encoding + Qwen 2.5 72B schema inference
    - **Stage 2:** DataPrep quality profiling + AI cleaning plan + diff preview + Parquet snapshots
    - **Stage 3:** LangGraph 4-node workflow with confidence gating (≥0.65) + retry logic
    - **Stage 4:** Safe column engineering with AST-sandboxed Polars eval
    - **Orchestrator:** End-to-end pipeline with SSE progress streaming
    
    ## LLM Integration
    - Primary: Qwen 2.5 72B (Groq Free Tier — $0)
    - Fallback: Llama 3.1 8B (Ollama — $0 local)
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# =============================================================================
# Middleware Stack
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)
app.middleware("http")(log_request_middleware)

# ── Phase 5 Middleware (Performance, Security, Monitoring) ──────────────────
register_middleware(app)


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "data": None,
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_id": getattr(request.state, "request_id", str(uuid4())),
                "version": settings.APP_VERSION,
            },
            "errors": [exc.detail],
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "data": None,
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_id": getattr(request.state, "request_id", str(uuid4())),
                "version": settings.APP_VERSION,
            },
            "errors": ["An unexpected error occurred. Please try again later."],
        },
    )


# =============================================================================
# Health Check Endpoints
# =============================================================================

@app.get("/health", tags=["System"])
async def health_check_endpoint():
    """Comprehensive system health check."""
    start_time = time.time()
    db_health = await health_check()

    health_status = {
        "status": "healthy",
        "application": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "phase": "2",
            "debug": settings.DEBUG,
        },
        "database": db_health,
        "cache": await cache_manager.health_check(),
        "llm_provider": {
            "primary": settings.LLM_PROVIDER,
            "primary_model": settings.GROQ_MODEL,
            "fallback": "ollama",
            "fallback_model": settings.OLLAMA_MODEL,
        },
        "pipeline": {
            "stages": ["CSV→JSON", "Cleaning", "LangGraph", "Column Engineering"],
            "max_retries": 3,
            "confidence_gate": settings.CONFIDENCE_MANUAL_APPROVAL,
        },
        "response_time_ms": round((time.time() - start_time) * 1000, 2),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if db_health.get("status") == "unhealthy":
        health_status["status"] = "degraded"

    return JSONResponse(
        content=health_status,
        status_code=200 if health_status["status"] != "degraded" else 503,
    )


@app.get("/health/ready", tags=["System"])
async def readiness_check():
    return {"status": "ready", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/health/live", tags=["System"])
async def liveness_check():
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat() + "Z"}


# =============================================================================
# API v1 Router
# =============================================================================

from fastapi import APIRouter
from pydantic import BaseModel

api_v1 = APIRouter(prefix="/api/v1")


# ── Request/Response Models ────────────────────────────────────────────────

class UploadInitiateRequest(BaseModel):
    filename: str
    file_size: int
    content_type: Optional[str] = None


class ChunkUploadRequest(BaseModel):
    upload_id: str
    chunk_index: int = 0
    is_final: bool = False


class PipelineRunRequest(BaseModel):
    upload_id: str
    llm_provider: str = "groq"
    skip_cleaning: bool = False


class ApproveCleaningRequest(BaseModel):
    pipeline_id: str
    operations: List[Dict[str, Any]]


# ── Upload Endpoints (Phase 2) ─────────────────────────────────────────────

@api_v1.post(
    "/upload/initiate",
    tags=["Upload"],
    summary="Initiate File Upload",
    description="Start a new file upload session. Returns upload_id for chunked upload.",
)
async def upload_initiate(request: UploadInitiateRequest):
    """Initiate a new file upload session."""
    try:
        result = await upload_handler.initiate_upload(
            filename=request.filename,
            file_size=request.file_size,
            content_type=request.content_type,
        )
        return {
            "status": "success",
            "data": result,
            "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
            "errors": [],
        }
    except UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_v1.post(
    "/upload/chunk",
    tags=["Upload"],
    summary="Upload File Chunk",
    description="Upload a chunk of file data. Use is_final=True for the last chunk.",
)
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(0),
    is_final: bool = Form(False),
    file: UploadFile = File(...),
):
    """Upload a chunk of file data."""
    try:
        chunk_data = await file.read()
        result = await upload_handler.upload_chunk(
            upload_id=upload_id,
            chunk_data=chunk_data,
            chunk_index=chunk_index,
            is_final=is_final,
        )
        return {
            "status": "success",
            "data": result,
            "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
            "errors": [],
        }
    except UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_v1.get(
    "/upload/progress/{upload_id}",
    tags=["Upload"],
    summary="SSE Upload Progress",
    description="SSE stream for real-time upload progress.",
)
async def upload_progress_sse(upload_id: str):
    """SSE event stream for upload progress."""
    async def event_generator():
        last_progress = -1
        while True:
            progress = await cache_manager.get_upload_progress(upload_id)
            if progress:
                current = progress.get("progress", -1)
                if current != last_progress:
                    yield {
                        "event": "upload_progress",
                        "data": json.dumps(progress),
                    }
                    last_progress = current
                    if current >= 100 or progress.get("status") in ("completed", "failed", "cancelled"):
                        yield {
                            "event": "upload_complete",
                            "data": json.dumps(progress),
                        }
                        break
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@api_v1.post(
    "/upload/complete/{upload_id}",
    tags=["Upload"],
    summary="Complete Upload",
    description="Finalize an upload. Computes hash, detects encoding, stages file.",
)
async def upload_complete(upload_id: str):
    """Finalize an upload."""
    try:
        result = await upload_handler.complete_upload(upload_id)
        return {
            "status": "success",
            "data": result,
            "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
            "errors": [],
        }
    except UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_v1.delete(
    "/upload/{upload_id}",
    tags=["Upload"],
    summary="Cancel Upload",
    description="Cancel an upload and clean up staging files.",
)
async def upload_cancel(upload_id: str):
    """Cancel an upload."""
    await upload_handler.cancel_upload(upload_id)
    return {
        "status": "success",
        "data": {"upload_id": upload_id, "status": "cancelled"},
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
        "errors": [],
    }


# ── Auth Routes ────────────────────────────────────────────────────────────

@api_v1.post("/auth/login", tags=["Authentication"])
async def login(email: str, password: str):
    from backend.auth import create_tokens

    if password != "password":
        raise HTTPException(status_code=401, detail="Invalid email or password")

    tokens = create_tokens(user_id=str(uuid4()), email=email, role="analyst")

    return {
        "status": "success",
        "data": tokens,
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "request_id": str(uuid4()), "version": settings.APP_VERSION},
        "errors": [],
    }


@api_v1.post("/auth/refresh", tags=["Authentication"])
async def refresh_token(refresh_token: str):
    from backend.auth import refresh_access_token
    new_tokens = await refresh_access_token(refresh_token)

    return {
        "status": "success",
        "data": new_tokens,
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "request_id": str(uuid4()), "version": settings.APP_VERSION},
        "errors": [],
    }


@api_v1.post("/auth/register", tags=["Authentication"])
async def register(email: str, password: str, name: str):
    from backend.auth import hash_password
    hashed = hash_password(password)

    return {
        "status": "success",
        "data": {
            "id": str(uuid4()),
            "email": email,
            "name": name,
            "role": "analyst",
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True,
        },
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "request_id": str(uuid4()), "version": settings.APP_VERSION},
        "errors": [],
    }


# ── Pipeline Routes (Phase 2 Enhanced) ─────────────────────────────────────

@api_v1.post(
    "/pipeline/run",
    tags=["Pipeline"],
    summary="Execute Full Pipeline",
    description="Execute the complete 4-stage data pipeline with progress tracking.",
)
async def run_pipeline(request: PipelineRunRequest):
    """
    Execute the full 4-stage data pipeline:
      Stage 1: CSV → JSON Schema Inference (Qwen 2.5 72B)
      Stage 2: Data Cleaning (AI plan + transformations)
      Stage 3: LangGraph Agent (Relationship Discovery)
      Stage 4: Column Engineering & UDM Assembly
    
    Returns pipeline_id for status polling and SSE streaming.
    """
    # Get upload info
    try:
        upload_info = await upload_handler.get_upload_info(request.upload_id)
    except UploadError as e:
        raise HTTPException(status_code=404, detail=str(e))

    staging_path = upload_info.get("staging_path", "")

    if not staging_path:
        raise HTTPException(status_code=400, detail="Upload file not staged")

    pipeline_id = str(uuid4())

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator(llm_provider=request.llm_provider)

    # Start pipeline in background
    import asyncio
    asyncio.create_task(
        orchestrator.run_pipeline(
            file_path=staging_path,
            pipeline_id=pipeline_id,
            skip_cleaning=request.skip_cleaning,
        )
    )

    return {
        "status": "success",
        "data": {
            "pipeline_id": pipeline_id,
            "status": "queued",
            "upload_id": request.upload_id,
            "message": "Pipeline started. Track progress via GET /api/v1/pipeline/status/{id}",
            "events_url": f"/api/v1/pipeline/events/{pipeline_id}",
            "stages": [
                {"name": "CSV → JSON", "status": "pending"},
                {"name": "Data Cleaning", "status": "pending"},
                {"name": "LangGraph Agent", "status": "pending"},
                {"name": "Column Engineering", "status": "pending"},
            ],
        },
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "request_id": str(uuid4()), "version": settings.APP_VERSION},
        "errors": [],
    }


@api_v1.get(
    "/pipeline/status/{pipeline_id}",
    tags=["Pipeline"],
    summary="Pipeline Status",
    description="Get current pipeline execution status with stage-by-stage progress.",
)
async def get_pipeline_status(pipeline_id: str):
    """Get pipeline execution status."""
    orchestrator = PipelineOrchestrator()
    state = await orchestrator.get_pipeline_status(pipeline_id)

    return {
        "status": "success",
        "data": state,
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "request_id": str(uuid4()), "version": settings.APP_VERSION},
        "errors": [],
    }


@api_v1.get(
    "/pipeline/events/{pipeline_id}",
    tags=["Pipeline"],
    summary="SSE Pipeline Events",
    description="SSE stream for real-time pipeline execution events.",
)
async def pipeline_events_sse(pipeline_id: str):
    """SSE event stream for pipeline progress."""
    async def event_generator():
        last_progress = -1.0
        last_status = ""
        while True:
            state = await cache_manager.get_pipeline_state(pipeline_id)
            if state:
                progress = state.get("global_progress", 0.0)
                status = state.get("status", "running")

                if progress != last_progress or status != last_status:
                    yield {
                        "event": "pipeline_progress",
                        "data": json.dumps(state),
                    }
                    last_progress = progress
                    last_status = status

                    if status in ("completed", "failed"):
                        yield {
                            "event": "pipeline_complete",
                            "data": json.dumps(state),
                        }
                        break
            else:
                yield {
                    "event": "pipeline_not_found",
                    "data": json.dumps({"pipeline_id": pipeline_id}),
                }
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@api_v1.get(
    "/pipeline/diff/{pipeline_id}",
    tags=["Pipeline"],
    summary="Cleaning Diff Preview",
    description="Get before/after diff preview of data cleaning changes.",
)
async def get_pipeline_diff(pipeline_id: str):
    """Get cleaning diff preview."""
    # Phase 2: Returns mock diff — full implementation with actual data
    return {
        "status": "success",
        "data": {
            "pipeline_id": pipeline_id,
            "original_rows": 1000,
            "cleaned_rows": 998,
            "changes": [
                {
                    "column": "example_col",
                    "changed_count": 5,
                    "change_percentage": 0.5,
                    "samples": [
                        {"row": 1, "before": "null", "after": "42.5"},
                        {"row": 2, "before": "null", "after": "37.2"},
                    ],
                }
            ],
            "quality_improvement": 0.15,
        },
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "request_id": str(uuid4()), "version": settings.APP_VERSION},
        "errors": [],
    }


@api_v1.post(
    "/pipeline/cleaning/approve",
    tags=["Pipeline"],
    summary="Approve Cleaning Plan",
    description="Approve or modify cleaning operations before execution.",
)
async def approve_cleaning(request: ApproveCleaningRequest):
    """Approve cleaning operations for execution."""
    # Store approved operations in cache
    await cache_manager.set(
        f"cleaning_approved:{request.pipeline_id}",
        request.operations,
        ttl=3600,
    )

    return {
        "status": "success",
        "data": {
            "pipeline_id": request.pipeline_id,
            "approved_operations": len(request.operations),
            "message": "Cleaning plan approved. Operations will be applied in Stage 2.",
        },
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "request_id": str(uuid4()), "version": settings.APP_VERSION},
        "errors": [],
    }


# ── Report Routes (Phase 2 Placeholder) ────────────────────────────────────

@api_v1.post(
    "/reports/generate",
    tags=["Reports"],
    summary="Generate Report",
    description="Generate a comprehensive 8-section analytical report from a pipeline result.",
)
async def generate_report(data_model_id: str, title: Optional[str] = None):
    """
    Generate a comprehensive analytical report.
    
    The 4-phase report engine:
      Phase 1: 5 deterministic profiling functions (zero LLM)
      Phase 2: 8 parallel LLM sub-agents (asyncio.gather)
      Phase 3: Pydantic validation + confidence gating
      Phase 4: Assembly + multi-format export (HTML/MD/PDF/XLSX)
    
    Args:
        data_model_id: UUID of the UnifiedDataModel to report on
        title: Optional report title
    
    Returns:
        Report metadata with export URLs
    """
    from backend.report.orchestrator import ReportOrchestrator
    
    orchestrator = ReportOrchestrator()
    
    import asyncio
    
    report_id = str(uuid4())
    
    # Load UDM from storage (S3 or PostgreSQL)
    try:
        from backend.storage import storage_manager
        from backend.schemas import UnifiedDataModel
        import json
        
        # Try S3 first
        udm_key = f"autoinsight/{data_model_id}/unified_data_model.json"
        udm_data = await storage_manager.download_file(udm_key)
        
        if isinstance(udm_data, bytes):
            udm_dict = json.loads(udm_data.decode())
        else:
            udm_dict = json.loads(udm_data)
        
        unified_data_model = UnifiedDataModel(**udm_dict)
        
        # Start report generation in background
        asyncio.create_task(
            orchestrator.generate_report(
                unified_data_model=unified_data_model,
                title=title,
                report_id=report_id,
            )
        )
        
        return {
            "status": "success",
            "data": {
                "report_id": report_id,
                "data_model_id": data_model_id,
                "title": title or "Auto-Generated Analytical Report",
                "status": "queued",
                "message": "Report generation started. Use GET /api/v1/reports/{id} to check status.",
            },
            "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
            "errors": [],
        }
    except Exception as e:
        logger.error(f"Failed to load UDM for report generation: {e}")
        return {
            "status": "error",
            "data": None,
            "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
            "errors": [f"Failed to load data model: {str(e)}"],
        }


@api_v1.get(
    "/reports/{report_id}",
    tags=["Reports"],
    summary="Get Report",
    description="Retrieve a generated report by ID with all 8 sections and export URLs.",
)
async def get_report(report_id: str):
    """
    Retrieve a generated report.
    
    Returns the complete ReportBundle with all 8 sections,
    confidence badges, audit trail, and export URLs.
    """
    from backend.report.orchestrator import ReportOrchestrator
    
    orchestrator = ReportOrchestrator()
    status = await orchestrator.get_report_status(report_id)
    
    return {
        "status": "success",
        "data": status,
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
        "errors": [],
    }


@api_v1.get(
    "/reports/{report_id}/export/{format}",
    tags=["Reports"],
    summary="Export Report",
    description="Export a report in the specified format: html, md, pdf, xlsx.",
)
async def export_report(report_id: str, format: str):
    """
    Export a report in the specified format.
    
    Args:
        report_id: Report UUID
        format: Export format (html, md, pdf, xlsx)
    
    Returns:
        Redirect to the exported file URL
    """
    from fastapi.responses import RedirectResponse
    
    from backend.report.orchestrator import ReportOrchestrator
    orchestrator = ReportOrchestrator()
    
    status = await orchestrator.get_report_status(report_id)
    export_urls = status.get("export_urls", {})
    
    url = export_urls.get(format)
    if not url:
        raise HTTPException(
            status_code=404,
            detail=f"Export format '{format}' not available for report {report_id}",
        )
    
    return RedirectResponse(url=url)


# ── NLQ Routes (Phase 2 Placeholder) ──────────────────────────────────────

@api_v1.post("/nlq/query", tags=["NLQ"])
async def nlq_query(query: str, dataset_id: str, conversation_id: Optional[str] = None):
    return {
        "status": "success",
        "data": {
            "natural_language_response": f"Phase 2 placeholder for: '{query}'",
            "confidence": 0.0,
        },
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
        "errors": [],
    }


# ── Dashboard Routes ───────────────────────────────────────────────────────

@api_v1.get("/dashboard/{dashboard_id}", tags=["Dashboard"])
async def get_dashboard(dashboard_id: str):
    return {
        "status": "success",
        "data": {
            "dashboard_id": dashboard_id,
            "title": "Auto-Generated Dashboard",
            "charts": [],
            "layout": {"columns": 2},
        },
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
        "errors": [],
    }


# ── Admin Routes ───────────────────────────────────────────────────────────

@api_v1.get("/admin/users", tags=["Admin"])
async def list_users():
    return {
        "status": "success",
        "data": {
            "users": [
                {
                    "id": str(uuid4()),
                    "email": "admin@autoinsight.com",
                    "name": "Admin User",
                    "role": "admin",
                    "created_at": datetime.utcnow().isoformat(),
                    "is_active": True,
                },
            ],
            "total": 1,
        },
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
        "errors": [],
    }


# ── System Info Route ──────────────────────────────────────────────────────

@api_v1.get("/system/info", tags=["System"])
async def system_info():
    return {
        "status": "success",
        "data": {
            "application": {
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "phase": "2",
                "debug": settings.DEBUG,
            },
            "llm": {
                "provider": settings.LLM_PROVIDER,
                "primary_model": settings.GROQ_MODEL,
                "fallback_model": settings.OLLAMA_MODEL,
                "max_retries": settings.GROQ_MAX_RETRIES,
            },
            "pipeline": {
                "stages": ["CSV→JSON", "Cleaning", "LangGraph", "Column Engineering"],
                "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
        "confidence_gate": settings.CONFIDENCE_MANUAL_APPROVAL,
        "retry_base_delay_s": 2,
    },
    "middleware": get_middleware_stats(),
        },
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z", "version": settings.APP_VERSION},
        "errors": [],
    }


# =============================================================================
# Register API v1 Router
# =============================================================================

app.include_router(api_v1)


@app.get("/", tags=["System"], include_in_schema=False)
async def root():
    return {
        "message": f"{settings.APP_NAME} v{settings.APP_VERSION} — Phase 2",
        "documentation": "/docs",
        "health_check": "/health",
        "api_v1": "/api/v1",
    }
