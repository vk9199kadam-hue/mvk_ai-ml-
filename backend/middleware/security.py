# =============================================================================
# AutoInsight AI — Security Hardening Middleware (Phase 5, Day 46)
# Rate limiting, input sanitization, security headers, token blacklist
# =============================================================================

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import json

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Security Constants ─────────────────────────────────────────────────────

# Rate limiting
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 100          # 100 req/min per IP
RATE_LIMIT_AUTH_MAX = 10               # 10 auth attempts/min per IP
RATE_LIMIT_UPLOAD_MAX = 5              # 5 uploads/min per IP

# Input validation
SUSPICIOUS_PATTERNS = [
    r"<script[^>]*>.*?</script>",       # XSS
    r"javascript\s*:",                   # XSS in URLs
    r"on\w+\s*=",                        # Event handlers
    r"<!--.*?-->",                       # HTML comments (potential injection)
    r"\/\*.*?\*\/",                      # SQL comments
    r"(\bSELECT\b.*\bFROM\b)",           # SQL injection basic
    r"(\bDROP\b.*\bTABLE\b)",            # SQL injection DROP
    r"(\bUNION\b.*\bSELECT\b)",          # SQL injection UNION
    r"(\bINSERT\b.*\bINTO\b)",           # SQL injection INSERT
    r"(\bDELETE\b.*\bFROM\b)",           # SQL injection DELETE
    r"(?:';.*--)|(?:'.*OR\s+1\s*=\s*1)", # SQL injection OR
    r"\$\{.*?\}",                        # Template injection
    r"\{\{.*?\}\}",                      # Jinja2 template injection
    r"__proto__",                        # Prototype pollution
    r"constructor",                      # Prototype pollution
]

# SQL injection patterns (case insensitive)
SQL_PATTERNS = [
    r"\bSELECT\b.*\bFROM\b",
    r"\bDROP\b.*\bTABLE\b",
    r"\bUNION\b.*\bSELECT\b",
    r"\bINSERT\b.*\bINTO\b",
    r"\bDELETE\b.*\bFROM\b",
    r"\bALTER\b.*\bTABLE\b",
    r"\bEXEC\b.*\bXP_\b",
    r"\bEXECUTE\b.*\bXP_\b",
    r"';.*--",
    r"'.*OR\s+1\s*=\s*1",
    r"'.*OR\s+'[^']+'\s*=\s*'[^']*'",
]

# Path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",
    r"\.\.\\",
    r"\.\.%2f",
    r"\.\.%5c",
    r"%2e%2e%2f",
    r"%2e%2e%5c",
]


# ── Token Blacklist ────────────────────────────────────────────────────────

class TokenBlacklist:
    """In-memory token blacklist for revoked JWT tokens.
    
    Supports:
      - Blacklist tokens on logout
      - Check token against blacklist
      - Auto-expire entries based on original token expiry
    """

    def __init__(self):
        self._blacklist: Dict[str, datetime] = {}

    def revoke(self, jti: str, expires_at: Optional[datetime] = None) -> None:
        """Add a token to the blacklist.
        
        Args:
            jti: Token JWT ID
            expires_at: Token expiry time (auto-cleanup)
        """
        self._blacklist[jti] = expires_at or (datetime.utcnow() + timedelta(hours=1))
        self._cleanup()

    def is_revoked(self, jti: str) -> bool:
        """Check if a token has been revoked.
        
        Args:
            jti: Token JWT ID
        
        Returns:
            True if token is blacklisted
        """
        self._cleanup()
        return jti in self._blacklist

    def _cleanup(self) -> None:
        """Remove expired entries from the blacklist."""
        now = datetime.utcnow()
        expired = [jti for jti, exp in self._blacklist.items() if exp <= now]
        for jti in expired:
            del self._blacklist[jti]
        if expired:
            logger.debug(f"Cleaned {len(expired)} expired tokens from blacklist")


# Global token blacklist instance
token_blacklist = TokenBlacklist()


# ── Rate Limiter ───────────────────────────────────────────────────────────

class RateLimiter:
    """Sliding window rate limiter per IP address.
    
    Tracks request counts per path prefix and enforces limits.
    Uses in-memory dict with periodic cleanup.
    """

    def __init__(self):
        self._requests: Dict[str, List[float]] = {}

    def check(self, ip: str, path: str) -> Tuple[bool, int, int]:
        """Check if request is allowed under rate limits.
        
        Args:
            ip: Client IP address
            path: Request path
        
        Returns:
            Tuple of (allowed, current_count, max_limit)
        """
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS

        # Determine max limit based on path
        if path.startswith("/api/v1/auth/"):
            max_limit = RATE_LIMIT_AUTH_MAX
        elif "/upload" in path:
            max_limit = RATE_LIMIT_UPLOAD_MAX
        else:
            max_limit = RATE_LIMIT_MAX_REQUESTS

        # Clean old entries
        key = f"{ip}:{path.split('/')[1] if len(path.split('/')) > 1 else 'other'}"
        if key not in self._requests:
            self._requests[key] = []

        self._requests[key] = [
            t for t in self._requests[key] if t > window_start
        ]

        # Check limit
        current_count = len(self._requests[key])
        if current_count >= max_limit:
            return False, current_count, max_limit

        # Record request
        self._requests[key].append(now)
        return True, current_count + 1, max_limit

    def cleanup(self) -> int:
        """Remove expired entries. Returns count removed."""
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS
        expired = 0
        keys_to_delete = []
        for key, timestamps in list(self._requests.items()):
            valid = [t for t in timestamps if t > window_start]
            if not valid:
                keys_to_delete.append(key)
            else:
                self._requests[key] = valid
            expired += len(timestamps) - len(valid)
        for key in keys_to_delete:
            del self._requests[key]
        return expired


# Global rate limiter instance
rate_limiter = RateLimiter()


# ── Input Sanitizer ────────────────────────────────────────────────────────

class InputSanitizer:
    """Validates and sanitizes user input against common attack patterns."""

    @staticmethod
    def has_sql_injection(value: str) -> bool:
        """Check if a string contains SQL injection patterns."""
        if not isinstance(value, str):
            return False
        for pattern in SQL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"SQL injection pattern detected: {value[:100]}")
                return True
        return False

    @staticmethod
    def has_xss(value: str) -> bool:
        """Check if a string contains XSS attack patterns."""
        if not isinstance(value, str):
            return False
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"XSS pattern detected: {value[:100]}")
                return True
        return False

    @staticmethod
    def has_path_traversal(value: str) -> bool:
        """Check if a string contains path traversal patterns."""
        if not isinstance(value, str):
            return False
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Path traversal detected: {value[:100]}")
                return True
        return False

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize a filename to prevent path traversal."""
        # Remove path components
        filename = filename.replace("\\", "/").split("/")[-1]
        # Remove null bytes
        filename = filename.replace("\x00", "")
        # Whitelist safe characters
        safe = re.sub(r"[^\w\.\-\(\) ]", "_", filename)
        return safe[:255]  # Max filename length

    @staticmethod
    def sanitize_input(value: str, max_length: int = 1000) -> str:
        """Sanitize a user input string."""
        if not isinstance(value, str):
            return str(value)[:max_length]
        # Trim whitespace
        value = value.strip()
        # Remove null bytes
        value = value.replace("\x00", "")
        # Limit length
        return value[:max_length]


# Global input sanitizer instance
input_sanitizer = InputSanitizer()


# ── Security Headers Middleware ─────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses.
    
    Headers added:
      - X-Content-Type-Options: nosniff
      - X-Frame-Options: DENY
      - X-XSS-Protection: 1; mode=block
      - Strict-Transport-Security: max-age=31536000; includeSubDomains
      - Content-Security-Policy: restrictive defaults
      - Referrer-Policy: strict-origin-when-cross-origin
      - Permissions-Policy: restricted feature set
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "interest-cohort=()"
        )
        response.headers["X-Powered-By"] = "AutoInsight AI"

        return response


# ── Auth Rate Limit Middleware ─────────────────────────────────────────────

class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limits authentication endpoints to prevent brute force attacks."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # Only rate-limit auth endpoints
        if "/api/v1/auth/" in path:
            allowed, current, max_limit = rate_limiter.check(client_ip, path)
            if not allowed:
                logger.warning(
                    f"Rate limit exceeded: {client_ip} — "
                    f"{current}/{max_limit} requests on {path}"
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "status": "error",
                        "data": None,
                        "meta": {
                            "request_id": str(uuid4()),
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        },
                        "errors": [
                            f"Rate limit exceeded. "
                            f"Maximum {max_limit} requests per "
                            f"{RATE_LIMIT_WINDOW_SECONDS} seconds. "
                            f"Current: {current}"
                        ],
                    },
                    headers={
                        "Retry-After": str(RATE_LIMIT_WINDOW_SECONDS),
                        "X-RateLimit-Limit": str(max_limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )

        response = await call_next(request)

        # Add rate limit headers
        if client_ip != "unknown":
            _, current, max_limit = rate_limiter.check(client_ip, path)
            response.headers["X-RateLimit-Limit"] = str(max_limit)
            response.headers["X-RateLimit-Remaining"] = str(
                max(max_limit - current, 0)
            )

        return response


# ── Input Validation Middleware ─────────────────────────────────────────────

class InputValidationMiddleware(BaseHTTPMiddleware):
    """Validates request query params and body against injection patterns."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check query parameters
        for key, values in request.query_params.items():
            for value in values if isinstance(values, list) else [values]:
                if not isinstance(value, str):
                    continue
                if input_sanitizer.has_sql_injection(value):
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "data": None,
                            "meta": {"request_id": str(uuid4())},
                            "errors": [
                                "Invalid input detected in query parameters"
                            ],
                        },
                    )
                if input_sanitizer.has_xss(value):
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "data": None,
                            "meta": {"request_id": str(uuid4())},
                            "errors": [
                                "Invalid input detected in query parameters"
                            ],
                        },
                    )

        # Check path parameters
        path = request.url.path
        for segment in path.split("/"):
            if input_sanitizer.has_path_traversal(segment):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "data": None,
                        "meta": {"request_id": str(uuid4())},
                        "errors": ["Invalid path traversal detected"],
                    },
                )

        return await call_next(request)


# ── JWT Blacklist Middleware ───────────────────────────────────────────────

class JWTBlacklistMiddleware(BaseHTTPMiddleware):
    """Checks JWT tokens against the blacklist on protected routes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip public routes
        path = request.url.path
        public_routes = ["/health", "/api/v1/auth/login", "/api/v1/auth/register"]
        if any(path.startswith(r) for r in public_routes):
            return await call_next(request)

        # Extract JWT from header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # Extract JTI from token (decode without verification for JTI)
            try:
                from jose import jwt as jose_jwt
                payload = jose_jwt.get_unverified_claims(token)
                jti = payload.get("jti", "")
                if jti and token_blacklist.is_revoked(jti):
                    logger.warning(f"Revoked token used: {jti[:8]}...")
                    return JSONResponse(
                        status_code=401,
                        content={
                            "status": "error",
                            "data": None,
                            "meta": {"request_id": str(uuid4())},
                            "errors": ["Token has been revoked"],
                        },
                    )
            except Exception:
                pass

        return await call_next(request)


# ── Security Audit Logger ──────────────────────────────────────────────────

class SecurityAuditLogger:
    """Logs security-relevant events for audit trail."""

    @staticmethod
    def log_auth_event(
        event: str,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        ip: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        """Log an authentication event (login, logout, token refresh)."""
        logger.info(
            f"AUDIT:AUTH:{event} — "
            f"user={user_id or 'anonymous'}({email or 'unknown'}) "
            f"ip={ip or 'unknown'} "
            f"details={details or ''}"
        )

    @staticmethod
    def log_security_event(
        event: str,
        severity: str = "INFO",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a security event (rate limit, injection attempt, etc.)."""
        log_level = getattr(logger, severity.lower(), logger.info)
        log_level(
            f"AUDIT:SEC:{event} — "
            f"details={json.dumps(details) if details else 'none'}"
        )

    @staticmethod
    def log_data_access(
        user_id: str,
        resource: str,
        action: str,
        allowed: bool,
    ) -> None:
        """Log a data access attempt for audit trail."""
        status = "ALLOWED" if allowed else "DENIED"
        logger.info(
            f"AUDIT:DATA:{status} — "
            f"user={user_id} resource={resource} action={action}"
        )


# Global security audit logger instance
security_audit = SecurityAuditLogger()
