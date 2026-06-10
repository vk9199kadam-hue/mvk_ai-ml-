# =============================================================================
# AutoInsight AI — File Upload Handler (upload.py)
# Phase 2: Core Pipeline — Upload Management
# =============================================================================
"""
File upload handler with validation, chunked upload support, and progress tracking.

Handles:
  - CSV file upload with size validation (max 100MB)
  - Encoding detection via chardet
  - Chunked upload support for large files
  - Upload progress tracking for SSE streaming
  - Duplicate detection via MD5 hashing
  - Secure file storage via S3/MinIO

Flow:
  1. User initiates upload → Returns upload_id
  2. Client streams file chunks → Progress tracked in Redis
  3. On completion → chardet encoding detection
  4. Placed in staging area → Pipeline ready to consume

Usage:
    from backend.upload import UploadHandler
    
    handler = UploadHandler()
    info = await handler.initiate_upload(filename="data.csv", size=1048576)
    result = await handler.complete_upload(upload_id)
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from backend.cache import cache_manager
from backend.config import settings
from backend.storage import StorageManager

logger = logging.getLogger(__name__)

# Allowed file types
ALLOWED_EXTENSIONS = {".csv", ".tsv", ".json", ".parquet"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "text/tab-separated-values",
    "application/json",
    "application/x-parquet",
    "text/plain",
    "application/octet-stream",
}

# Maximum file size (100MB)
MAX_FILE_SIZE_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024

# Staging directory for temporary uploads
STAGING_DIR = Path("/tmp/autoinsight-uploads")


class UploadStatus(str, Enum):
    """Upload progress status values."""
    INITIATED = "initiated"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UploadError(Exception):
    """Base exception for upload errors."""
    pass


class UploadTooLargeError(UploadError):
    """Raised when file exceeds maximum size."""
    pass


class InvalidFileTypeError(UploadError):
    """Raised when file type is not supported."""
    pass


class UploadNotFoundError(UploadError):
    """Raised when upload ID is not found."""
    pass


class UploadHandler:
    """
    Handles file upload lifecycle: initiate → upload chunks → complete → stage.
    
    Supports:
      - Single-chunk upload (small files < 10MB)
      - Multi-chunk upload (large files, chunked)
      - Progress tracking via Redis SSE
      - Duplicate detection via MD5 hashing
      - Automatic encoding detection
    """
    
    def __init__(self):
        """Initialize the upload handler."""
        self.storage = StorageManager()
        os.makedirs(STAGING_DIR, exist_ok=True)
    
    def _validate_filename(self, filename: str) -> str:
        """
        Validate and sanitize a filename.
        
        Args:
            filename: Original filename
        
        Returns:
            Sanitized filename
        
        Raises:
            InvalidFileTypeError: If extension is not supported
        """
        if not filename or not filename.strip():
            raise InvalidFileTypeError("Filename is empty")
        
        # Extract extension
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise InvalidFileTypeError(
                f"File type '{ext}' is not supported. "
                f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Sanitize filename (remove path separators, special chars)
        sanitized = re.sub(r'[^\w\.\-]', '_', filename)
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:250] + ext
        
        return sanitized
    
    async def initiate_upload(
        self,
        filename: str,
        file_size: int,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiate a new file upload.
        
        Creates an upload session with a unique ID and stores metadata.
        
        Args:
            filename: Original filename
            file_size: File size in bytes
            content_type: MIME type of the file
        
        Returns:
            Upload metadata dict with upload_id for chunked uploads
        
        Raises:
            UploadTooLargeError: If file exceeds max size
            InvalidFileTypeError: If file type is not supported
        """
        # Validate
        sanitized_filename = self._validate_filename(filename)
        
        if file_size > MAX_FILE_SIZE_BYTES:
            raise UploadTooLargeError(
                f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds "
                f"maximum allowed size ({settings.MAX_FILE_SIZE_MB}MB)"
            )
        
        # Generate upload ID
        upload_id = str(uuid.uuid4())
        
        # Create upload directory
        upload_dir = STAGING_DIR / upload_id
        os.makedirs(upload_dir, exist_ok=True)
        
        # Create upload metadata
        upload_info = {
            "upload_id": upload_id,
            "filename": sanitized_filename,
            "original_filename": filename,
            "file_size": file_size,
            "content_type": content_type or "application/octet-stream",
            "status": UploadStatus.INITIATED.value,
            "chunks_received": 0,
            "bytes_received": 0,
            "file_hash": None,
            "encoding": None,
            "staging_path": str(upload_dir / sanitized_filename),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # Store in cache
        await cache_manager.set_upload_progress(
            upload_id, 0.0, UploadStatus.INITIATED.value,
            f"Upload initiated: {sanitized_filename}"
        )
        
        # Store metadata
        await cache_manager.set(
            f"upload_meta:{upload_id}",
            upload_info,
            ttl=7200,  # 2 hours to complete upload
        )
        
        logger.info(
            f"Upload initiated: id={upload_id}, "
            f"file={sanitized_filename}, "
            f"size={file_size} bytes"
        )
        
        return upload_info
    
    async def upload_chunk(
        self,
        upload_id: str,
        chunk_data: bytes,
        chunk_index: int = 0,
        is_final: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload a chunk of file data.
        
        For single-chunk uploads (small files), pass all data with is_final=True.
        For multi-chunk uploads, send chunks sequentially with is_final on last.
        
        Args:
            upload_id: Upload session ID from initiate_upload
            chunk_data: Binary chunk data
            chunk_index: Chunk sequence number
            is_final: Whether this is the final chunk
        
        Returns:
            Updated upload metadata
        
        Raises:
            UploadNotFoundError: If upload_id is not found
        """
        # Get upload metadata
        upload_info = await cache_manager.get(f"upload_meta:{upload_id}")
        if not upload_info:
            raise UploadNotFoundError(f"Upload not found: {upload_id}")
        
        staging_path = upload_info["staging_path"]
        
        # Append chunk to file
        mode = "ab" if os.path.exists(staging_path) and chunk_index > 0 else "wb"
        with open(staging_path, mode) as f:
            f.write(chunk_data)
        
        # Update progress
        bytes_received = upload_info.get("bytes_received", 0) + len(chunk_data)
        progress = min(99.0, (bytes_received / upload_info["file_size"]) * 100) if upload_info["file_size"] > 0 else 50.0
        
        upload_info["bytes_received"] = bytes_received
        upload_info["chunks_received"] = upload_info.get("chunks_received", 0) + 1
        upload_info["status"] = UploadStatus.UPLOADING.value
        upload_info["updated_at"] = datetime.utcnow().isoformat()
        
        # Update cache
        await cache_manager.set_upload_progress(
            upload_id, progress, UploadStatus.UPLOADING.value,
            f"Received chunk {chunk_index + 1} ({bytes_received}/{upload_info['file_size']} bytes)"
        )
        await cache_manager.set(f"upload_meta:{upload_id}", upload_info, ttl=7200)
        
        if is_final:
            return await self.complete_upload(upload_id)
        
        return upload_info
    
    async def complete_upload(self, upload_id: str) -> Dict[str, Any]:
        """
        Finalize an upload: compute hash, detect encoding, stage for pipeline.
        
        Args:
            upload_id: Upload session ID
        
        Returns:
            Complete upload info with hash, encoding, and staging path
        
        Raises:
            UploadNotFoundError: If upload_id is not found
        """
        upload_info = await cache_manager.get(f"upload_meta:{upload_id}")
        if not upload_info:
            raise UploadNotFoundError(f"Upload not found: {upload_id}")
        
        staging_path = upload_info["staging_path"]
        
        if not os.path.exists(staging_path):
            raise UploadError(f"Upload file not found: {staging_path}")
        
        actual_size = os.path.getsize(staging_path)
        
        # Compute MD5 hash
        file_hash = self._compute_hash(staging_path)
        
        # Detect encoding (for CSV/TSV files)
        encoding = None
        ext = os.path.splitext(upload_info["filename"])[1].lower()
        if ext in (".csv", ".tsv"):
            encoding = self._detect_encoding(staging_path)
        
        # Update metadata
        upload_info["file_hash"] = file_hash
        upload_info["encoding"] = encoding or "utf-8"
        upload_info["actual_size"] = actual_size
        upload_info["status"] = UploadStatus.READY.value
        upload_info["updated_at"] = datetime.utcnow().isoformat()
        
        # Store permanently in S3/MinIO
        storage_key = await self.storage.upload_file(staging_path, upload_id)
        upload_info["storage_key"] = storage_key
        
        # Update cache
        await cache_manager.set_upload_progress(
            upload_id, 100.0, UploadStatus.READY.value,
            f"Upload complete: {upload_info['filename']} ({actual_size} bytes)"
        )
        await cache_manager.set(
            f"upload_meta:{upload_id}",
            upload_info,
            ttl=TTL_PIPELINE,
        )
        
        # Remove staging file
        try:
            os.remove(staging_path)
            os.rmdir(os.path.dirname(staging_path))
        except Exception:
            pass
        
        logger.info(
            f"Upload completed: id={upload_id}, "
            f"file={upload_info['filename']}, "
            f"size={actual_size} bytes, "
            f"hash={file_hash[:12]}..., "
            f"encoding={encoding}"
        )
        
        return upload_info
    
    async def get_upload_info(self, upload_id: str) -> Dict[str, Any]:
        """
        Get upload information by ID.
        
        Args:
            upload_id: Upload session ID
        
        Returns:
            Upload metadata
        
        Raises:
            UploadNotFoundError: If upload_id is not found
        """
        upload_info = await cache_manager.get(f"upload_meta:{upload_id}")
        if not upload_info:
            raise UploadNotFoundError(f"Upload not found: {upload_id}")
        return upload_info
    
    async def get_upload_progress(self, upload_id: str) -> Dict[str, Any]:
        """
        Get upload progress for SSE streaming.
        
        Args:
            upload_id: Upload session ID
        
        Returns:
            Progress dict with percentage, status, message
        """
        progress = await cache_manager.get_upload_progress(upload_id)
        if not progress:
            return {
                "file_id": upload_id,
                "progress": 0.0,
                "status": "not_found",
                "message": "Upload not found",
            }
        return progress
    
    async def cancel_upload(self, upload_id: str) -> bool:
        """
        Cancel an upload and clean up staging files.
        
        Args:
            upload_id: Upload session ID
        
        Returns:
            True if cancelled
        """
        upload_info = await cache_manager.get(f"upload_meta:{upload_id}")
        if upload_info:
            staging_path = upload_info.get("staging_path", "")
            if staging_path and os.path.exists(staging_path):
                try:
                    os.remove(staging_path)
                    os.rmdir(os.path.dirname(staging_path))
                except Exception:
                    pass
        
        await cache_manager.delete(f"upload_meta:{upload_id}")
        await cache_manager.set_upload_progress(
            upload_id, 0.0, UploadStatus.CANCELLED.value,
            "Upload cancelled"
        )
        
        logger.info(f"Upload cancelled: {upload_id}")
        return True
    
    def _compute_hash(self, file_path: str) -> str:
        """
        Compute MD5 hash of a file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            MD5 hex digest
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _detect_encoding(self, file_path: str) -> str:
        """
        Detect file encoding using chardet.
        
        Args:
            file_path: Path to the file
        
        Returns:
            Detected encoding name
        """
        try:
            import chardet
            with open(file_path, "rb") as f:
                raw = f.read(100000)  # Read first 100KB
            result = chardet.detect(raw)
            encoding = result.get("encoding", "utf-8")
            confidence = result.get("confidence", 0)
            logger.debug(f"Encoding detected: {encoding} (confidence={confidence:.2f})")
            return encoding
        except ImportError:
            logger.warning("chardet not installed. Defaulting to utf-8.")
            return "utf-8"
        except Exception as e:
            logger.warning(f"Encoding detection failed: {e}. Defaulting to utf-8.")
            return "utf-8"


# Global handler instance
upload_handler = UploadHandler()
