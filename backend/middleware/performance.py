# =============================================================================
# AutoInsight AI — Performance Profiling & Caching Optimization (Phase 5)
# Day 45: Response compression, query caching, and performance monitoring
# =============================================================================

from __future__ import annotations

import gzip
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from hashlib import md5

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.cache import cache_manager
from backend.config import settings

logger = logging.getLogger(__name__)

# ── Response Compression Middleware ────────────────────────────────────────

MIN_COMPRESS_SIZE = 512  # Only compress responses larger than 512 bytes


class CompressionMiddleware(BaseHTTPMiddleware):
    """Gzip compression middleware for API responses.
    
    Compresses JSON responses > 512 bytes to reduce bandwidth.
    Adds Content-Encoding: gzip header when compression is applied.
    Target: <3s dashboard load even with large datasets.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Only compress JSON responses
        if not response.headers.get("content-type", "").startswith("application/json"):
            return response

        # Only compress responses larger than threshold
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        if len(body) < MIN_COMPRESS_SIZE:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Compress
        compressed = gzip.compress(body, compresslevel=6)

        headers = dict(response.headers)
        headers["Content-Encoding"] = "gzip"
        headers["Content-Length"] = str(len(compressed))
        headers["X-Compression-Ratio"] = f"{len(body) / len(compressed):.1f}x"

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


# ── Query Result Cache Middleware ──────────────────────────────────────────

CACHEABLE_PATHS = [
    "/api/v1/system/info",
    "/api/v1/dashboard",
    "/api/v1/reports",
]

CACHE_TTL_BY_PATH = {
    "/api/v1/system/info": 300,       # 5 min
    "/api/v1/dashboard": 60,          # 1 min
    "/api/v1/reports": 120,           # 2 min
}

CACHEABLE_METHODS = {"GET"}


class QueryCacheMiddleware(BaseHTTPMiddleware):
    """Caches GET responses for frequently accessed endpoints.
    
    Cache keys are based on (path + query params) with configurable TTL.
    Reduces database load and improves response times for repeated queries.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only cache GET requests to cacheable paths
        if request.method not in CACHEABLE_METHODS:
            return await call_next(request)

        path = request.url.path
        is_cacheable = any(path.startswith(p) for p in CACHEABLE_PATHS)
        if not is_cacheable:
            return await call_next(request)

        # Build cache key from path + query params
        query_key = str(request.query_params) if request.query_params else ""
        cache_key = f"query_cache:{path}:{md5(query_key.encode()).hexdigest()[:16]}"

        # Try cache hit
        cached = await cache_manager.get(cache_key)
        if cached is not None:
            ttl = CACHE_TTL_BY_PATH.get(
                next((p for p in CACHE_TTL_BY_PATH if path.startswith(p)), 60),
                60,
            )
            logger.debug(f"Query cache HIT: {cache_key} (TTL={ttl}s)")
            return JSONResponse(
                content=cached,
                headers={
                    "X-Cache": "HIT",
                    "X-Cache-TTL": str(ttl),
                },
            )

        # Cache miss — process normally
        response = await call_next(request)

        # Cache successful responses
        if response.status_code == 200:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            try:
                data = json.loads(body)
                ttl = CACHE_TTL_BY_PATH.get(
                    next((p for p in CACHE_TTL_BY_PATH if path.startswith(p)), 60),
                    60,
                )
                await cache_manager.set(cache_key, data, ttl=ttl)
                headers = dict(response.headers)
                headers["X-Cache"] = "MISS"
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=headers,
                    media_type=response.media_type,
                )
            except (json.JSONDecodeError, StopAsyncIteration):
                pass

        return response


# ── Performance Metrics Middleware ─────────────────────────────────────────

class PerformanceMetricsMiddleware(BaseHTTPMiddleware):
    """Tracks request performance metrics and logs slow queries.
    
    Records:
      - Per-endpoint response times (p50, p95, p99)
      - Slow query warnings (>500ms / >1s / >3s)
      - Total request count and bytes transferred
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._metrics: Dict[str, list] = {}
        self._slow_thresholds = {
            "warning": 0.5,   # 500ms
            "critical": 1.0,  # 1s
            "severe": 3.0,    # 3s (dashboard target)
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        start_bytes = 0

        path = request.url.path
        method = request.method

        response = await call_next(request)

        elapsed = time.perf_counter() - start_time

        # Track metrics per-endpoint
        endpoint = f"{method}:{path}"
        if endpoint not in self._metrics:
            self._metrics[endpoint] = []
        self._metrics[endpoint].append(elapsed)

        # Log slow queries
        if elapsed > self._slow_thresholds["warning"]:
            level = "WARNING"
            if elapsed > self._slow_thresholds["severe"]:
                level = "CRITICAL"
            elif elapsed > self._slow_thresholds["critical"]:
                level = "ERROR"

            getattr(logger, level.lower())(
                f"SLOW QUERY [{level}] {method} {path} — "
                f"{elapsed:.2f}s "
                f"({response.status_code})"
            )

        # Add performance headers
        response.headers["X-Response-Time-MS"] = str(round(elapsed * 1000, 2))

        return response

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated performance statistics."""
        stats = {}
        for endpoint, times in self._metrics.items():
            if not times:
                continue
            sorted_times = sorted(times)
            n = len(sorted_times)
            stats[endpoint] = {
                "count": n,
                "p50_ms": round(sorted_times[n // 2] * 1000, 2),
                "p95_ms": round(sorted_times[int(n * 0.95)] * 1000, 2),
                "p99_ms": round(sorted_times[int(n * 0.99)] * 1000, 2),
                "min_ms": round(sorted_times[0] * 1000, 2),
                "max_ms": round(sorted_times[-1] * 1000, 2),
                "avg_ms": round(sum(times) / n * 1000, 2),
            }
        return stats


# ── Global Performance Monitor ─────────────────────────────────────────────

performance_monitor = PerformanceMetricsMiddleware.__new__(PerformanceMetricsMiddleware)
performance_monitor._metrics = {}
performance_monitor._slow_thresholds = {
    "warning": 0.5,
    "critical": 1.0,
    "severe": 3.0,
}
