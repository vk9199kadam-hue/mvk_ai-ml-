# =============================================================================
# AutoInsight AI — Pipeline Integration Tests (test_pipeline_orchestrator.py)
# Phase 2: Core Pipeline — End-to-End & Unit Tests
# =============================================================================
"""
Integration and unit tests for the full 4-stage pipeline.

Test categories:
  - Stage 1: CSV parsing, encoding detection, schema inference
  - Stage 2: Quality profiling, cleaning plan, transformations
  - Stage 3: LangGraph nodes, validation gate, retry logic
  - Stage 4: Column engineering, type validation, viz schema
  - Orchestrator: Full pipeline execution with progress tracking
  - Cache: Redis caching layer
  - Upload: File upload handler

Run with:
    pytest tests/test_pipeline_orchestrator.py -v
    pytest tests/test_pipeline_orchestrator.py --cov=backend -v
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import polars as pl
import pytest

from backend.cache import CacheManager
from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.pipeline.progress import ProgressTracker, STAGE_BOUNDARIES
from backend.pipeline.stage1_csv_to_json import Stage1_CSVtoJSON, SchemaInferenceError
from backend.pipeline.stage2_data_clean import Stage2_DataClean
from backend.pipeline.stage3_langgraph_agent import Stage3_LangGraphAgent
from backend.pipeline.stage4_column_engine import Stage4_ColumnEngine
from backend.schemas import (
    ChartType,
    CleaningOperation,
    CleaningPlan,
    ColumnInference,
    DataType,
    DerivedColumn,
    PipelineResult,
    PipelineStatus,
    QualityProfile,
    Relationship,
    RelationshipType,
    SchemaInferenceResponse,
    TransformationAudit,
    UnifiedDataModel,
)
from backend.tools import (
    compute_pearson,
    compute_univariate_stats,
    detect_encoding,
    detect_outliers_iqr,
    discover_relationship_candidates,
    impute_missing,
    mask_pii,
    parse_csv,
    profile_schema,
    safe_eval_polars,
    SandboxViolation,
)
from backend.upload import UploadHandler


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_csv_path():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("name,age,salary,department,join_date\n")
        f.write("Alice,30,75000,Engineering,2020-01-15\n")
        f.write("Bob,25,65000,Sales,2021-03-20\n")
        f.write("Charlie,35,85000,Engineering,2019-06-10\n")
        f.write("Diana,,95000,Marketing,2022-11-01\n")
        f.write("Eve,28,,Sales,2020-07-22\n")
        f.write("Frank,42,120000,Engineering,2018-02-14\n")
        f.write("Grace,31,72000,,2021-09-30\n")
        f.write("Henry,29,68000,Marketing,2022-04-18\n")
        f.write("Iris,38,90000,Engineering,\n")
        f.write("Jack,45,110000,Sales,2017-12-05\n")
        f_path = f.name

    yield f_path
    os.unlink(f_path)


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    return pl.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "age": [30, 25, 35, None, 28],
        "salary": [75000, 65000, 85000, 95000, None],
        "department": ["Engineering", "Sales", "Engineering", "Marketing", None],
        "experience_years": [5, 3, 10, 12, 4],
        "score": [85.5, 72.0, 91.0, 68.5, 95.0],
    })


@pytest.fixture
def sample_schema_response():
    """Create a sample SchemaInferenceResponse."""
    return SchemaInferenceResponse(
        columns=[
            ColumnInference(
                column_name="name",
                detected_type=DataType.STRING,
                confidence=0.95,
                reasoning="String values",
                nullable=False,
                sample_values=["Alice", "Bob", "Charlie"],
            ),
            ColumnInference(
                column_name="age",
                detected_type=DataType.INTEGER,
                confidence=0.98,
                reasoning="Integer values",
                nullable=True,
                sample_values=["30", "25", "35"],
            ),
            ColumnInference(
                column_name="salary",
                detected_type=DataType.INTEGER,
                confidence=0.98,
                reasoning="Integer salary values",
                nullable=True,
                sample_values=["75000", "65000", "85000"],
            ),
        ],
        row_count=10,
        encoding="utf-8",
        detected_delimiter=",",
        has_header=True,
        file_hash="abc123def456",
        processing_time_ms=1500,
    )


@pytest.fixture
def sample_quality_profile():
    """Create a sample QualityProfile."""
    return QualityProfile(
        columns={
            "age": {
                "dtype": "Int64",
                "null_count": 1,
                "null_percentage": 10.0,
                "cardinality": 5,
                "sample_values": ["30", "25", "35"],
            },
        },
        missing_summary={
            "total_cells": 25,
            "total_missing": 3,
            "missing_percentage": 12.0,
            "issues": [
                {"column": "age", "null_count": 1, "null_percentage": 10.0},
                {"column": "salary", "null_count": 1, "null_percentage": 10.0},
                {"column": "department", "null_count": 1, "null_percentage": 10.0},
            ],
        },
        outlier_summary={
            "columns": {},
            "total_outliers": 0,
        },
        duplicate_summary={"count": 0, "duplicate_percentage": 0.0},
        pii_columns=[],
        overall_quality_score=0.88,
    )


# =============================================================================
# Stage 1 Tests
# =============================================================================

class TestStage1_CSVtoJSON:
    """Tests for Stage 1: CSV → JSON Schema Inference."""

    @pytest.mark.asyncio
    async def test_file_validation(self, sample_csv_path):
        """Test file validation checks."""
        stage = Stage1_CSVtoJSON(llm_provider="ollama")

        # Non-existent file
        with pytest.raises(SchemaInferenceError):
            await stage.run("/nonexistent/file.csv")

        # Empty file
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            empty_path = f.name

        with pytest.raises(SchemaInferenceError):
            await stage.run(empty_path)

        os.unlink(empty_path)

    @pytest.mark.asyncio
    async def test_encoding_detection(self, sample_csv_path):
        """Test encoding detection via chardet."""
        encoding = detect_encoding(sample_csv_path)
        assert encoding is not None
        assert isinstance(encoding, str)

    @pytest.mark.asyncio
    async def test_csv_parsing(self, sample_csv_path):
        """Test Polars CSV parsing."""
        df = parse_csv(sample_csv_path)
        assert len(df) == 10
        assert len(df.columns) == 5
        assert "name" in df.columns
        assert "age" in df.columns

    @pytest.mark.asyncio
    async def test_schema_validation(self, sample_schema_response):
        """Test SchemaInferenceResponse validation."""
        # Valid response
        assert sample_schema_response.overall_confidence is not None
        assert sample_schema_response.overall_confidence > 0.0
        assert len(sample_schema_response.columns) == 3

        # Invalid: empty columns
        with pytest.raises(Exception):
            SchemaInferenceResponse(columns=[], row_count=0)


class TestStage2_DataClean:
    """Tests for Stage 2: Data Cleaning."""

    @pytest.mark.asyncio
    async def test_quality_profiling(self, sample_df):
        """Test quality profiling produces expected structure."""
        stage = Stage2_DataClean(llm_provider="ollama")
        profile = await stage._profile_quality(sample_df)

        assert isinstance(profile, QualityProfile)
        assert profile.overall_quality_score > 0.0
        assert profile.overall_quality_score <= 1.0
        assert "name" in profile.columns
        assert "age" in profile.columns

    @pytest.mark.asyncio
    async def test_missing_value_detection(self, sample_df):
        """Test missing value detection in profiling."""
        stage = Stage2_DataClean(llm_provider="ollama")
        profile = await stage._profile_quality(sample_df)

        # Sample has 3 missing values (age, salary, department)
        assert profile.missing_summary["total_missing"] == 3
        assert profile.missing_summary["missing_percentage"] > 0.0

    @pytest.mark.asyncio
    async def test_fallback_cleaning_plan(self, sample_df, sample_quality_profile):
        """Test rule-based cleaning plan generation."""
        stage = Stage2_DataClean(llm_provider="ollama")
        plan = stage._fallback_cleaning_plan(sample_df, sample_quality_profile)

        assert isinstance(plan, CleaningPlan)
        assert plan.description is not None
        assert len(plan.operations) > 0

    @pytest.mark.asyncio
    async def test_imputation(self, sample_df):
        """Test missing value imputation."""
        # Mean imputation
        cleaned = impute_missing(sample_df, strategy="mean")
        assert cleaned["age"].null_count() == 0
        assert cleaned["salary"].null_count() == 0


class TestStage3_LangGraphAgent:
    """Tests for Stage 3: LangGraph Agent."""

    @pytest.mark.asyncio
    async def test_profile_step(self, sample_df):
        """Test deterministic profiling node."""
        agent = Stage3_LangGraphAgent(llm_provider="ollama")
        from backend.pipeline.stage3_langgraph_agent import AgentState

        state = AgentState(sample_df)
        state = await agent.profile_step(state)

        assert "schema" in state.profile
        assert "stats" in state.profile
        assert state.profile["column_count"] == 6
        assert state.profile["row_count"] == 5

    @pytest.mark.asyncio
    async def test_discover_step(self, sample_df):
        """Test deterministic discovery node."""
        agent = Stage3_LangGraphAgent(llm_provider="ollama")
        from backend.pipeline.stage3_langgraph_agent import AgentState

        state = AgentState(sample_df)
        state = await agent.profile_step(state)
        state = await agent.discover_step(state)

        assert "candidates" in state.candidates
        assert "summary" in state.candidates

    @pytest.mark.asyncio
    async def test_fallback_reason_step(self, sample_df):
        """Test deterministic fallback reason step."""
        agent = Stage3_LangGraphAgent(llm_provider="ollama")
        from backend.pipeline.stage3_langgraph_agent import AgentState

        state = AgentState(sample_df)
        state = await agent.profile_step(state)
        state = await agent.discover_step(state)
        state = agent._fallback_reason_step(state)

        assert len(state.relationships) > 0

    @pytest.mark.asyncio
    async def test_executor_step(self, sample_df):
        """Test executor step with derived column expressions."""
        agent = Stage3_LangGraphAgent(llm_provider="ollama")
        from backend.pipeline.stage3_langgraph_agent import AgentState

        state = AgentState(sample_df)
        state = await agent.profile_step(state)
        state.derived_columns = [
            {
                "name": "bonus",
                "expression": 'pl.col("salary") * 0.1',
                "data_type": "float",
                "description": "10% bonus calculation",
                "validation_rules": ["non_negative"],
                "confidence": 0.85,
            }
        ]
        state = await agent.executor_step(state)

        assert len(state.derived_columns) > 0


class TestPipelineOrchestrator:
    """Tests for the full pipeline orchestrator."""

    @pytest.mark.asyncio
    async def test_pipeline_status(self):
        """Test pipeline status retrieval."""
        orchestrator = PipelineOrchestrator(llm_provider="ollama")
        status = await orchestrator.get_pipeline_status("nonexistent-id")

        assert status is not None
        assert status["pipeline_id"] == "nonexistent-id"

    @pytest.mark.asyncio
    async def test_progress_tracker(self):
        """Test progress tracking."""
        from backend.pipeline.progress import STAGE_BOUNDARIES

        assert 1 in STAGE_BOUNDARIES
        assert 2 in STAGE_BOUNDARIES
        assert 3 in STAGE_BOUNDARIES
        assert 4 in STAGE_BOUNDARIES

        assert STAGE_BOUNDARIES[1]["start"] == 0.0
        assert STAGE_BOUNDARIES[4]["end"] == 100.0


class TestTools:
    """Tests for the deterministic tools module."""

    def test_profile_schema(self, sample_df):
        """Test schema profiling."""
        profile = profile_schema(sample_df)
        assert "columns" in profile
        assert profile["row_count"] == 5
        assert profile["column_count"] == 6

    def test_univariate_stats(self, sample_df):
        """Test univariate statistics."""
        stats = compute_univariate_stats(sample_df)
        assert "age" in stats
        assert "salary" in stats
        assert stats["age"]["mean"] is not None
        assert stats["age"]["count"] == 4  # 1 null

    def test_pearson_correlation(self, sample_df):
        """Test Pearson correlation."""
        corr = compute_pearson(sample_df)
        assert len(corr) > 0

        # Age and experience should be correlated
        if "age" in corr and "experience_years" in corr["age"]:
            assert abs(corr["age"]["experience_years"]) > 0.5

    def test_outlier_detection_iqr(self):
        """Test IQR outlier detection."""
        series = pl.Series([1, 2, 3, 4, 5, 100])
        mask, stats = detect_outliers_iqr(series)

        assert stats["outlier_count"] >= 1  # 100 is an outlier

    def test_safe_eval(self, sample_df):
        """Test sandboxed expression evaluation."""
        # Valid expression
        result = safe_eval_polars('pl.col("salary") * 0.1', sample_df)
        assert len(result) == 5

        # Block dangerous operation
        with pytest.raises(SandboxViolation):
            safe_eval_polars('__import__("os")', sample_df)

    def test_imputation(self, sample_df):
        """Test missing value imputation."""
        cleaned = impute_missing(sample_df, strategy="mean")
        assert cleaned["age"].null_count() == 0
        assert cleaned["salary"].null_count() == 0

    def test_discover_candidates(self, sample_df):
        """Test relationship candidate discovery."""
        result = discover_relationship_candidates(sample_df)
        assert "candidates" in result
        assert "summary" in result


class TestUploadHandler:
    """Tests for the upload handler."""

    @pytest.mark.asyncio
    async def test_upload_initiate(self):
        """Test upload initiation."""
        handler = UploadHandler()
        info = await handler.initiate_upload(
            filename="test.csv",
            file_size=1024,
            content_type="text/csv",
        )

        assert info["filename"] == "test.csv"
        assert info["file_size"] == 1024
        assert info["status"] == "initiated"
        assert "upload_id" in info

    @pytest.mark.asyncio
    async def test_upload_invalid_type(self):
        """Test invalid file type rejection."""
        handler = UploadHandler()
        with pytest.raises(Exception):
            await handler.initiate_upload(
                filename="test.exe",
                file_size=1024,
            )

    @pytest.mark.asyncio
    async def test_upload_too_large(self):
        """Test oversized file rejection."""
        handler = UploadHandler()
        from backend.config import settings
        huge_size = (settings.MAX_FILE_SIZE_MB + 1) * 1024 * 1024

        with pytest.raises(Exception):
            await handler.initiate_upload(
                filename="test.csv",
                file_size=huge_size,
            )


class TestSchemas:
    """Tests for Pydantic schemas."""

    def test_relationship_model(self):
        """Test Relationship model creation and validation."""
        rel = Relationship(
            source_column="age",
            target_column="salary",
            relationship_type=RelationshipType.ONE_TO_ONE,
            confidence=0.85,
            description="Age correlates with salary",
            chart_hint=ChartType.SCATTER,
        )

        assert rel.source_column == "age"
        assert rel.confidence == 0.85
        assert rel.chart_hint == ChartType.SCATTER

    def test_derived_column_model(self):
        """Test DerivedColumn model."""
        col = DerivedColumn(
            name="bonus",
            expression='pl.col("salary") * 0.1',
            data_type="float",
            description="10% bonus",
            validation_rules=["non_negative"],
            confidence=0.85,
        )

        assert col.name == "bonus"
        assert "pl.col" in col.expression
        assert len(col.validation_rules) == 1

    def test_unified_data_model(self):
        """Test UnifiedDataModel assembly."""
        udm = UnifiedDataModel(
            original_columns=["a", "b", "c"],
            cleaned_columns=["a", "b", "c"],
            derived_columns=[],
            relationships=[],
        )

        assert udm.total_columns == 3
        assert udm.average_relationship_confidence == 0.0

    def test_schema_inference_response(self):
        """Test SchemaInferenceResponse."""
        response = SchemaInferenceResponse(
            columns=[
                ColumnInference(
                    column_name="test",
                    detected_type=DataType.INTEGER,
                    confidence=0.95,
                    reasoning="Test",
                )
            ],
            row_count=100,
        )

        assert response.overall_confidence is not None
        assert response.overall_confidence == 0.95


class TestCleanup:
    """Cleanup and integration tests."""

    def test_confidence_gate_constants(self):
        """Test confidence gate constants are valid."""
        from backend.config import settings
        assert settings.CONFIDENCE_MANUAL_APPROVAL >= settings.CONFIDENCE_REVIEW_REQUIRED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
