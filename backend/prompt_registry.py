# =============================================================================
# AutoInsight AI — Versioned Prompt Registry (prompt_registry.py)
# Phase 1: Foundation — Prompt Management System
# =============================================================================
"""
Versioned prompt registry with PostgreSQL storage and Redis caching.

Manages all LLM prompt templates used across the 8 stages.
Each prompt is:
  - Versioned (semantic versioning)
  - Stored in PostgreSQL for persistence
  - Cached in Redis for fast retrieval
  - Template-based with variable injection

Prompt Categories:
  - schema_inference: Stage 1 — CSV column type inference
  - cleaning_plan: Stage 2 — Data cleaning recommendations
  - core_agent: Stage 3 — LangGraph relationship reasoning
  - report_*: Stage 5 — 8 report sub-agents
  - nlq_parser: Stage 6 — Natural language query parsing

Usage:
    from backend.prompt_registry import PromptRegistry
    
    registry = PromptRegistry()
    
    # Get latest version
    prompt = await registry.get_prompt("infer_schema")
    
    # Get specific version
    prompt = await registry.get_prompt("core_agent_system", version=2)
    
    # Register new prompt
    await registry.register_prompt(
        name="infer_schema",
        template="You are a data schema expert...",
        version=1,
    )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

import redis.asyncio as aioredis
from langchain_core.prompts import PromptTemplate

from backend.config import settings

logger = logging.getLogger(__name__)

# Redis cache key prefix and TTL
CACHE_PREFIX = "prompt:"
CACHE_TTL_SECONDS = 3600  # 1 hour


# =============================================================================
# Default Prompt Templates
# =============================================================================

# These are the core prompt templates for the AutoInsight AI system.
# They are registered at startup if they don't exist in PostgreSQL.

DEFAULT_PROMPTS: Dict[str, Dict[str, Any]] = {
    # ── Stage 1: Schema Inference ─────────────────────────────────────────
    "infer_schema": {
        "version": 1,
        "template": """You are a data schema expert. Given the first 100 rows of a CSV file:
1. Detect data type for each column (int, float, str, date, datetime, boolean)
2. Provide confidence level for each inference
3. Note format specifications (date format, separators)
4. Flag ambiguous types.

Output ONLY valid JSON matching the SchemaInferenceResponse Pydantic schema.
Do not include markdown code blocks or any explanatory text.

CSV Sample Data (first 100 rows):
{csv_sample}""",
        "description": "Infers column types and schema from CSV sample data",
        "stage": 1,
    },
    
    # ── Stage 2: Cleaning Plan ────────────────────────────────────────────
    "cleaning_plan": {
        "version": 1,
        "template": """You are a data cleaning expert. Given a DataPrep quality profile:
1. Recommend imputation strategies for missing values
2. Suggest outlier treatment methods
3. Propose deduplication approach
4. Identify PII columns and masking rules
5. Provide confidence scores.

Output ONLY valid JSON matching the CleaningPlan Pydantic schema.

Quality Profile:
{quality_profile}""",
        "description": "Generates data cleaning plan from quality profile",
        "stage": 2,
    },
    
    # ── Stage 3: Core Agent System Prompt ─────────────────────────────────
    "core_agent_system": {
        "version": 1,
        "template": """You are an Expert Data Model Architect. Given schema, stats, and candidates:
1. Validate & filter relationships (confidence >= 0.65 only)
2. For each, provide: relationship_type, ai_reasoning, analytical_purpose, chart_hint
3. Generate 3-5 derived columns (exact Polars formulas, business rationale, confidence)
4. Assemble final unified schema for visualization.

RULES:
- Never invent columns. Base confidence on statistical evidence.
- Output ONLY JSON matching UnifiedDataModel Pydantic schema.
- Do not include markdown code blocks.

Schema Metadata:
{schema_metadata}

Candidate Relationships:
{candidates}

Statistical Profile:
{statistics}""",
        "description": "Core LangGraph agent system prompt for relationship discovery",
        "stage": 3,
    },
    
    # ── Stage 5: 8 Report Sub-Agents ─────────────────────────────────────
    "report_business_understanding": {
        "version": 1,
        "template": """You are a Business Analyst. Given the dataset profile and relationships:
1. Identify the business domain and context
2. Map key business KPIs to available columns
3. Identify stakeholders who would use this data
4. Suggest business questions this data can answer

Output ONLY valid JSON with: section_type, title, content, confidence.

Data Profile:
{data_profile}""",
        "description": "Business understanding section of the report",
        "stage": 5,
    },
    
    "report_data_collection": {
        "version": 1,
        "template": """You are a Data Engineer. Given the dataset profile:
1. Describe data sources and collection methodology
2. Document format specifications
3. Identify data quality issues and limitations
4. Create data dictionary with column descriptions

Output ONLY valid JSON matching the ReportSection schema.

Data Profile:
{data_profile}""",
        "description": "Data collection methodology section",
        "stage": 5,
    },
    
    "report_cleaning_analysis": {
        "version": 1,
        "template": """You are a Data Quality Analyst. Given the cleaning plan and audit log:
1. Summarize data quality before and after cleaning
2. Quantify the impact of cleaning operations
3. Identify remaining quality concerns
4. Recommend ongoing monitoring strategies

Output ONLY valid JSON matching the ReportSection schema.

Cleaning Plan:
{cleaning_plan}

Audit Log:
{audit_log}""",
        "description": "Data cleaning and quality analysis section",
        "stage": 5,
    },
    
    "report_eda": {
        "version": 1,
        "template": """You are an Exploratory Data Analyst. Given the univariate stats and correlation matrix:
1. Describe distribution patterns for each column
2. Identify notable correlations and relationships
3. Flag anomalies and outliers
4. Provide visual pattern descriptions

Output ONLY valid JSON matching the ReportSection schema.

Univariate Statistics:
{univariate_stats}

Correlation Matrix:
{correlation_matrix}""",
        "description": "Exploratory data analysis section",
        "stage": 5,
    },
    
    "report_statistical_analysis": {
        "version": 1,
        "template": """You are a Statistician. Given the data profile:
1. Perform hypothesis testing on key relationships
2. Assess statistical significance of correlations
3. Identify regression opportunities
4. Provide confidence intervals where applicable

Output ONLY valid JSON matching the ReportSection schema.

Statistical Profile:
{statistical_profile}""",
        "description": "Statistical analysis section",
        "stage": 5,
    },
    
    "report_dashboard_viz": {
        "version": 1,
        "template": """You are a Visualization Expert. Given the relationships and chart hints:
1. Design KPI dashboard layout
2. Specify chart types for each relationship
3. Configure axes, colors, and tooltips
4. Suggest filter architecture and drill-down paths

Output ONLY valid JSON matching the ReportSection schema.

Relationships:
{relationships}

Chart Hints:
{chart_hints}""",
        "description": "Dashboard and visualization recommendations",
        "stage": 5,
    },
    
    "report_insights": {
        "version": 1,
        "template": """You are a Senior Data Analyst. Given all analysis results:
1. Identify top 5 key insights from the data
2. Flag anomalies that require investigation
3. Quantify business impact for each insight
4. Prioritize insights by actionability

Output ONLY valid JSON matching the ReportSection schema.

Analysis Summary:
{analysis_summary}""",
        "description": "Key insights and findings section",
        "stage": 5,
    },
    
    "report_recommendations": {
        "version": 1,
        "template": """You are a Business Consultant. Given the insights and analysis:
1. Provide actionable recommendations
2. Prioritize by impact and effort
3. Suggest implementation roadmap
4. Identify success metrics for each recommendation

Output ONLY valid JSON matching the ReportSection schema.

Insights:
{insights}

Business Context:
{business_context}""",
        "description": "Actionable recommendations section",
        "stage": 5,
    },
    
    # ── Stage 6: NLQ Parser ──────────────────────────────────────────────
    "nlq_parser": {
        "version": 1,
        "template": """You are an NLQ Parser. Convert the user's natural language query into:
1. Extracted metrics (aggregate columns)
2. Dimensions (group-by columns)
3. Filters (where conditions)
4. Sort order
5. SQL query (DuckDB compatible)

Available columns and their types:
{schema_info}

User query: {user_query}

Output ONLY valid JSON with: metrics, dimensions, filters, sql, confidence.""",
        "description": "Parses natural language queries into SQL",
        "stage": 6,
    },
}


# =============================================================================
# Prompt Registry Class
# =============================================================================

class PromptRegistry:
    """
    Versioned prompt registry with PostgreSQL storage and Redis caching.
    
    Prompts are stored in PostgreSQL (prompts table) and cached in Redis.
    The registry provides:
      - Versioned prompt retrieval
      - Automatic registration of default prompts
      - Redis caching with TTL
      - Format string validation
    """
    
    def __init__(self):
        """Initialize the prompt registry."""
        self._redis: Optional[aioredis.Redis] = None
        self._cache_enabled = True
    
    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                )
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Cache disabled.")
                self._cache_enabled = False
        return self._redis
    
    async def get_prompt(
        self,
        name: str,
        version: Optional[int] = None,
    ) -> PromptTemplate:
        """
        Retrieve a prompt template by name and optional version.
        
        Cache strategy:
          1. Check Redis cache (key: "prompt:{name}:{version}")
          2. If miss, query PostgreSQL
          3. Cache result in Redis for 1 hour
          4. Return PromptTemplate
        
        Args:
            name: Prompt name (e.g., "infer_schema")
            version: Specific version (None = latest)
        
        Returns:
            LangChain PromptTemplate ready for use
        
        Raises:
            ValueError: If prompt is not found
        
        Example:
            prompt = await registry.get_prompt("infer_schema")
            chain = prompt | llm
        """
        cache_key = f"{CACHE_PREFIX}{name}:{version or 'latest'}"
        template_str = None
        
        # ── Step 1: Check Redis cache ─────────────────────────────────────
        if self._cache_enabled:
            try:
                redis_client = await self._get_redis()
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Prompt cache HIT: {cache_key}")
                    template_str = cached
            except Exception as e:
                logger.debug(f"Cache read failed: {e}")
        
        # ── Step 2: Check PostgreSQL ──────────────────────────────────────
        if template_str is None:
            logger.debug(f"Prompt cache MISS: {cache_key}")
            
            # In Phase 1, we use default prompts (PostgreSQL integration comes in Phase 2)
            # For now, check defaults
            if name in DEFAULT_PROMPTS:
                prompt_data = DEFAULT_PROMPTS[name]
                if version is None or version == prompt_data["version"]:
                    template_str = prompt_data["template"]
            
            if template_str is None:
                raise ValueError(
                    f"Prompt '{name}' (version {version or 'latest'}) not found. "
                    f"Available prompts: {', '.join(DEFAULT_PROMPTS.keys())}"
                )
            
            # ── Step 3: Cache in Redis ────────────────────────────────────
            if self._cache_enabled and template_str:
                try:
                    redis_client = await self._get_redis()
                    await redis_client.setex(cache_key, CACHE_TTL_SECONDS, template_str)
                except Exception as e:
                    logger.debug(f"Cache write failed: {e}")
        
        return PromptTemplate.from_template(template_str)
    
    async def register_prompt(
        self,
        name: str,
        template: str,
        version: int = 1,
        description: str = "",
        stage: int = 0,
    ) -> bool:
        """
        Register a new prompt version in PostgreSQL.
        
        Args:
            name: Prompt name
            template: Prompt template string (with {variable} placeholders)
            version: Version number (auto-incremented if exists)
            description: Human-readable description
            stage: Which stage this prompt belongs to (1-8)
        
        Returns:
            True if registration was successful
        
        Example:
            await registry.register_prompt(
                name="infer_schema",
                template="You are a data schema expert...",
                version=2,
                description="Updated schema inference prompt",
                stage=1,
            )
        """
        # Validate template format strings
        self._validate_template(template)
        
        # In Phase 1, we store in the defaults dict
        # Full PostgreSQL integration comes in Phase 2
        if name in DEFAULT_PROMPTS:
            existing = DEFAULT_PROMPTS[name]
            if version <= existing["version"]:
                version = existing["version"] + 1
        
        DEFAULT_PROMPTS[name] = {
            "version": version,
            "template": template,
            "description": description,
            "stage": stage,
        }
        
        # Invalidate Redis cache
        if self._cache_enabled:
            try:
                redis_client = await self._get_redis()
                cache_key = f"{CACHE_PREFIX}{name}:latest"
                await redis_client.delete(cache_key)
                cache_key = f"{CACHE_PREFIX}{name}:{version}"
                await redis_client.delete(cache_key)
            except Exception:
                pass
        
        logger.info(f"Prompt registered: {name} v{version}")
        return True
    
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """
        List all registered prompts with their metadata.
        
        Returns:
            List of prompt metadata dicts
        """
        prompts = []
        for name, data in DEFAULT_PROMPTS.items():
            prompts.append({
                "name": name,
                "version": data["version"],
                "description": data.get("description", ""),
                "stage": data.get("stage", 0),
                "template_preview": data["template"][:100] + "...",
            })
        return prompts
    
    def _validate_template(self, template: str) -> None:
        """
        Validate that a prompt template has valid format strings.
        
        Args:
            template: Template string to validate
        
        Raises:
            ValueError: If template has invalid format strings
        """
        try:
            template.format(**{"test": "value"})
        except KeyError:
            pass  # Template may have variables — that's fine
        except ValueError as e:
            raise ValueError(f"Invalid template format: {e}")
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    @staticmethod
    def get_prompt_info(name: str) -> Optional[Dict[str, Any]]:
        """
        Get prompt metadata without retrieving the full template.
        
        Args:
            name: Prompt name
        
        Returns:
            Prompt metadata or None if not found
        """
        if name in DEFAULT_PROMPTS:
            data = DEFAULT_PROMPTS[name]
            return {
                "name": name,
                "version": data["version"],
                "description": data.get("description", ""),
                "stage": data.get("stage", 0),
                "has_template": bool(data.get("template")),
            }
        return None
