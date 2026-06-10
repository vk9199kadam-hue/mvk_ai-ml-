# =============================================================================
# AutoInsight AI — S3/MinIO Storage Manager (storage.py)
# Phase 2: Core Pipeline — File Storage & Retrieval
# =============================================================================
"""
Storage abstraction layer for S3/MinIO-compatible object storage.

Handles:
  - Upload files to S3/MinIO with configurable bucket and path
  - Download files from S3/MinIO 
  - Generate pre-signed URLs for secure access
  - Parquet file snapshots for versioned cleaning history
  - Export file storage (PDF, HTML, Excel)
  - Fallback to local filesystem when S3 is unavailable

Usage:
    from backend.storage import StorageManager
    
    storage = StorageManager()
    url = await storage.upload_file("/path/to/file.csv", "pipeline-uuid")
    data = await storage.download_file("pipeline-uuid/file.csv")
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, BinaryIO, Union

import polars as pl

from backend.config import settings

logger = logging.getLogger(__name__)

LOCAL_STORAGE_DIR = Path("/tmp/autoinsight-storage")


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class StorageManager:
    """
    File storage manager supporting S3/MinIO with local filesystem fallback.
    
    Stores files organized as: {bucket}/{prefix}/{upload_id}/{filename}
    """
    
    def __init__(self):
        """Initialize the storage manager."""
        self._s3_client = None
        self._bucket = settings.S3_BUCKET
        self._prefix = "autoinsight"
        self._local_fallback = False
        
        # Create local storage directory
        os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)
        
        # Try to initialize S3 client
        try:
            import boto3
            from botocore.config import Config
            
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
                config=Config(
                    connect_timeout=5,
                    read_timeout=10,
                    retries={"max_attempts": 3},
                ),
                use_ssl=settings.S3_SECURE,
            )
            
            # Ensure bucket exists
            self._ensure_bucket()
            logger.info(f"S3 storage initialized: {settings.S3_ENDPOINT}/{self._bucket}")
            
        except Exception as e:
            logger.warning(f"S3 initialization failed: {e}. Using local filesystem fallback.")
            self._local_fallback = True
    
    def _ensure_bucket(self):
        """Ensure the S3 bucket exists, creating it if necessary."""
        try:
            self._s3_client.head_bucket(Bucket=self._bucket)
        except Exception:
            try:
                self._s3_client.create_bucket(Bucket=self._bucket)
                logger.info(f"Created S3 bucket: {self._bucket}")
            except Exception as e:
                logger.error(f"Failed to create S3 bucket: {e}")
                raise
    
    def _get_key(self, upload_id: str, filename: str) -> str:
        """Get the full S3 key for a file."""
        return f"{self._prefix}/{upload_id}/{filename}"
    
    async def upload_file(
        self,
        local_path: str,
        upload_id: str,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to storage.
        
        Args:
            local_path: Local filesystem path to the file
            upload_id: Upload or pipeline identifier
            filename: Remote filename (defaults to basename of local_path)
            content_type: MIME type of the file
        
        Returns:
            Storage metadata dict with key, url, and size
        
        Raises:
            StorageError: If upload fails
        """
        if filename is None:
            filename = os.path.basename(local_path)
        
        file_size = os.path.getsize(local_path)
        key = self._get_key(upload_id, filename)
        
        if self._local_fallback:
            # Local filesystem fallback
            dest = LOCAL_STORAGE_DIR / key
            os.makedirs(dest.parent, exist_ok=True)
            
            import shutil
            shutil.copy2(local_path, dest)
            
            logger.info(f"Local storage upload: {dest} ({file_size} bytes)")
            return {
                "key": key,
                "url": str(dest),
                "size": file_size,
                "storage_type": "local",
            }
        
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            
            with open(local_path, "rb") as f:
                self._s3_client.upload_fileobj(
                    f, self._bucket, key, ExtraArgs=extra_args or None
                )
            
            # Generate URL
            url = f"{settings.S3_ENDPOINT}/{self._bucket}/{key}"
            
            logger.info(f"S3 upload: {key} ({file_size} bytes)")
            return {
                "key": key,
                "url": url,
                "size": file_size,
                "storage_type": "s3",
                "bucket": self._bucket,
            }
        
        except Exception as e:
            raise StorageError(f"Failed to upload file '{local_path}': {e}")
    
    async def download_file(
        self,
        key: str,
        local_path: Optional[str] = None,
    ) -> Union[bytes, str]:
        """
        Download a file from storage.
        
        Args:
            key: Storage key (e.g., "autoinsight/{upload_id}/file.csv")
            local_path: If provided, save to this path and return path
        
        Returns:
            File bytes if no local_path, or local path string
        
        Raises:
            StorageError: If download fails
        """
        if self._local_fallback:
            src = LOCAL_STORAGE_DIR / key
            if not src.exists():
                raise StorageError(f"File not found: {key}")
            
            if local_path:
                import shutil
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                shutil.copy2(src, local_path)
                return local_path
            
            with open(src, "rb") as f:
                return f.read()
        
        try:
            buffer = io.BytesIO()
            self._s3_client.download_fileobj(self._bucket, key, buffer)
            buffer.seek(0)
            data = buffer.read()
            
            if local_path:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(data)
                return local_path
            
            return data
        
        except Exception as e:
            raise StorageError(f"Failed to download file '{key}': {e}")
    
    async def delete_file(self, key: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            key: Storage key to delete
        
        Returns:
            True if deleted
        """
        if self._local_fallback:
            path = LOCAL_STORAGE_DIR / key
            if path.exists():
                os.remove(path)
                return True
            return False
        
        try:
            self._s3_client.delete_object(Bucket=self._bucket, Key=key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete file '{key}': {e}")
            return False
    
    async def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        List files in storage with the given prefix.
        
        Args:
            prefix: Key prefix to filter by
        
        Returns:
            List of file metadata dicts
        """
        full_prefix = f"{self._prefix}/{prefix}" if prefix else self._prefix
        
        if self._local_fallback:
            base = LOCAL_STORAGE_DIR / full_prefix
            files = []
            if base.exists():
                for p in base.rglob("*"):
                    if p.is_file():
                        files.append({
                            "key": str(p.relative_to(LOCAL_STORAGE_DIR)),
                            "size": p.stat().st_size,
                            "last_modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                        })
            return files
        
        try:
            response = self._s3_client.list_objects_v2(
                Bucket=self._bucket, Prefix=full_prefix
            )
            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                })
            return files
        except Exception as e:
            logger.error(f"Failed to list files with prefix '{prefix}': {e}")
            return []
    
    async def save_parquet_snapshot(
        self,
        df: "pl.DataFrame",  # type: ignore
        upload_id: str,
        version: str,
    ) -> str:
        """
        Save a Polars DataFrame as a versioned Parquet snapshot.
        
        Args:
            df: DataFrame to save
            upload_id: Pipeline upload identifier
            version: Version string (e.g., "v1.0-cleaned")
        
        Returns:
            Storage key of the saved Parquet file
        """
        filename = f"{version}.parquet"
        key = self._get_key(upload_id, filename)
        
        # Write to bytes
        buffer = df.write_parquet(compression=settings.PARQUET_COMPRESSION)
        
        if self._local_fallback:
            dest = LOCAL_STORAGE_DIR / key
            os.makedirs(dest.parent, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(buffer)
        else:
            self._s3_client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=buffer,
                ContentType="application/x-parquet",
            )
        
        logger.info(f"Parquet snapshot saved: {key} ({len(buffer)} bytes)")
        return key
    
    async def load_parquet_snapshot(self, key: str) -> "pl.DataFrame":  # type: ignore
        """
        Load a Parquet snapshot from storage.
        
        Args:
            key: Storage key of the Parquet file
        
        Returns:
            Polars DataFrame
        """
        data = await self.download_file(key)
        return pl.read_parquet(io.BytesIO(data) if isinstance(data, bytes) else data)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check storage health."""
        if self._local_fallback:
            return {
                "status": "healthy",
                "type": "local_filesystem",
                "path": str(LOCAL_STORAGE_DIR),
            }
        
        try:
            self._s3_client.head_bucket(Bucket=self._bucket)
            return {
                "status": "healthy",
                "type": "s3",
                "endpoint": settings.S3_ENDPOINT,
                "bucket": self._bucket,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "type": "s3",
                "error": str(e),
            }


# Global storage instance
storage_manager = StorageManager()
