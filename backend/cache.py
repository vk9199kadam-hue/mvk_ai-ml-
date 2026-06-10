# =============================================================================
# AutoInsight AI — Redis Caching Layer (cache.py)
# Phase 2: Core Pipeline — Distributed Cache Infrastructure
# =============================================================================
"""
Redis-based caching layer for data, prompts, pipeline state, and progress.

Provides:
  - Data caching: Store parsed CSV chunks, schema inference results, cleaned DataFrames
  - Prompt caching: Cache frequently used prompt templates
  - Pipeline state: Track pipeline execution progress and status
  - Session cache: Store user sessions and conversation history
  - Cache invalidation: TTL-based expiration and manual invalidation

Cache Strategy:
  - Hot data (accessed frequently): TTL = 1 hour
  - Warm data (recently processed): TTL = 4 hours
  - Cold data (archived): No cache, fetched from PostgreSQL
  - Pipeline state: TTL = 24 hours (for status polling)

Usage:
    from backend.cache import CacheManager
    
    cache = CacheManager()
    await cache.set("schema:file_hash_123", schema_data, ttl=3600)
    data = await cache.get("schema:file_hash_123")
"""

from __future__ import annotations

import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, TypeVar

import redis.asyncio as aioredis
from pydantic import BaseModel

from backend.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default TTL values (in seconds)
TTL_HOT = 3600           # 1 hour
TTL_WARM = 14400         # 4 hours
TTL_PIPELINE = 86400     # 24 hours
TTL_SESSION = 7200       # 2 hours
TTL_PROMPT = 3600        # 1 hour


class CacheManager:
    """
    Distributed cache manager using Redis.
    
    Supports:
      - JSON serialization for dicts/lists
      - Pydantic model serialization
      - Pipeline state tracking with TTL
      - Cache health monitoring
      - Batch operations
    """
    
    def __init__(self):
        """Initialize the cache manager."""
        self._redis: Optional[aioredis.Redis] = None
        self._enabled = True
        self._prefix = "autoinsight:"
    
    async def _get_connection(self) -> aioredis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=False,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                # Test connection
                await self._redis.ping()
                logger.info("Redis cache connection established")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Cache disabled.")
                self._enabled = False
                self._redis = None
        return self._redis
    
    async def _key(self, key: str) -> str:
        """Build full cache key with prefix."""
        return f"{self._prefix}{key}"
    
    async def get(
        self,
        key: str,
        model_class: Optional[type[BaseModel]] = None,
    ) -> Optional[Any]:
        """
        Retrieve a value from cache.
        
        Args:
            key: Cache key
            model_class: If provided, deserialize to this Pydantic model
        
        Returns:
            Cached value or None if not found
        
        Example:
            schema = await cache.get("schema:abc123", SchemaInferenceResponse)
        """
        if not self._enabled:
            return None
        
        try:
            redis = await self._get_connection()
            if redis is None:
                return None
            
            data = await redis.get(await self._key(key))
            if data is None:
                logger.debug(f"Cache MISS: {key}")
                return None
            
            logger.debug(f"Cache HIT: {key}")
            
            if model_class is not None:
                return model_class.model_validate_json(data)
            
            # Try to deserialize
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return data
                
        except Exception as e:
            logger.debug(f"Cache read error for '{key}': {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = TTL_HOT,
        encode_as_json: bool = True,
    ) -> bool:
        """
        Store a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
            encode_as_json: If True, encode as JSON. If False, use pickle.
        
        Returns:
            True if successfully cached
        """
        if not self._enabled:
            return False
        
        try:
            redis = await self._get_connection()
            if redis is None:
                return False
            
            # Serialize
            if isinstance(value, BaseModel):
                serialized = value.model_dump_json()
            elif isinstance(value, (dict, list)):
                serialized = json.dumps(value, default=str)
            elif encode_as_json:
                serialized = json.dumps(value, default=str)
            else:
                serialized = pickle.dumps(value)
            
            await redis.setex(await self._key(key), ttl, serialized)
            logger.debug(f"Cache SET: {key} (TTL={ttl}s)")
            return True
            
        except Exception as e:
            logger.debug(f"Cache write error for '{key}': {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Remove a value from cache.
        
        Args:
            key: Cache key to invalidate
        
        Returns:
            True if key was deleted
        """
        if not self._enabled:
            return False
        
        try:
            redis = await self._get_connection()
            if redis is None:
                return False
            
            result = await redis.delete(await self._key(key))
            logger.debug(f"Cache DEL: {key} (deleted={result > 0})")
            return result > 0
            
        except Exception as e:
            logger.debug(f"Cache delete error for '{key}': {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if key exists
        """
        if not self._enabled:
            return False
        
        try:
            redis = await self._get_connection()
            if redis is None:
                return False
            
            return await redis.exists(await self._key(key)) > 0
            
        except Exception as e:
            logger.debug(f"Cache exists error for '{key}': {e}")
            return False
    
    async def set_pipeline_state(
        self,
        pipeline_id: str,
        state: Dict[str, Any],
    ) -> bool:
        """
        Store pipeline execution state for status polling.
        
        Args:
            pipeline_id: Pipeline execution UUID
            state: Current state dict with status, progress, stages
        
        Returns:
            True if successfully cached
        """
        return await self.set(
            f"pipeline:{pipeline_id}",
            state,
            ttl=TTL_PIPELINE,
        )
    
    async def get_pipeline_state(
        self,
        pipeline_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve pipeline execution state.
        
        Args:
            pipeline_id: Pipeline execution UUID
        
        Returns:
            Pipeline state dict or None
        """
        return await self.get(f"pipeline:{pipeline_id}")
    
    async def update_pipeline_progress(
        self,
        pipeline_id: str,
        stage_name: str,
        progress: float,
        status: str = "running",
        message: str = "",
    ) -> bool:
        """
        Update pipeline progress incrementally.
        
        Args:
            pipeline_id: Pipeline execution UUID
            stage_name: Current stage name
            progress: Progress percentage (0.0 - 100.0)
            status: Current status (running, completed, failed)
            message: Status message
        
        Returns:
            True if updated
        """
        # Get current state
        state = await self.get_pipeline_state(pipeline_id) or {
            "pipeline_id": pipeline_id,
            "status": "running",
            "progress": 0.0,
            "current_stage": stage_name,
            "stages": [],
            "message": "",
        }
        
        # Update
        state["current_stage"] = stage_name
        state["progress"] = max(state.get("progress", 0), progress)
        state["status"] = status
        state["message"] = message
        
        # Update stage if changed
        stages = state.get("stages", [])
        stage_exists = False
        for s in stages:
            if s["name"] == stage_name:
                s["progress"] = progress
                s["status"] = status
                stage_exists = True
                break
        if not stage_exists:
            stages.append({
                "name": stage_name,
                "progress": progress,
                "status": status,
                "started_at": datetime.utcnow().isoformat(),
            })
        state["stages"] = stages
        
        return await self.set_pipeline_state(pipeline_id, state)
    
    async def get_upload_progress(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get upload progress for SSE streaming.
        
        Args:
            file_id: Upload file identifier
        
        Returns:
            Upload progress dict or None
        """
        return await self.get(f"upload:{file_id}")
    
    async def set_upload_progress(
        self,
        file_id: str,
        progress: float,
        status: str = "uploading",
        message: str = "",
    ) -> bool:
        """
        Set upload progress for SSE streaming.
        
        Args:
            file_id: Upload file identifier
            progress: Progress percentage (0.0 - 100.0)
            status: Upload status
            message: Status message
        
        Returns:
            True if set
        """
        return await self.set(
            f"upload:{file_id}",
            {
                "file_id": file_id,
                "progress": progress,
                "status": status,
                "message": message,
                "updated_at": datetime.utcnow().isoformat(),
            },
            ttl=TTL_WARM,
        )
    
    async def cache_dataframe(
        self,
        key: str,
        df: "pl.DataFrame",  # type: ignore
        ttl: int = TTL_WARM,
    ) -> bool:
        """
        Cache a Polars DataFrame as Parquet bytes.
        
        Args:
            key: Cache key
            df: Polars DataFrame to cache
            ttl: TTL in seconds
        
        Returns:
            True if cached
        """
        import polars as pl
        
        try:
            # Serialize DataFrame to Parquet bytes
            buffer = df.write_parquet()
            return await self.set(
                f"df:{key}",
                buffer,
                ttl=ttl,
                encode_as_json=False,
            )
        except Exception as e:
            logger.error(f"Failed to cache DataFrame '{key}': {e}")
            return False
    
    async def get_dataframe(self, key: str) -> Optional["pl.DataFrame"]:  # type: ignore
        """
        Retrieve a cached Polars DataFrame.
        
        Args:
            key: Cache key
        
        Returns:
            Polars DataFrame or None
        """
        import polars as pl
        
        try:
            data = await self.get(f"df:{key}")
            if data is None:
                return None
            return pl.read_parquet(data)
        except Exception as e:
            logger.error(f"Failed to retrieve cached DataFrame '{key}': {e}")
            return None
    
    async def clear_all(self, pattern: str = "*") -> int:
        """
        Clear all cache entries matching a pattern.
        
        Args:
            pattern: Redis glob pattern
        
        Returns:
            Number of keys deleted
        
        Warning: Use with caution. 'clear_all("*")' flushes all cache.
        """
        if not self._enabled:
            return 0
        
        try:
            redis = await self._get_connection()
            if redis is None:
                return 0
            
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor, match=await self._key(pattern), count=100
                )
                if keys:
                    deleted += await redis.delete(*keys)
                if cursor == 0:
                    break
            
            logger.info(f"Cache clear: {deleted} keys deleted (pattern='{pattern}')")
            return deleted
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check cache health.
        
        Returns:
            Dict with status, latency, and info
        """
        start = datetime.utcnow()
        try:
            redis = await self._get_connection()
            if redis is None:
                return {"status": "disabled", "message": "Cache is disabled"}
            
            info = await redis.info()
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "uptime_days": info.get("uptime_in_days", 0),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
    
    async def close(self):
        """Close the Redis connection."""
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None
            logger.info("Redis cache connection closed")


# Global cache instance for convenience
cache_manager = CacheManager()
