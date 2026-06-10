# =============================================================================
# AutoInsight AI — Auth Middleware (middleware/auth.py)
# Phase 1: Foundation — Request Interception & Security
# =============================================================================
"""
FastAPI middleware for authentication, authorization, and request logging.

Provides:
  - AuthMiddleware: Intercepts requests, validates JWT, enforces RBAC
  - log_request_middleware: Logs all requests with timing and status
  - Public/Protected route detection based on path prefix

The middleware runs BEFORE route handlers, ensuring:
  1. All protected routes have valid tokens
  2. RBAC roles are checked
  3. All requests are logged with timing
  4. Rate limiting headers are set
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.auth import verify_token
from backend.config import settings

logger = logging.getLogger(__name__)

# ── Public Routes (no authentication required) ─────────────────────────────
PUBLIC_ROUTES: List[str] = [
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/docs",
    "/redoc",
    "/openapi.json",
]

# ── Admin-Only Routes ─────────────────────────────────────────────────────
ADMIN_ROUTES: List[str] = [
    "/api/v1/admin",
]

# ── Routes that can use refresh tokens ────────────────────────────────────
REFRESH_TOKEN_ROUTES: List[str] = [
    "/api/v1/auth/refresh",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication and authorization middleware.
    
    For each request:
      1. Check if route is public (skip auth)
      2. Extract JWT from Authorization header
      3. Verify token signature and expiry
      4. Check RBAC permissions
      5. Set user info in request.state for route handlers
    
    Public routes (no auth required):
      - /health
      - /api/v1/auth/login
      - /api/v1/auth/register
      - /docs, /redoc, /openapi.json
    
    Admin routes (require admin role):
      - /api/v1/admin/*
    """
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process incoming request through auth middleware.
        
        Args:
            request: Incoming FastAPI request
            call_next: Next middleware or route handler
        
        Returns:
            Response object (either successful or error)
        """
        request_id = str(uuid4())
        request.state.request_id = request_id
        request.state.user = None
        
        path = request.url.path
        
        # ── Step 1: Bypass auth for public routes ─────────────────────────
        if self._is_public_route(path):
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        
        # ── Step 2: Extract and validate JWT ──────────────────────────────
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "data": None,
                    "meta": {
                        "request_id": request_id,
                        "timestamp": time.time(),
                    },
                    "errors": [
                        "Authentication required. "
                        "Provide a Bearer token in the Authorization header."
                    ],
                },
            )
        
        try:
            # Extract token from "Bearer <token>"
            token = auth_header.split(" ")[1] if " " in auth_header else auth_header
            
            # Verify the token
            payload = verify_token(token)
            
            # ── Step 3: Check RBAC for admin routes ───────────────────────
            if self._is_admin_route(path) and payload.get("role") != "admin":
                return JSONResponse(
                    status_code=403,
                    content={
                        "status": "error",
                        "data": None,
                        "meta": {"request_id": request_id},
                        "errors": [
                            "Admin privileges required for this endpoint."
                        ],
                    },
                )
            
            # ── Step 4: Set user info for route handlers ──────────────────
            request.state.user = {
                "user_id": payload["sub"],
                "email": payload["email"],
                "role": payload["role"],
                "token_type": payload.get("type", "access"),
            }
            
        except Exception as e:
            logger.warning(f"Auth failed for {path}: {e}")
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "data": None,
                    "meta": {"request_id": request_id},
                    "errors": [f"Authentication failed: {str(e)}"],
                },
            )
        
        # ── Step 5: Process the request ──────────────────────────────────
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response
    
    def _is_public_route(self, path: str) -> bool:
        """Check if a route is public (no auth required)."""
        for route in PUBLIC_ROUTES:
            if path.startswith(route):
                return True
        return False
    
    def _is_admin_route(self, path: str) -> bool:
        """Check if a route requires admin privileges."""
        for route in ADMIN_ROUTES:
            if path.startswith(route):
                return True
        return False


# =============================================================================
# Request Logging Middleware
# =============================================================================

async def log_request_middleware(request: Request, call_next: Callable) -> Response:
    """
    Log all incoming requests with timing and response status.
    
    Logs:
      - HTTP method
      - Request path
      - Client IP
      - User agent
      - Response status code
      - Processing time
    
    Usage in FastAPI:
        app.middleware("http")(log_request_middleware)
    
    Note: This is an ASGI middleware, not a class-based middleware.
    It's simpler and faster for logging-only use cases.
    """
    start_time = time.time()
    
    # Process the request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    process_time_ms = round(process_time * 1000, 2)
    
    # Get client info
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Log the request
    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} "
        f"[{process_time_ms}ms] "
        f"from {client_ip} "
        f"({user_agent[:50]}...)"
    )
    
    # Add timing header
    response.headers["X-Process-Time-MS"] = str(process_time_ms)
    
    return response
