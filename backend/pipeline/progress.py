# =============================================================================
# AutoInsight AI — Pipeline Progress Tracker (pipeline/progress.py)
# Phase 2: Core Pipeline — Stage Progress Management
# =============================================================================
"""
Pipeline progress tracking with SSE (Server-Sent Events) support.

Provides:
  - Stage-by-stage progress tracking
  - SSE event streaming for real-time frontend updates
  - Detailed status per operation within each stage
  - Timing and performance metrics per stage

Progress Flow:
  Stage 1: CSV → JSON (0% - 25%)
    ├── Encoding detection  (0% → 5%)
    ├── CSV parsing         (5% → 10%)
    ├── Schema inference    (10% → 20%)
    └── Caching             (20% → 25%)
  
  Stage 2: Data Cleaning (25% - 50%)
    ├── Quality profiling   (25% → 30%)
    ├── LLM cleaning plan   (30% → 38%)
    ├── Diff preview        (38% → 42%)
    └── Transformations     (42% → 50%)
  
  Stage 3: LangGraph Agent (50% - 80%)
    ├── profile_step        (50% → 56%)
    ├── discover_step       (56% → 62%)
    ├── reason_step         (62% → 72%)  ← LLM
    └── executor_step       (72% → 80%)
  
  Stage 4: Column Engineering (80% - 100%)
    ├── Expression eval     (80% → 88%)
    ├── Viz schema gen      (88% → 94%)
    └── UDM assembly        (94% → 100%)

Usage:
    from backend.pipeline.progress import ProgressTracker
    
    tracker = ProgressTracker(pipeline_id="uuid")
    await tracker.start_stage(1, "CSV → JSON")
    await tracker.update(15, "Parsing CSV file...")
    await tracker.complete_stage()
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from backend.cache import cache_manager

logger = logging.getLogger(__name__)

# Stage progress boundaries
STAGE_BOUNDARIES = {
    1: {"start": 0.0, "end": 25.0, "name": "CSV → JSON Schema Inference"},
    2: {"start": 25.0, "end": 50.0, "name": "Data Cleaning & Preprocessing"},
    3: {"start": 50.0, "end": 80.0, "name": "LangGraph Relationship Discovery"},
    4: {"start": 80.0, "end": 100.0, "name": "Column Engineering & UDM Assembly"},
}


class StageStatus(str, Enum):
    """Status of an individual pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class ProgressTracker:
    """
    Tracks pipeline execution progress across all stages.
    
    Supports:
      - Stage-by-stage progress with % completion
      - Operation-level granularity within each stage
      - SSE event generation for real-time frontend updates
      - Timing metrics per stage and operation
      - Retry tracking with attempt counts
    
    Usage:
        tracker = ProgressTracker("pipeline-uuid")
        async with tracker.stage(1):
            await tracker.op("Detecting encoding")
            await tracker.update(20)
    """
    
    def __init__(self, pipeline_id: str):
        """
        Initialize progress tracker for a pipeline execution.
        
        Args:
            pipeline_id: UUID of the pipeline execution
        """
        self.pipeline_id = pipeline_id
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._stage_start_times: Dict[int, float] = {}
        self._stage_end_times: Dict[int, float] = {}
        self._stage_retries: Dict[int, int] = {}
        
        # Current state
        self.current_stage: int = 0
        self.current_stage_name: str = ""
        self.current_operation: str = ""
        self.global_progress: float = 0.0
        self.status: StageStatus = StageStatus.PENDING
        self.stages: Dict[int, Dict[str, Any]] = {}
        
        # Initialize stage tracking
        for num, bounds in STAGE_BOUNDARIES.items():
            self.stages[num] = {
                "name": bounds["name"],
                "status": StageStatus.PENDING.value,
                "progress": 0.0,
                "operations": [],
                "started_at": None,
                "completed_at": None,
                "duration_ms": None,
                "retries": 0,
                "error": None,
            }
    
    async def __aenter__(self):
        """Context manager entry — starts pipeline tracking."""
        await self._emit_event("pipeline_started", {
            "pipeline_id": self.pipeline_id,
            "total_stages": len(STAGE_BOUNDARIES),
        })
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — finalizes pipeline tracking."""
        if exc_type:
            await self._emit_event("pipeline_failed", {
                "error": str(exc_val),
                "stage": self.current_stage,
            })
        else:
            await self._emit_event("pipeline_completed", {
                "global_progress": 100.0,
                "total_duration_ms": self._get_total_duration(),
            })
    
    async def stage(self, stage_num: int) -> "StageContext":
        """
        Context manager for tracking a stage.
        
        Usage:
            async with tracker.stage(1):
                ...
        """
        return StageContext(self, stage_num)
    
    async def start_stage(self, stage_num: int, name: str) -> None:
        """
        Mark a stage as started.
        
        Args:
            stage_num: Stage number (1-4)
            name: Human-readable stage name
        """
        self.current_stage = stage_num
        self.current_stage_name = name
        self.status = StageStatus.RUNNING
        self._stage_start_times[stage_num] = time.time()
        
        self.stages[stage_num]["status"] = StageStatus.RUNNING.value
        self.stages[stage_num]["started_at"] = datetime.utcnow().isoformat()
        
        # Update global progress
        bounds = STAGE_BOUNDARIES[stage_num]
        self.global_progress = bounds["start"]
        
        await self._persist_state()
        await self._emit_event("stage_started", {
            "stage": stage_num,
            "name": name,
            "global_progress": self.global_progress,
        })
        
        logger.info(f"[Pipeline {self.pipeline_id[:8]}] Stage {stage_num} started: {name}")
    
    async def update(self, progress_in_stage: float, message: str = "") -> None:
        """
        Update progress within the current stage.
        
        Args:
            progress_in_stage: Progress within current stage (0.0 - 100.0)
            message: Optional status message
        """
        bounds = STAGE_BOUNDARIES.get(self.current_stage)
        if not bounds:
            return
        
        stage_range = bounds["end"] - bounds["start"]
        self.global_progress = bounds["start"] + (stage_range * progress_in_stage / 100.0)
        
        self.stages[self.current_stage]["progress"] = progress_in_stage
        
        await self._persist_state()
        await self._emit_event("progress", {
            "global_progress": round(self.global_progress, 1),
            "stage": self.current_stage,
            "stage_progress": round(progress_in_stage, 1),
            "message": message,
        })
    
    async def op(self, name: str, weight: float = 1.0) -> "OperationContext":
        """
        Context manager for tracking an operation within a stage.
        
        Usage:
            async with tracker.op("Detecting encoding"):
                # do work
        """
        return OperationContext(self, name, weight)
    
    async def start_operation(self, name: str) -> None:
        """Mark an operation as started."""
        self.current_operation = name
        
        self.stages[self.current_stage]["operations"].append({
            "name": name,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "duration_ms": None,
        })
        
        await self._emit_event("operation_started", {
            "stage": self.current_stage,
            "operation": name,
        })
    
    async def complete_operation(self, name: str, duration_ms: float) -> None:
        """Mark an operation as completed."""
        ops = self.stages[self.current_stage]["operations"]
        for op in reversed(ops):
            if op["name"] == name:
                op["status"] = "completed"
                op["duration_ms"] = round(duration_ms, 1)
                break
        
        await self._emit_event("operation_completed", {
            "stage": self.current_stage,
            "operation": name,
            "duration_ms": round(duration_ms, 1),
        })
    
    async def complete_stage(self, status: str = "completed") -> None:
        """
        Mark the current stage as completed.
        
        Args:
            status: Final status (completed, skipped, failed)
        """
        duration = time.time() - self._stage_start_times.get(self.current_stage, time.time())
        self._stage_end_times[self.current_stage] = time.time()
        
        self.status = StageStatus(status.upper())
        self.stages[self.current_stage].update({
            "status": status,
            "completed_at": datetime.utcnow().isoformat(),
            "duration_ms": round(duration * 1000, 1),
            "progress": 100.0 if status == "completed" else self.stages[self.current_stage]["progress"],
        })
        
        # Update global progress
        bounds = STAGE_BOUNDARIES.get(self.current_stage)
        if bounds:
            self.global_progress = bounds["end"] if status == "completed" else self.global_progress
        
        await self._persist_state()
        await self._emit_event("stage_completed", {
            "stage": self.current_stage,
            "name": self.current_stage_name,
            "status": status,
            "duration_ms": round(duration * 1000, 1),
            "global_progress": self.global_progress,
        })
        
        logger.info(
            f"[Pipeline {self.pipeline_id[:8]}] Stage {self.current_stage} "
            f"{status} ({duration * 1000:.0f}ms)"
        )
    
    async def fail_stage(self, error: str, retry_count: int = 0) -> None:
        """
        Mark the current stage as failed.
        
        Args:
            error: Error message
            retry_count: Number of retry attempts made
        """
        self.stages[self.current_stage].update({
            "status": StageStatus.FAILED.value,
            "error": error,
            "retries": retry_count,
        })
        
        await self._persist_state()
        await self._emit_event("stage_failed", {
            "stage": self.current_stage,
            "error": error,
            "retries": retry_count,
        })
        
        logger.error(
            f"[Pipeline {self.pipeline_id[:8]}] Stage {self.current_stage} "
            f"failed: {error} (retries={retry_count})"
        )
    
    async def increment_retry(self, stage_num: int) -> int:
        """
        Increment retry count for a stage.
        
        Args:
            stage_num: Stage number
        
        Returns:
            New retry count
        """
        self._stage_retries[stage_num] = self._stage_retries.get(stage_num, 0) + 1
        self.stages[stage_num]["retries"] = self._stage_retries[stage_num]
        self.stages[stage_num]["status"] = StageStatus.RETRYING.value
        
        await self._persist_state()
        await self._emit_event("stage_retrying", {
            "stage": stage_num,
            "retry": self._stage_retries[stage_num],
        })
        
        return self._stage_retries[stage_num]
    
    def _get_total_duration(self) -> float:
        """Get total pipeline duration in milliseconds."""
        if not self._stage_start_times:
            return 0.0
        start = min(self._stage_start_times.values())
        end = max(self._stage_end_times.values()) if self._stage_end_times else time.time()
        return (end - start) * 1000
    
    async def _persist_state(self) -> None:
        """Persist current state to Redis cache."""
        state = {
            "pipeline_id": self.pipeline_id,
            "status": self.status.value if isinstance(self.status, StageStatus) else str(self.status),
            "current_stage": self.current_stage,
            "current_stage_name": self.current_stage_name,
            "global_progress": round(self.global_progress, 1),
            "stages": {
                str(k): v for k, v in self.stages.items()
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        await cache_manager.set_pipeline_state(self.pipeline_id, state)
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Emit an SSE event.
        
        Args:
            event_type: Type of event (e.g., "stage_started", "progress")
            data: Event payload
        """
        event = {
            "event": event_type,
            "data": json.dumps({
                **data,
                "pipeline_id": self.pipeline_id,
                "timestamp": datetime.utcnow().isoformat(),
            }),
        }
        await self._event_queue.put(event)
    
    async def event_stream(self) -> AsyncGenerator[str, None]:
        """
        Async generator for SSE event streaming.
        
        Usage:
            async for event in tracker.event_stream():
                yield f"event: {event['event']}\ndata: {event['data']}\n\n"
        """
        while True:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                yield f"event: {event['event']}\ndata: {event['data']}\n\n"
                
                # If pipeline completed or failed, stop streaming
                if event["event"] in ("pipeline_completed", "pipeline_failed"):
                    break
            except asyncio.TimeoutError:
                # Check if pipeline is still active
                if not self.status in (StageStatus.RUNNING, StageStatus.PENDING):
                    break
                continue


class StageContext:
    """Context manager for pipeline stage tracking."""
    
    def __init__(self, tracker: ProgressTracker, stage_num: int):
        self.tracker = tracker
        self.stage_num = stage_num
        self.name = STAGE_BOUNDARIES[stage_num]["name"]
    
    async def __aenter__(self):
        await self.tracker.start_stage(self.stage_num, self.name)
        return self.tracker
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.tracker.fail_stage(str(exc_val))
        else:
            await self.tracker.complete_stage("completed")


class OperationContext:
    """Context manager for operation tracking within a stage."""
    
    def __init__(self, tracker: ProgressTracker, name: str, weight: float = 1.0):
        self.tracker = tracker
        self.name = name
        self.weight = weight
        self._start_time: float = 0.0
    
    async def __aenter__(self):
        self._start_time = time.time()
        await self.tracker.start_operation(self.name)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = (time.time() - self._start_time) * 1000
        await self.tracker.complete_operation(self.name, duration)
