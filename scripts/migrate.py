#! /usr/bin/env python3
# =============================================================================
# AutoInsight AI — Database Migration Script (scripts/migrate.py)
# Phase 1: Foundation — PostgreSQL Schema Setup
# =============================================================================
"""
Database migration script for AutoInsight AI.

Creates all required PostgreSQL tables:
  - users: User accounts with RBAC roles
  - pipelines: Pipeline execution tracking
  - data_models: UnifiedDataModel storage (JSONB)
  - reports: Report index with export URLs
  - conversations: NLQ conversation history
  - prompts: Versioned prompt templates
  - audit_log: Complete audit trail

Usage:
    python scripts/migrate.py                    # Run migrations
    python scripts/migrate.py --rollback          # Rollback (not yet implemented)
    python scripts/migrate.py --check             # Check migration status

Environment:
    DATABASE_URL must be set in .env or environment variables
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Database
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# DDL Statements
# =============================================================================

# Migration version tracking
CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS _migrations (
    id SERIAL PRIMARY KEY,
    version INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    checksum VARCHAR(64)
);
"""

# ── v001: Core Schema ──────────────────────────────────────────────────────

MIGRATION_V001 = """
-- Users & Authentication
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'analyst',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    CONSTRAINT valid_role CHECK (role IN ('admin', 'analyst', 'viewer'))
);

-- Pipeline Execution Tracking
CREATE TABLE IF NOT EXISTS pipelines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    file_name VARCHAR(255),
    file_size BIGINT,
    file_hash VARCHAR(64),
    llm_provider VARCHAR(50) DEFAULT 'groq',
    stages_completed TEXT[] DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_pipeline_status CHECK (
        status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
    )
);

-- Data Models (UnifiedDataModel JSONB Storage)
CREATE TABLE IF NOT EXISTS data_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id UUID REFERENCES pipelines(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    model_json JSONB NOT NULL,
    confidence_avg FLOAT,
    column_count INTEGER,
    row_count BIGINT,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reports Index
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_model_id UUID REFERENCES data_models(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    report_bundle JSONB,
    export_urls JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    overall_confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_report_status CHECK (
        status IN ('pending', 'generating', 'completed', 'failed')
    )
);

-- NLQ Conversation Store
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    dataset_id UUID,
    context JSONB,
    turn_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Versioned Prompt Registry
CREATE TABLE IF NOT EXISTS prompts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    template TEXT NOT NULL,
    description TEXT,
    stage INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Complete Audit Trail
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- File Storage Index
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT,
    file_hash VARCHAR(64),
    mime_type VARCHAR(255),
    s3_key VARCHAR(512),
    s3_bucket VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

# ── Indexes for Performance ───────────────────────────────────────────────

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_pipelines_user_id ON pipelines(user_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
CREATE INDEX IF NOT EXISTS idx_pipelines_created_at ON pipelines(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_models_pipeline_id ON data_models(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_data_models_user_id ON data_models(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_data_model_id ON reports(data_model_id);
CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_prompts_name_version ON prompts(name, version DESC);
CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_file_hash ON files(file_hash);
"""


# =============================================================================
# Migration Runner
# =============================================================================

MIGRATIONS = [
    {
        "version": 1,
        "name": "core_schema",
        "sql": MIGRATION_V001,
    },
    {
        "version": 2,
        "name": "indexes",
        "sql": CREATE_INDEXES,
    },
]


async def get_connection() -> asyncpg.Connection:
    """Get a database connection using DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    try:
        conn = await asyncpg.connect(dsn=database_url)
        logger.info(f"Connected to database: {database_url.split('@')[-1]}")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)


async def run_migrations(check_only: bool = False):
    """
    Run all pending database migrations.
    
    Args:
        check_only: If True, only show pending migrations without applying
    """
    conn = await get_connection()
    
    try:
        # Create migrations tracking table
        await conn.execute(CREATE_MIGRATIONS_TABLE)
        
        # Get applied migrations
        applied = await conn.fetch("SELECT version FROM _migrations ORDER BY version")
        applied_versions = {row["version"] for row in applied}
        
        logger.info(f"Applied migrations: {sorted(applied_versions) if applied_versions else 'None'}")
        
        # Run pending migrations
        for migration in MIGRATIONS:
            if migration["version"] not in applied_versions:
                if check_only:
                    logger.info(f"  [PENDING] v{migration['version']:03d}: {migration['name']}")
                else:
                    logger.info(f"  [APPLYING] v{migration['version']:03d}: {migration['name']}...")
                    
                    async with conn.transaction():
                        await conn.execute(migration["sql"])
                        await conn.execute(
                            "INSERT INTO _migrations (version, name) VALUES ($1, $2)",
                            migration["version"],
                            migration["name"],
                        )
                    
                    logger.info(f"  [COMPLETED] v{migration['version']:03d}: {migration['name']}")
            else:
                logger.info(f"  [SKIPPED] v{migration['version']:03d}: {migration['name']} (already applied)")
        
        # Summary
        updated = await conn.fetch("SELECT version, name, applied_at FROM _migrations ORDER BY version")
        logger.info(f"\nMigration Summary: {len(updated)} migrations applied")
        for m in updated:
            logger.info(f"  v{m['version']:03d}: {m['name']} ({m['applied_at'].strftime('%Y-%m-%d %H:%M:%S')})")
        
    finally:
        await conn.close()


async def seed_default_data():
    """Seed the database with default data (admin user, default prompts)."""
    logger.info("Seeding default data...")
    conn = await get_connection()
    
    try:
        # Seed default prompts
        from backend.prompt_registry import DEFAULT_PROMPTS
        
        for name, data in DEFAULT_PROMPTS.items():
            existing = await conn.fetchval(
                "SELECT id FROM prompts WHERE name = $1 AND version = $2",
                name, data["version"],
            )
            if not existing:
                await conn.execute(
                    """INSERT INTO prompts (name, version, template, description, stage)
                       VALUES ($1, $2, $3, $4, $5)""",
                    name,
                    data["version"],
                    data["template"],
                    data.get("description", ""),
                    data.get("stage", 0),
                )
                logger.info(f"  Seeded prompt: {name} v{data['version']}")
        
        logger.info("Default data seeding complete")
    finally:
        await conn.close()


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="AutoInsight AI — Database Migration Tool",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check pending migrations without applying",
    )
    parser.add_argument(
        "--seed", action="store_true",
        help="Seed default data after migrations",
    )
    parser.add_argument(
        "--rollback", action="store_true",
        help="Rollback last migration (not yet implemented)",
    )
    
    args = parser.parse_args()
    
    if args.rollback:
        logger.error("Rollback not yet implemented")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("AutoInsight AI — Database Migration")
    logger.info("=" * 60)
    
    asyncio.run(run_migrations(check_only=args.check))
    
    if args.seed and not args.check:
        asyncio.run(seed_default_data())
    
    logger.info("\nMigration complete.")


if __name__ == "__main__":
    main()
