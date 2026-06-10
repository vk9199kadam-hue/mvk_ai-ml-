# =============================================================================
# AutoInsight AI — Middleware Registration (Phase 5)
# Registers all performance, security, and monitoring middleware
# =============================================================================

from __future__ import annotations

import logging

from fastapi import FastAPI

from backend.config import settings
from backend.middleware.performance import (
    CompressionMiddleware,
    PerformanceMetricsMiddleware,
    QueryCacheMiddleware,
    performance_monitor,
)
from backend.middleware.security import (
    AuthRateLimitMiddleware,
    InputValidationMiddleware,
    JWTBlacklistMiddleware,
    SecurityHeadersMiddleware,
    rate_limiter,
    security_audit,
    token_blacklist,
)

logger = logging.getLogger(__name__)


def register_middleware(app: FastAPI) -> None:
    """Register all Phase 5 middleware in the correct order.
    
    Middleware execution order (last added = first executed):
    1. SecurityHeaders — Add security headers to ALL responses
    2. JWTBlacklist — Check JWT blacklist before processing
    3. AuthRateLimit — Rate limit authentication endpoints
    4. InputValidation — Validate inputs against injection patterns
    5. Compression — Compress responses > 512 bytes
    6. QueryCache — Cache GET responses for frequent endpoints
    7. PerformanceMetrics — Track response times and log slow queries
    
    Args:
        app: FastAPI application instance
    """

    # Order matters: middleware runs in REVERSE order of registration.
    # The LAST middleware added runs FIRST (outermost).
    # SecurityHeaders MUST be outermost so ALL responses get security headers
    # — including cached responses from QueryCache.
    
    # 1. Performance metrics (innermost — runs last on request)
    app.add_middleware(PerformanceMetricsMiddleware)
    logger.debug("Registered: PerformanceMetricsMiddleware")

    # 2. Query cache
    app.add_middleware(QueryCacheMiddleware)
    logger.debug("Registered: QueryCacheMiddleware")

    # 3. Response compression
    app.add_middleware(CompressionMiddleware)
    logger.debug("Registered: CompressionMiddleware")

    # 4. Input validation
    app.add_middleware(InputValidationMiddleware)
    logger.debug("Registered: InputValidationMiddleware")

    # 5. Auth rate limiting
    app.add_middleware(AuthRateLimitMiddleware)
    logger.debug("Registered: AuthRateLimitMiddleware")

    # 6. JWT blacklist check
    app.add_middleware(JWTBlacklistMiddleware)
    logger.debug("Registered: JWTBlacklistMiddleware")

    # 7. Security headers (outermost — runs FIRST on request)
    # Ensures ALL responses have security headers, even cached hits
    app.add_middleware(SecurityHeadersMiddleware)
    logger.debug("Registered: SecurityHeadersMiddleware")

    logger.info(
        f"╔══════════════════════════════════════════════════╗\n"
        f"║  Phase 5 Middleware Registered                   ║\n"
        f"║  ────────────────────────                        ║\n"
        f"║  ✓ SecurityHeadersMiddleware     (outermost)     ║\n"
        f"║  ✓ JWTBlacklistMiddleware                       ║\n"
        f"║  ✓ AuthRateLimitMiddleware                      ║\n"
        f"║  ✓ InputValidationMiddleware                    ║\n"
        f"║  ✓ CompressionMiddleware                        ║\n"
        f"║  ✓ QueryCacheMiddleware                         ║\n"
        f"║  ✓ PerformanceMetricsMiddleware  (innermost)    ║\n"
        f"║  ✓ Token Blacklist (in-memory)                   ║\n"
        f"║  ✓ Rate Limiter (sliding window)                 ║\n"
        f"║  ✓ Input Sanitizer (SQL/XSS/Path)                ║\n"
        f"╚══════════════════════════════════════════════════╝"
    )


def get_middleware_stats() -> dict:
    """Get performance and security statistics for admin dashboard.
    
    Returns:
        Dict with current metrics
    """
    return {
        "performance": {
            "monitoring": True,
            "compression_enabled": True,
            "cache_enabled": True,
            "slow_query_logging": True,
        },
        "security": {
            "token_blacklist_size": len(token_blacklist._blacklist),
            "rate_limiting_enabled": True,
            "input_validation_enabled": True,
            "security_headers_enabled": True,
        },
    }
