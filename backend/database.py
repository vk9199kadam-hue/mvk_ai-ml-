# =============================================================================
# AutoInsight AI — Database Connection & Query Utilities (database.py)
# Phase 1: Foundation — Async PostgreSQL with Connection Pooling
# =============================================================================
"""
Asynchronous PostgreSQL database connection management using asyncpg.

Provides:
  - Connection pool management (create, acquire, release)
  - CRUD utility functions for common operations
  - JSONB serialization for Pydantic models
  - Row-to-dict mapping with type coercion

Usage:
    from backend.database import get_pool, close_pool
    
    async def main():
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from backend.config import settings

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None

# Type variable for generic database operations
T = TypeVar("T", bound=BaseModel)


# =============================================================================
# Pool Management
# =============================================================================

async def get_pool() -> asyncpg.Pool:
    """
    Get or create the database connection pool.
    
    The pool is created once and reused across the application lifetime.
    Pool configuration:
      - min_size: 2 connections (always available)
      - max_size: 20 connections (concurrent operations)
      - max_queries: 50000 queries per connection before recycling
      - max_inactive_connection_lifetime: 300s (5 min idle timeout)
    
    Returns:
        asyncpg.Pool instance for database operations
    """
    global _pool
    
    if _pool is None or _pool._closed:
        logger.info(
            "Creating database connection pool",
            extra={"db_url": settings.DATABASE_URL.replace(settings.DB_PASSWORD, "****")},
        )
        
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=20,
            max_queries=50000,
            max_inactive_connection_lifetime=300.0,
            command_timeout=60,
            # Register custom codec for JSONB serialization
            init=schema_init,
        )
        
        logger.info("Database connection pool created successfully")
    
    return _pool


async def schema_init(conn: asyncpg.Connection) -> None:
    """Initialize connection with custom codecs and schema search path."""
    # Set the search path
    await conn.execute("SET search_path TO public")
    
    # Register UUID ↔ str codec
    await conn.set_type_codec(
        "uuid",
        encoder=str,
        decoder=lambda x: str(x) if not isinstance(x, str) else x,
        schema="pg_catalog",
    )


async def close_pool() -> None:
    """Close the database connection pool gracefully."""
    global _pool
    
    if _pool and not _pool._closed:
        logger.info("Closing database connection pool")
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")


async def health_check() -> Dict[str, Any]:
    """
    Check database connectivity by executing a simple query.
    
    Returns:
        Dict with connection status and server version
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            return {
                "status": "healthy",
                "server_version": version,
                "pool_size": pool.get_size(),
                "pool_idle": len(pool._holders) if hasattr(pool, '_holders') else 'N/A',
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


# =============================================================================
# Generic CRUD Utilities
# =============================================================================

async def insert_one(
    table: str,
    data: Dict[str, Any],
    returning: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Insert a single row into a table.
    
    Args:
        table: Table name
        data: Column-value mapping
        returning: Column to return (e.g., "id"), None = no return
    
    Returns:
        The returned row as dict, or None
    
    Example:
        user = await insert_one("users", {"email": "test@test.com", "name": "Test"})
    """
    pool = await get_pool()
    
    columns = ", ".join(data.keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
    values = list(data.values())
    
    query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    if returning:
        query += f" RETURNING {returning}"
    
    async with pool.acquire() as conn:
        if returning:
            row = await conn.fetchrow(query, *values)
            return dict(row) if row else None
        else:
            await conn.execute(query, *values)
            return None


async def insert_many(
    table: str,
    data: List[Dict[str, Any]],
    batch_size: int = 100,
) -> int:
    """
    Bulk insert multiple rows into a table.
    
    Args:
        table: Table name
        data: List of column-value mappings
        batch_size: Rows per INSERT statement
    
    Returns:
        Number of rows inserted
    """
    if not data:
        return 0
    
    pool = await get_pool()
    columns = ", ".join(data[0].keys())
    placeholders = ", ".join(f"${i+1}" for i in range(len(data[0])))
    
    query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    
    total_inserted = 0
    async with pool.acquire() as conn:
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            for row in batch:
                await conn.execute(query, *list(row.values()))
                total_inserted += 1
    
    return total_inserted


async def fetch_one(
    table: str,
    conditions: Optional[Dict[str, Any]] = None,
    order_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single row matching conditions.
    
    Args:
        table: Table name
        conditions: Column-value filter conditions (AND)
        order_by: Optional ORDER BY clause
    
    Returns:
        Row as dict, or None if not found
    """
    pool = await get_pool()
    
    query = f"SELECT * FROM {table}"
    params = []
    
    if conditions:
        where_clauses = []
        for i, (col, val) in enumerate(conditions.items()):
            where_clauses.append(f"{col} = ${i+1}")
            params.append(val)
        query += " WHERE " + " AND ".join(where_clauses)
    
    if order_by:
        query += f" ORDER BY {order_by}"
    
    query += " LIMIT 1"
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
        return dict(row) if row else None


async def fetch_many(
    table: str,
    conditions: Optional[Dict[str, Any]] = None,
    order_by: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Fetch multiple rows matching conditions.
    
    Args:
        table: Table name
        conditions: Column-value filter conditions (AND)
        order_by: Optional ORDER BY clause
        limit: Maximum rows to return
        offset: Row offset for pagination
    
    Returns:
        List of rows as dicts
    """
    pool = await get_pool()
    
    query = f"SELECT * FROM {table}"
    params = []
    
    if conditions:
        where_clauses = []
        for i, (col, val) in enumerate(conditions.items()):
            where_clauses.append(f"{col} = ${i+1}")
            params.append(val)
        query += " WHERE " + " AND ".join(where_clauses)
    
    if order_by:
        query += f" ORDER BY {order_by}"
    
    query += f" LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}"
    params.extend([limit, offset])
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def update_one(
    table: str,
    data: Dict[str, Any],
    conditions: Dict[str, Any],
) -> int:
    """
    Update rows matching conditions.
    
    Args:
        table: Table name
        data: Column-value pairs to update
        conditions: Filter conditions (AND)
    
    Returns:
        Number of rows updated
    """
    pool = await get_pool()
    
    set_clauses = []
    params = []
    
    for i, (col, val) in enumerate(data.items()):
        set_clauses.append(f"{col} = ${i+1}")
        params.append(val)
    
    where_clauses = []
    for i, (col, val) in enumerate(conditions.items()):
        where_clauses.append(f"{col} = ${len(params) + i + 1}")
        params.append(val)
    
    query = (
        f"UPDATE {table} "
        f"SET {', '.join(set_clauses)} "
        f"WHERE {' AND '.join(where_clauses)}"
    )
    
    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)
        # result is like "UPDATE 3" — parse the count
        return int(result.split()[-1]) if result else 0


async def delete_one(
    table: str,
    conditions: Dict[str, Any],
) -> int:
    """
    Delete rows matching conditions.
    
    Args:
        table: Table name
        conditions: Filter conditions (AND)
    
    Returns:
        Number of rows deleted
    """
    pool = await get_pool()
    
    where_clauses = []
    params = []
    
    for i, (col, val) in enumerate(conditions.items()):
        where_clauses.append(f"{col} = ${i+1}")
        params.append(val)
    
    query = f"DELETE FROM {table} WHERE {' AND '.join(where_clauses)}"
    
    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)
        return int(result.split()[-1]) if result else 0


# =============================================================================
# Serialization Helpers
# =============================================================================

def serialize_model(model: BaseModel) -> Dict[str, Any]:
    """
    Serialize a Pydantic model to a dict for database storage.
    Handles JSONB fields, UUIDs, and datetime objects.
    
    Args:
        model: Pydantic model instance
    
    Returns:
        Dict ready for database insertion
    """
    data = model.model_dump()
    
    # Convert datetime objects to ISO strings
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    
    return data


def deserialize_row(
    row: Dict[str, Any],
    model_class: type[T],
) -> T:
    """
    Deserialize a database row into a Pydantic model.
    Handles JSONB string parsing and type coercion.
    
    Args:
        row: Database row as dict
        model_class: Pydantic model class to instantiate
    
    Returns:
        Instantiated Pydantic model
    """
    data = dict(row)
    
    # Parse JSONB fields if they're strings
    for key, value in data.items():
        if isinstance(value, str):
            try:
                data[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass  # Keep as string
    
    return model_class(**data)
