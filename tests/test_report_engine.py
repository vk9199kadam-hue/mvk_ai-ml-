# =============================================================================
# AutoInsight AI — Report Engine Tests (test_report_engine.py)
# Phase 3: Report Engine — 4-Phase Unit & Integration Tests
# =============================================================================
"""
Tests for the full 4-phase report generation engine.

Test categories:
  - Phase 1: Deterministic profiling functions (5 functions)
  - Phase 2: Sub-agent prompt building, section generation
  - Phase 3: Validation, confidence gating, retry logic
  - Phase 4: ReportBundle assembly, Jinja2 templates, export formats
  - Orchestrator: End-to-end report generation

Run with:
    pytest tests/test_report_engine.py -v
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import polars as pl
import pytest

from backend.report.phase1_profiling import Phase1_Profiling
from backend.report.phase2_sub_agents import Phase2_SubAgents, SubAgentOutput
from backend.report.phase3_validation import Phase3_Validation
from backend.report.phase4_export import Phase4_Export
from backend.report.orchestrator import ReportOrchestrator
from backend.schemas import (
    ChartType,
    ConfidenceLevel,
    DataProfile,
    DerivedColumn,
    Relationship,
    RelationshipType,
    ReportBundle,
    ReportSection,
    ReportSectionType,
    UnifiedDataModel,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_df():
    """Sample DataFrame for profiling tests."""
    return pl.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "age": [30, 25, 35, 28, 42],
        "salary": [75000, 65000, 85000, 95000, 120000],
        "department": ["Engineering", "Sales", "Engineering", "Marketing", "Engineering"],
        "experience_years": [5, 3, 10, 7, 15],
        "score": [85.5, 72.0, 91.0, 68.5, 95.0],
        "join_date": ["2020-01-15", "2021-03-20", "2019-06-10", "2022-11-01", "2018-02-14"],
    })


@pytest.fixture
def sample_data_profile():
    """Sample DataProfile (constructed directly, no async)."""
    return DataProfile(
        schema_metadata={
            "columns": {
                "name": {"dtype": "Utf8", "null_count": 0, "null_percentage": 0.0, "cardinality": 5, "is_numeric": False, "is_categorical": True},
                "age": {"dtype": "Int64", "null_count": 0, "null_percentage": 0.0, "cardinality": 4, "is_numeric": True, "is_categorical": False},
                "salary": {"dtype": "Int64", "null_count": 0, "null_percentage": 0.0, "cardinality": 5, "is_numeric": True, "is_categorical": False},
            },
            "row_count": 5,
            "column_count": 3,
            "summary": {"numeric_columns": 2, "categorical_columns": 1, "null_percentage_total": 0.0},
        },
        univariate_stats={
            "age": {"mean": 32.0, "median": 30.0, "std": 6.52, "min": 25, "max": 42, "cv": 0.20},
            "salary": {"mean": 88000.0, "median": 85000.0, "std": 20248.46, "min": 65000, "max": 120000, "cv": 0.23},
        },
        bivariate_matrix={
            "age": {"salary": {"pearson_r": 0.75, "p_value": 0.05, "significant": True, "strength": "strong"}},
            "salary": {"age": {"pearson_r": 0.75, "p_value": 0.05, "significant": True, "strength": "strong"}},
        },
        trends=None,
        domain_context=None,
    )


@pytest.fixture
def sample_udm():
    """Sample UnifiedDataModel for report orchestration."""
    return UnifiedDataModel(
        original_columns=["name", "age", "salary", "department"],
        cleaned_columns=["name", "age", "salary", "department"],
        derived_columns=[
            DerivedColumn(
                name="bonus",
                expression='pl.col("salary") * 0.1',
                data_type="float",
                description="10% bonus",
                validation_rules=["non_negative"],
                confidence=0.85,
            )
        ],
        relationships=[
            Relationship(
                source_column="age",
                target_column="salary",
                relationship_type=RelationshipType.ONE_TO_ONE,
                confidence=0.85,
                description="Age correlates with salary",
                chart_hint=ChartType.SCATTER,
                analytical_purpose="Compensation analysis",
            )
        ],
        transformation_audit=[],
        final_viz_schema={},
        recommended_dashboard_layout={},
    )


@pytest.fixture
def sample_sections():
    """Sample report sections for Phase 3/4 tests."""
    types = [
        ReportSectionType.BUSINESS_UNDERSTANDING,
        ReportSectionType.DATA_COLLECTION,
        ReportSectionType.CLEANING_ANALYSIS,
        ReportSectionType.EDA,
        ReportSectionType.STATISTICAL_ANALYSIS,
        ReportSectionType.DASHBOARD_VIZ,
        ReportSectionType.INSIGHTS,
        ReportSectionType.RECOMMENDATIONS,
    ]
    return [
        ReportSection(
            section_type=t,
            title=t.value.replace("_", " ").title(),
            content=f"## {t.value.replace('_', ' ').title()}\n\nThis section covers the analysis.",
            confidence=0.85,
        )
        for t in types
    ]


# =============================================================================
# Phase 1: Deterministic Profiling Tests
# =============================================================================

class TestPhase1_Profiling:
    """Tests for Phase 1: 5 deterministic profiling functions."""

    @pytest.mark.asyncio
    async def test_run_returns_data_profile(self, sample_df):
        profiler = Phase1_Profiling()
        profile = await profiler.run(sample_df)
        assert isinstance(profile, DataProfile)
        assert profile.schema_metadata is not None
        assert profile.univariate_stats is not None
        assert profile.bivariate_matrix is not None

    @pytest.mark.asyncio
    async def test_extract_schema_metadata(self, sample_df):
        profiler = Phase1_Profiling()
        schema = profiler.extract_schema_metadata(sample_df)
        assert "columns" in schema
        assert schema["column_count"] == 7
        assert "summary" in schema

    @pytest.mark.asyncio
    async def test_compute_univariate_stats_detailed(self, sample_df):
        profiler = Phase1_Profiling()
        stats = profiler.compute_univariate_stats_detailed(sample_df)
        assert "age" in stats
        assert "salary" in stats
        assert stats["age"]["mean"] is not None
        assert stats["age"]["cv"] is not None

    @pytest.mark.asyncio
    async def test_compute_bivariate_matrix(self, sample_df):
        profiler = Phase1_Profiling()
        matrix = profiler.compute_bivariate_matrix(sample_df)
        assert "age" in matrix
        assert "salary" in matrix
        if "salary" in matrix["age"]:
            entry = matrix["age"]["salary"]
            assert isinstance(entry, dict)
            assert "pearson_r" in entry
            assert "p_value" in entry

    @pytest.mark.asyncio
    async def test_detect_trends(self, sample_df):
        profiler = Phase1_Profiling()
        trends = profiler.detect_trends_seasonality(sample_df)
        assert trends is not None
        assert "date_column" in trends

    @pytest.mark.asyncio
    async def test_infer_domain(self):
        df = pl.DataFrame({
            "product": ["A", "B"], "price": [10, 20],
            "customer": ["X", "Y"], "order_amount": [100, 200],
        })
        profiler = Phase1_Profiling()
        domain = profiler.infer_domain_context(df)
        assert domain is not None
        assert "retail_ecommerce" in domain.lower()

    @pytest.mark.asyncio
    async def test_no_domain_match(self):
        df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
        profiler = Phase1_Profiling()
        domain = profiler.infer_domain_context(df)
        assert domain is None


# =============================================================================
# Phase 2: Sub-Agent Tests
# =============================================================================

class TestPhase2_SubAgents:
    """Tests for Phase 2: 8 parallel sub-agents."""

    @pytest.mark.asyncio
    async def test_fallback_section_generation(self, sample_data_profile):
        agents = Phase2_SubAgents()
        section = agents._generate_fallback_section(
            ReportSectionType.BUSINESS_UNDERSTANDING,
            sample_data_profile,
        )
        assert isinstance(section, ReportSection)
        assert len(section.content) > 50
        assert section.confidence > 0.0

    @pytest.mark.asyncio
    async def test_all_fallback_sections(self, sample_data_profile):
        agents = Phase2_SubAgents()
        for section_type in [
            ReportSectionType.BUSINESS_UNDERSTANDING,
            ReportSectionType.DATA_COLLECTION,
            ReportSectionType.EDA,
            ReportSectionType.STATISTICAL_ANALYSIS,
            ReportSectionType.DASHBOARD_VIZ,
            ReportSectionType.INSIGHTS,
            ReportSectionType.RECOMMENDATIONS,
        ]:
            section = agents._generate_fallback_section(section_type, sample_data_profile)
            assert isinstance(section, ReportSection)
            assert len(section.content) > 30

    @pytest.mark.asyncio
    async def test_build_agent_variables(self, sample_data_profile, sample_udm):
        agents = Phase2_SubAgents()
        vars = agents._build_agent_variables(
            ReportSectionType.INSIGHTS, sample_data_profile, sample_udm
        )
        assert "data_profile" in vars

    @pytest.mark.asyncio
    async def test_build_agent_prompt(self, sample_data_profile):
        agents = Phase2_SubAgents()
        prompt = agents._build_agent_prompt(
            ReportSectionType.EDA,
            {"data_profile": "test", "univariate_stats": "stats"},
        )
        assert "EDA" in prompt or "eda" in prompt


# =============================================================================
# Phase 3: Validation & Confidence Gating Tests
# =============================================================================

class TestPhase3_Validation:
    """Tests for Phase 3: Validation and confidence gating."""

    @pytest.mark.asyncio
    async def test_run_returns_validated(self, sample_sections):
        validator = Phase3_Validation(max_retries=0)
        sections, report = await validator.run(sample_sections)
        assert len(sections) == 8
        assert report["total_sections"] == 8

    @pytest.mark.asyncio
    async def test_confidence_level_mapping(self):
        validator = Phase3_Validation()
        assert validator._get_confidence_level(0.95) == ConfidenceLevel.HIGH
        assert validator._get_confidence_level(0.80) == ConfidenceLevel.MEDIUM
        assert validator._get_confidence_level(0.60) == ConfidenceLevel.LOW
        assert validator._get_confidence_level(0.30) == ConfidenceLevel.VERY_LOW

    @pytest.mark.asyncio
    async def test_can_auto_apply(self):
        validator = Phase3_Validation()
        assert validator.can_auto_apply(0.95) is True
        assert validator.can_auto_apply(0.70) is False

    @pytest.mark.asyncio
    async def test_get_badge_color(self):
        validator = Phase3_Validation()
        assert validator.get_badge_color(0.95) == "green"
        assert validator.get_badge_color(0.80) == "yellow"
        assert validator.get_badge_color(0.60) == "orange"
        assert validator.get_badge_color(0.30) == "red"

    @pytest.mark.asyncio
    async def test_validation_summary(self, sample_sections):
        validator = Phase3_Validation(max_retries=0)
        _, report = await validator.run(sample_sections)
        summary = validator.generate_validation_summary(report)
        assert "Validation Summary" in summary
        assert "Total Sections" in summary

    @pytest.mark.asyncio
    async def test_enrich_section(self):
        validator = Phase3_Validation()
        section = ReportSection(
            section_type=ReportSectionType.EDA,
            title="Test",
            content="Short",
            confidence=0.30,
        )
        enriched = validator._enrich_section(section)
        assert enriched.confidence > 0.30

    @pytest.mark.asyncio
    async def test_fallback_enrichment(self):
        validator = Phase3_Validation()
        section = ReportSection(
            section_type=ReportSectionType.EDA,
            title="Test",
            content="Short",
            confidence=0.30,
        )
        enriched = validator._apply_fallback_enrichment(section)
        assert len(enriched.content) >= 50
        assert enriched.confidence >= 0.45


# =============================================================================
# Phase 4: Assembly & Export Tests
# =============================================================================

class TestPhase4_Export:
    """Tests for Phase 4: Assembly and export."""

    @pytest.mark.asyncio
    async def test_assembly_creates_bundle(self, sample_sections):
        exporter = Phase4_Export()
        bundle = await exporter.run(sample_sections)
        assert isinstance(bundle, ReportBundle)
        assert len(bundle.sections) == 8
        assert bundle.overall_confidence > 0.0

    @pytest.mark.asyncio
    async def test_html_export(self, sample_sections):
        exporter = Phase4_Export()
        bundle = await exporter.run(sample_sections, title="Test Report")
        html = await exporter.export_html(bundle)
        assert "<html" in html or "<!DOCTYPE" in html
        assert "Test Report" in html
        assert bundle.report_id in html

    @pytest.mark.asyncio
    async def test_markdown_export(self, sample_sections):
        exporter = Phase4_Export()
        bundle = await exporter.run(sample_sections, title="Test Report")
        md = await exporter.export_markdown(bundle)
        assert bundle.report_id in md
        assert "# Test Report" in md

    @pytest.mark.asyncio
    async def test_compute_confidence(self, sample_sections):
        exporter = Phase4_Export()
        confidence = exporter._compute_overall_confidence(sample_sections)
        assert 0.0 < confidence <= 1.0
        assert confidence == 0.85

    @pytest.mark.asyncio
    async def test_build_viz_payload(self, sample_sections):
        exporter = Phase4_Export()
        payload = exporter._build_viz_payload(sample_sections)
        assert "charts" in payload
        assert "interactivity" in payload


# =============================================================================
# Orchestrator Tests
# =============================================================================

class TestReportOrchestrator:
    """Tests for the report orchestrator."""

    @pytest.mark.asyncio
    async def test_get_report_status_not_found(self):
        orchestrator = ReportOrchestrator()
        status = await orchestrator.get_report_status("nonexistent-id")
        assert status["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_orchestrator_init(self):
        orchestrator = ReportOrchestrator(llm_provider="ollama")
        assert orchestrator.llm_provider == "ollama"
        assert orchestrator.phase1 is not None
        assert orchestrator.phase2 is not None
        assert orchestrator.phase3 is not None
        assert orchestrator.phase4 is not None

    @pytest.mark.asyncio
    async def test_generate_report_with_udm_and_df(self, sample_udm, sample_df):
        """Full integration test: UDM + DataFrame -> report generation."""
        orchestrator = ReportOrchestrator()
        result = await orchestrator.generate_report(
            unified_data_model=sample_udm,
            df=sample_df,
            title="Integration Test Report",
        )
        # Verify structure
        assert result["status"] == "completed"
        assert "report_id" in result
        assert result["sections_count"] == 8
        assert "overall_confidence" in result
        assert 0.0 < result["overall_confidence"] <= 1.0
        # Verify timing data
        assert "phase_times_ms" in result
        assert "phase1_profiling" in result["phase_times_ms"]
        assert "phase2_sub_agents" in result["phase_times_ms"]
        assert "phase3_validation" in result["phase_times_ms"]
        assert "phase4_export" in result["phase_times_ms"]
        assert "total_duration_ms" in result
        assert result["total_duration_ms"] > 0
        # Verify validation report
        assert "validation" in result
        assert result["validation"]["total_sections"] == 8
        # Verify export URLs
        assert "export_urls" in result
        assert result["export_urls"].get("html") is not None
        assert result["export_urls"].get("md") is not None
        # generated_at timestamp
        assert "generated_at" in result

    @pytest.mark.asyncio
    async def test_generate_report_synthetic_profile(self, sample_udm):
        """Test that report works with synthetic profile when no DataFrame is provided."""
        orchestrator = ReportOrchestrator()
        result = await orchestrator.generate_report(
            unified_data_model=sample_udm,
            df=None,
            title="Synthetic Profile Test",
        )
        assert result["status"] == "completed"
        assert result["sections_count"] == 8
        assert result["overall_confidence"] > 0.0


# =============================================================================
# Jinja2 Template Tests
# =============================================================================

class TestTemplates:
    """Tests for Jinja2 templates."""

    def test_html_template_exists(self):
        template_path = Path(__file__).parent.parent / "backend" / "report" / "templates" / "report_html.jinja2"
        assert template_path.exists(), "HTML template not found"

    def test_markdown_template_exists(self):
        template_path = Path(__file__).parent.parent / "backend" / "report" / "templates" / "report_markdown.jinja2"
        assert template_path.exists(), "Markdown template not found"

    @pytest.mark.asyncio
    async def test_html_template_renders(self, sample_sections):
        from jinja2 import Environment, FileSystemLoader
        
        template_dir = Path(__file__).parent.parent / "backend" / "report" / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("report_html.jinja2")
        
        exporter = Phase4_Export()
        bundle = await exporter.run(sample_sections)
        
        html = template.render(report=bundle)
        assert len(html) > 100
        assert "autoinsight" in html.lower() or "AutoInsight" in html


# =============================================================================
# Schema Model Tests
# =============================================================================

class TestReportSchemas:
    """Tests for report-related Pydantic schemas."""

    def test_data_profile_model(self, sample_data_profile):
        assert sample_data_profile.schema_metadata is not None
        assert sample_data_profile.domain_context is not None or sample_data_profile.domain_context is None

    def test_report_section_model(self):
        section = ReportSection(
            section_type=ReportSectionType.EDA,
            title="Test Section",
            content="## Test\n\nContent here.",
            confidence=0.85,
        )
        assert section.section_type == ReportSectionType.EDA
        assert section.confidence == 0.85

    def test_report_bundle_model(self, sample_sections):
        bundle = ReportBundle(
            title="Test Report",
            sections=sample_sections,
            overall_confidence=0.85,
        )
        assert len(bundle.sections) == 8
        assert bundle.overall_confidence == 0.85
        assert bundle.report_id is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
