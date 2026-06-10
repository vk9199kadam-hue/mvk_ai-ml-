# =============================================================================
# AutoInsight AI — Application Configuration (config.py)
# Phase 1: Foundation — Environment-Based Settings
# =============================================================================
"""
Centralized configuration management using Pydantic Settings.
All configuration values are loaded from environment variables (.env).
Provides type validation and default values for all settings.

Usage:
    from backend.config import settings
    # Access any setting: settings.DATABASE_URL, settings.GROQ_API_KEY, etc.
"""

from __future__ import annotations

from typing import List, Optional
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All values can be overridden via .env file or system environment variables.
    Type validation ensures configuration correctness at startup.
    """
    
    # ── Application Meta ──────────────────────────────────────────────────
    APP_NAME: str = Field(default="AutoInsight AI", alias="APP_NAME")
    APP_VERSION: str = Field(default="1.0.0", alias="APP_VERSION")
    DEBUG: bool = Field(default=True, alias="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql://autoinsight:changeme@localhost:5432/autoinsight",
        alias="DATABASE_URL",
    )
    DB_HOST: str = Field(default="localhost", alias="DB_HOST")
    DB_PORT: int = Field(default=5432, alias="DB_PORT")
    DB_NAME: str = Field(default="autoinsight", alias="DB_NAME")
    DB_USER: str = Field(default="autoinsight", alias="DB_USER")
    DB_PASSWORD: str = Field(default="changeme", alias="DB_PASSWORD")
    
    # ── Redis (Cache + Task Queue) ────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )
    REDIS_HOST: str = Field(default="localhost", alias="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, alias="REDIS_PORT")
    REDIS_DB: int = Field(default=0, alias="REDIS_DB")
    
    # ── S3 File Storage ───────────────────────────────────────────────────
    S3_ENDPOINT: str = Field(default="http://localhost:9000", alias="S3_ENDPOINT")
    S3_ACCESS_KEY: str = Field(default="minioadmin", alias="S3_ACCESS_KEY")
    S3_SECRET_KEY: str = Field(default="minioadmin", alias="S3_SECRET_KEY")
    S3_BUCKET: str = Field(default="autoinsight-files", alias="S3_BUCKET")
    S3_REGION: str = Field(default="us-east-1", alias="S3_REGION")
    S3_SECURE: bool = Field(default=False, alias="S3_SECURE")
    
    # ── LLM Provider Configuration ────────────────────────────────────────
    # Primary: Qwen 2.5 72B via Groq Free Tier
    # Fallback: Llama 3.1 8B via local Ollama
    LLM_PROVIDER: str = Field(
        default="groq",
        alias="LLM_PROVIDER",
        description="LLM provider: 'groq' or 'ollama'",
    )
    GROQ_API_KEY: Optional[str] = Field(
        default=None, alias="GROQ_API_KEY",
        description="Groq API key for Qwen 2.5 72B access",
    )
    GROQ_MODEL: str = Field(
        default="qwen-2.5-72b",
        alias="GROQ_MODEL",
        description="Groq model name",
    )
    GROQ_MAX_RETRIES: int = Field(
        default=3, alias="GROQ_MAX_RETRIES",
        ge=0, le=10,
        description="Maximum LLM retry attempts",
    )
    GROQ_TIMEOUT_SECONDS: int = Field(
        default=30, alias="GROQ_TIMEOUT_SECONDS",
        description="LLM timeout in seconds",
    )
    
    # Ollama (fallback — local)
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        alias="OLLAMA_BASE_URL",
        description="Ollama API base URL",
    )
    OLLAMA_MODEL: str = Field(
        default="llama3.1:8b",
        alias="OLLAMA_MODEL",
        description="Ollama model name",
    )
    
    # ── JWT Authentication ────────────────────────────────────────────────
    JWT_SECRET: str = Field(
        default="your_jwt_secret_here_change_in_production",
        alias="JWT_SECRET",
        description="JWT signing secret key",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256", alias="JWT_ALGORITHM",
        description="JWT signing algorithm",
    )
    JWT_ACCESS_EXPIRE_MINUTES: int = Field(
        default=15, alias="JWT_ACCESS_EXPIRE_MINUTES",
        description="Access token expiry in minutes",
    )
    JWT_REFRESH_EXPIRE_DAYS: int = Field(
        default=7, alias="JWT_REFRESH_EXPIRE_DAYS",
        description="Refresh token expiry in days",
    )
    
    # ── Pipeline Configuration ────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = Field(
        default=100, alias="MAX_FILE_SIZE_MB",
        description="Maximum CSV file size in MB",
    )
    PIPELINE_TIMEOUT_SECONDS: int = Field(
        default=300, alias="PIPELINE_TIMEOUT_SECONDS",
        description="Pipeline execution timeout",
    )
    CHUNK_SIZE_MB: int = Field(
        default=10, alias="CHUNK_SIZE_MB",
        description="Processing chunk size in MB",
    )
    PARQUET_COMPRESSION: str = Field(
        default="snappy", alias="PARQUET_COMPRESSION",
        description="Parquet compression codec",
    )
    
    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        alias="CORS_ORIGINS",
        description="Comma-separated allowed CORS origins",
    )
    
    # ── Celery ────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_BROKER_URL",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/2",
        alias="CELERY_RESULT_BACKEND",
    )
    
    # ── Confidence Gating Thresholds ──────────────────────────────────────
    CONFIDENCE_AUTO_APPLY: float = Field(
        default=0.90, alias="CONFIDENCE_AUTO_APPLY",
        ge=0.0, le=1.0,
        description="Confidence threshold for auto-apply (green)",
    )
    CONFIDENCE_MANUAL_APPROVAL: float = Field(
        default=0.70, alias="CONFIDENCE_MANUAL_APPROVAL",
        ge=0.0, le=1.0,
        description="Confidence threshold for manual approval (yellow)",
    )
    CONFIDENCE_REVIEW_REQUIRED: float = Field(
        default=0.50, alias="CONFIDENCE_REVIEW_REQUIRED",
        ge=0.0, le=1.0,
        description="Confidence threshold for review required (orange)",
    )
    
    # ── Derived Properties ────────────────────────────────────────────────
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    @property
    def jwt_access_expire_seconds(self) -> int:
        """Access token expiry in seconds."""
        return self.JWT_ACCESS_EXPIRE_MINUTES * 60
    
    @property
    def jwt_refresh_expire_seconds(self) -> int:
        """Refresh token expiry in seconds."""
        return self.JWT_REFRESH_EXPIRE_DAYS * 24 * 3600
    
    @field_validator("LLM_PROVIDER")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate LLM provider selection."""
        if v.lower() not in ("groq", "ollama"):
            raise ValueError(f"Invalid LLM provider: {v}. Must be 'groq' or 'ollama'.")
        return v.lower()
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}.")
        return v.upper()
    
    class Config:
        """Pydantic settings configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses LRU cache to avoid re-reading .env on every call.
    Settings are loaded once at application startup.
    
    Returns:
        Settings instance with all configuration values
    """
    return Settings()


# Global settings instance for convenience
settings = get_settings()
