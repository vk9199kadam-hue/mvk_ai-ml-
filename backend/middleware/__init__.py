# =============================================================================
# AutoInsight AI — Middleware Package
# Phase 1: Foundation
# =============================================================================
"""
Middleware components for the FastAPI application.

Includes:
  - Authentication middleware (JWT validation)
  - RBAC authorization enforcement
  - Request logging middleware
  - CORS middleware configuration
"""

from backend.middleware.auth import AuthMiddleware, log_request_middleware
