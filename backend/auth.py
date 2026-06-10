# =============================================================================
# AutoInsight AI — JWT Authentication & RBAC (auth.py)
# Phase 1: Foundation — Security Module
# =============================================================================
"""
Authentication and authorization module using JWT tokens and RBAC.

Provides:
  - Password hashing with bcrypt (passlib)
  - JWT token creation (access + refresh tokens)
  - Token validation and user extraction
  - RBAC role checking (admin, analyst, viewer)
  - Dependency injection functions for FastAPI

Token Architecture:
  - Access Token: 15-minute expiry, sent in Authorization header
  - Refresh Token: 7-day expiry, used to obtain new access tokens
  - Both tokens contain: user_id, email, role

Roles (RBAC):
  - admin: Full system access, user management, configuration
  - analyst: Upload data, run pipelines, generate reports, NLQ
  - viewer: View dashboards, reports, read-only queries

Usage:
    from backend.auth import (
        create_access_token, verify_token, get_current_user,
        require_role, hash_password, verify_password
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Password Hashing ─────────────────────────────────────────────────────
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Higher rounds = more secure, slower
)

# ── Security Scheme ──────────────────────────────────────────────────────
security_scheme = HTTPBearer(
    auto_error=False,  # Don't auto-401; let our middleware handle it
    description="JWT Bearer token for authentication",
)


# =============================================================================
# Password Utilities
# =============================================================================

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password (min 8 chars)
    
    Returns:
        Bcrypt hash string
    
    Example:
        >>> hashed = hash_password("secure_password_123")
        >>> verify_password("secure_password_123", hashed)
        True
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its bcrypt hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored bcrypt hash
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


# =============================================================================
# Token Creation
# =============================================================================

def create_access_token(
    user_id: str,
    email: str,
    role: str,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a JWT access token.
    
    Access tokens are short-lived (default: 15 minutes) and contain:
      - sub: User ID
      - email: User email
      - role: User role for RBAC
      - type: "access"
      - jti: Unique token ID for revocation tracking
      - iat: Issued at timestamp
      - exp: Expiry timestamp
    
    Args:
        user_id: Unique user identifier
        email: User email address
        role: User role (admin, analyst, viewer)
        extra_claims: Optional additional claims to include
    
    Returns:
        Encoded JWT token string
    """
    now = datetime.now(timezone.utc)
    
    claims = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES),
    }
    
    if extra_claims:
        claims.update(extra_claims)
    
    token = jwt.encode(
        claims,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    
    return token


def create_refresh_token(
    user_id: str,
    email: str,
    role: str,
) -> str:
    """
    Create a JWT refresh token.
    
    Refresh tokens are long-lived (default: 7 days) and are used
    exclusively to obtain new access tokens without re-authentication.
    
    Args:
        user_id: Unique user identifier
        email: User email address
        role: User role for RBAC
    
    Returns:
        Encoded JWT refresh token string
    """
    now = datetime.now(timezone.utc)
    
    claims = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "refresh",
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    }
    
    token = jwt.encode(
        claims,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    
    return token


def create_tokens(
    user_id: str,
    email: str,
    role: str,
) -> Dict[str, Any]:
    """
    Create both access and refresh tokens.
    
    Args:
        user_id: Unique user identifier
        email: User email address
        role: User role
    
    Returns:
        Dict containing access_token, refresh_token, token_type, expires_in
    """
    access_token = create_access_token(user_id, email, role)
    refresh_token = create_refresh_token(user_id, email, role)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_expire_seconds,
    }


# =============================================================================
# Token Verification
# =============================================================================

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.
    
    Validates:
      - Token signature
      - Token expiry
      - Token type (access or refresh)
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload dict
    
    Raises:
        HTTPException 401: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        
        # Validate required claims
        if "sub" not in payload or "type" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing required claims",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
        
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    Obtain a new access token using a refresh token.
    
    Args:
        refresh_token: Valid JWT refresh token
    
    Returns:
        New set of tokens (access + refresh)
    
    Raises:
        HTTPException 401: If refresh token is invalid or not a refresh type
    """
    payload = verify_token(refresh_token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type: expected refresh token",
        )
    
    return create_tokens(
        user_id=payload["sub"],
        email=payload["email"],
        role=payload["role"],
    )


# =============================================================================
# FastAPI Dependencies
# =============================================================================

async def get_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[str]:
    """
    Extract JWT token from the Authorization header.
    Optional dependency — returns None if no token is provided.
    
    Args:
        credentials: HTTPBearer credentials from FastAPI
    
    Returns:
        Token string or None
    """
    if credentials is None:
        return None
    return credentials.credentials


async def get_current_user(
    token: str = Depends(get_token_from_header),
) -> Dict[str, Any]:
    """
    Get the current authenticated user from the JWT token.
    
    This is a FastAPI dependency that:
      1. Extracts the token from the Authorization header
      2. Verifies the token signature and expiry
      3. Returns the user payload
    
    Usage in FastAPI routes:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user": user}
    
    Raises:
        HTTPException 401: If no token or invalid token
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_token(token)
    
    # For access token routes, ensure it's an access token
    if payload.get("type") not in ("access", "refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    
    return {
        "user_id": payload["sub"],
        "email": payload["email"],
        "role": payload["role"],
    }


def require_role(allowed_roles: List[str]):
    """
    Factory function that creates a FastAPI dependency for RBAC.
    
    Args:
        allowed_roles: List of roles allowed to access the route
    
    Returns:
        FastAPI dependency function that checks user role
    
    Usage:
        @router.get("/admin/users")
        async def list_users(
            user: dict = Depends(require_role(["admin"]))
        ):
            ...
    
    Example:
        # Allow both admin and analyst
        @router.post("/pipeline/run")
        async def run_pipeline(
            user: dict = Depends(require_role(["admin", "analyst"]))
        ):
            ...
    """
    async def role_checker(
        user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient permissions. "
                    f"Required roles: {', '.join(allowed_roles)}. "
                    f"Your role: {user['role']}"
                ),
            )
        return user
    
    return role_checker


# ── Commonly used role dependencies ────────────────────────────────────────
require_admin = require_role(["admin"])
require_analyst = require_role(["admin", "analyst"])
require_viewer = require_role(["admin", "analyst", "viewer"])
