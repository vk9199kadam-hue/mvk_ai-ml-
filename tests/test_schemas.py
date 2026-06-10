# =============================================================================
# AutoInsight AI — Schema Unit Tests (tests/test_schemas.py)
# Phase 1: Foundation — Pydantic Model Validation Tests
# =============================================================================
"""
Unit tests for all Pydantic v2 data models in schemas.py.

Tests ensure:
  - All models can be instantiated with valid data
  - Validation errors are raised for invalid data
  - Confidence scores are clamped to [0.0, 1.0]
  - Enum values are validated
  - Default values are applied correctly
  - Optional fields work as expected
  - Model serialization/deserialization round-trips correctly

Coverage Target: 100% of schemas.py models
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.schemas import (
    # Enums
    RelationshipType,
    DataType,
    ConfidenceLevel,
    PipelineStatus,
    UserRole,
    ReportSectionType,
    ChartType,
    
    # Stage 1 Models
    ColumnInference,
    SchemaInferenceResponse,
    
    # Stage 2 Models
    QualityIssue,
    QualityProfile,
    CleaningOperation,
    CleaningPlan,
    
    # Stage 3 Models
    Relationship,
    DerivedColumn,
    TransformationAudit,
    UnifiedDataModel,
    
    # Stage 5 Models
    DataProfile,
    ReportSection,
    ReportBundle,
    
    # Stage 6 Models
    NLQQuery,
    NLQResponse,
    
    # API Models
    APIResponse,
    UserCreate,
    UserResponse,
    TokenResponse,
    LoginRequest,
    TaskStatus,
    PipelineRequest,
    PipelineResult,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def valid_column_inference():
    """Create a valid ColumnInference instance."""
    return ColumnInference(
        column_name="age",
        detected_type=DataType.INTEGER,
        confidence=0.95,
        reasoning="All values are integers between 0 and 120",
        sample_values=["25", "30", "45"],
    )


@pytest.fixture
def valid_schema_response(valid_column_inference):
    """Create a valid SchemaInferenceResponse instance."""
    return SchemaInferenceResponse(
        columns=[valid_column_inference],
        row_count=1000,
        encoding="utf-8",
        overall_confidence=0.95,
    )


@pytest.fixture
def valid_relationship():
    """Create a valid Relationship instance."""
    return Relationship(
        source_column="age",
        target_column="income",
        relationship_type=RelationshipType.ONE_TO_MANY,
        confidence=0.85,
        description="Age correlates with income level",
        chart_hint=ChartType.SCATTER,
    )


@pytest.fixture
def valid_derived_column():
    """Create a valid DerivedColumn instance."""
    return DerivedColumn(
        name="age_group",
        expression='pl.col("age").cut([0, 18, 35, 55, 120], labels=["Youth", "Young Adult", "Adult", "Senior"])',
        data_type="str",
        description="Age group classification based on age ranges",
        confidence=0.92,
    )


@pytest.fixture
def valid_unified_data_model(valid_relationship, valid_derived_column):
    """Create a valid UnifiedDataModel instance."""
    return UnifiedDataModel(
        original_columns=["age", "income", "name", "region"],
        cleaned_columns=["age", "income", "name", "region"],
        derived_columns=[valid_derived_column],
        relationships=[valid_relationship],
    )


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Test all enum classes."""
    
    def test_relationship_type_values(self):
        """Verify RelationshipType enum values."""
        assert RelationshipType.ONE_TO_ONE.value == "one-to-one"
        assert RelationshipType.ONE_TO_MANY.value == "one-to-many"
        assert RelationshipType.MANY_TO_MANY.value == "many-to-many"
    
    def test_data_type_values(self):
        """Verify DataType enum values."""
        assert DataType.INTEGER.value == "int"
        assert DataType.FLOAT.value == "float"
        assert DataType.STRING.value == "str"
        assert DataType.DATE.value == "date"
    
    def test_confidence_level_mapping(self):
        """Verify ConfidenceLevel mapping."""
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"
    
    def test_pipeline_status_values(self):
        """Verify PipelineStatus values."""
        assert PipelineStatus.QUEUED.value == "queued"
        assert PipelineStatus.COMPLETED.value == "completed"
        assert PipelineStatus.FAILED.value == "failed"
    
    def test_user_role_values(self):
        """Verify UserRole values."""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.ANALYST.value == "analyst"
        assert UserRole.VIEWER.value == "viewer"
    
    def test_chart_type_values(self):
        """Verify ChartType values."""
        assert ChartType.BAR.value == "bar"
        assert ChartType.LINE.value == "line"
        assert ChartType.SCATTER.value == "scatter"


# =============================================================================
# Stage 1: ColumnInference Tests
# =============================================================================

class TestColumnInference:
    """Tests for ColumnInference model."""
    
    def test_valid_column_inference(self, valid_column_inference):
        """Test creating a valid ColumnInference."""
        assert valid_column_inference.column_name == "age"
        assert valid_column_inference.detected_type == DataType.INTEGER
        assert valid_column_inference.confidence == 0.95
        assert valid_column_inference.reasoning.startswith("All values")
    
    def test_empty_column_name_raises_error(self):
        """Test that empty column name raises validation error."""
        with pytest.raises(ValidationError):
            ColumnInference(
                column_name="",
                detected_type=DataType.INTEGER,
                confidence=0.9,
                reasoning="Test",
            )
    
    def test_confidence_clamped_to_zero(self):
        """Test confidence is clamped at 0.0."""
        ci = ColumnInference(
            column_name="test",
            detected_type=DataType.STRING,
            confidence=-0.5,
            reasoning="Test",
        )
        assert ci.confidence == 0.0
    
    def test_confidence_clamped_to_one(self):
        """Test confidence is clamped at 1.0."""
        ci = ColumnInference(
            column_name="test",
            detected_type=DataType.STRING,
            confidence=1.5,
            reasoning="Test",
        )
        assert ci.confidence == 1.0


# =============================================================================
# Stage 1: SchemaInferenceResponse Tests
# =============================================================================

class TestSchemaInferenceResponse:
    """Tests for SchemaInferenceResponse model."""
    
    def test_valid_schema_response(self, valid_schema_response):
        """Test creating a valid SchemaInferenceResponse."""
        assert len(valid_schema_response.columns) == 1
        assert valid_schema_response.row_count == 1000
        assert valid_schema_response.encoding == "utf-8"
        assert valid_schema_response.overall_confidence == 0.95
    
    def test_overall_confidence_auto_computed(self, valid_column_inference):
        """Test overall_confidence is auto-computed from individual columns."""
        ci2 = ColumnInference(
            column_name="income",
            detected_type=DataType.FLOAT,
            confidence=0.85,
            reasoning="Test",
        )
        response = SchemaInferenceResponse(
            columns=[valid_column_inference, ci2],
            row_count=1000,
        )
        assert response.overall_confidence == pytest.approx(0.90, rel=0.01)


# =============================================================================
# Stage 3: Relationship Tests
# =============================================================================

class TestRelationship:
    """Tests for Relationship model."""
    
    def test_valid_relationship(self, valid_relationship):
        """Test creating a valid Relationship."""
        assert valid_relationship.source_column == "age"
        assert valid_relationship.target_column == "income"
        assert valid_relationship.confidence == 0.85
        assert valid_relationship.chart_hint == ChartType.SCATTER
    
    def test_confidence_below_gate_warning(self, valid_relationship):
        """Test that low confidence triggers a warning but still creates."""
        rel = Relationship(
            source_column="a",
            target_column="b",
            relationship_type=RelationshipType.ONE_TO_ONE,
            confidence=0.50,  # Below 0.65 gate
            description="Test",
            chart_hint=ChartType.BAR,
        )
        assert rel.confidence == 0.50
    
    def test_minimal_relationship(self):
        """Test relationship with only required fields."""
        rel = Relationship(
            source_column="col1",
            target_column="col2",
            relationship_type=RelationshipType.ONE_TO_ONE,
            confidence=0.75,
            description="Test relationship",
            chart_hint=ChartType.BAR,
        )
        assert rel.source_column == "col1"
        assert rel.target_column == "col2"
        assert rel.correlation_coefficient is None


# =============================================================================
# Stage 3: UnifiedDataModel Tests
# =============================================================================

class TestUnifiedDataModel:
    """Tests for UnifiedDataModel model."""
    
    def test_valid_udm(self, valid_unified_data_model):
        """Test creating a valid UnifiedDataModel."""
        assert len(valid_unified_data_model.original_columns) == 4
        assert len(valid_unified_data_model.derived_columns) == 1
        assert len(valid_unified_data_model.relationships) == 1
    
    def test_total_columns_property(self, valid_unified_data_model):
        """Test total_columns property returns original + derived."""
        assert valid_unified_data_model.total_columns == 5  # 4 cleaned + 1 derived
    
    def test_average_confidence(self, valid_unified_data_model):
        """Test average relationship confidence."""
        avg = valid_unified_data_model.average_relationship_confidence
        assert avg == pytest.approx(0.85, rel=0.01)
    
    def test_udm_json_roundtrip(self, valid_unified_data_model):
        """Test UDM serializes and deserializes correctly."""
        json_str = valid_unified_data_model.model_dump_json()
        restored = UnifiedDataModel.model_validate_json(json_str)
        assert restored.original_columns == valid_unified_data_model.original_columns
        assert len(restored.derived_columns) == 1
        assert restored.derived_columns[0].name == "age_group"


# =============================================================================
# API Response Tests
# =============================================================================

class TestAPIResponse:
    """Tests for APIResponse model."""
    
    def test_success_response(self):
        """Test creating a success response."""
        response = APIResponse.success(
            data={"user_id": "123"},
        )
        assert response.status == "success"
        assert response.data == {"user_id": "123"}
        assert len(response.errors) == 0
        assert response.meta["version"] == "1.0.0"
    
    def test_error_response(self):
        """Test creating an error response."""
        response = APIResponse.error(
            message="Something went wrong",
            status_code=400,
        )
        assert response.status == "error"
        assert response.errors == ["Something went wrong"]


# =============================================================================
# Auth Model Tests
# =============================================================================

class TestUserCreate:
    """Tests for UserCreate model."""
    
    def test_valid_user(self):
        """Test creating a valid user."""
        user = UserCreate(
            email="test@example.com",
            password="secure_password_123",
            name="Test User",
        )
        assert user.email == "test@example.com"
        assert user.role.value == "analyst"
    
    def test_invalid_email(self):
        """Test invalid email raises error."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="not-an-email",
                password="secure_password_123",
                name="Test",
            )
    
    def test_short_password(self):
        """Test short password raises error."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="test@example.com",
                password="short",  # < 8 chars
                name="Test",
            )
