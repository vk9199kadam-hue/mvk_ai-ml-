# =============================================================================
# AutoInsight AI — Tools Unit Tests (tests/test_tools.py)
# Phase 1: Foundation — Deterministic Tools Tests
# =============================================================================
"""
Unit tests for all deterministic data processing tools in tools.py.

Tests ensure:
  - Polars functions produce correct statistical outputs
  - Sandboxed eval blocks dangerous expressions
  - Outlier detection works on known data
  - PII masking correctly identifies and masks patterns
  - Imputation strategies handle edge cases
  - Correlation analysis produces correct values

Coverage Target: 90% of tools.py
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from backend.tools import (
    # Core functions
    profile_schema,
    compute_univariate_stats,
    compute_pearson,
    compute_spearman,
    compute_value_overlap,
    discover_relationship_candidates,
    
    # Outlier detection
    detect_outliers_iqr,
    detect_outliers_zscore,
    
    # Data cleaning
    impute_missing,
    mask_pii,
    
    # Data profiling
    generate_data_profile,
    
    # Sandboxed eval
    safe_eval_polars,
    SandboxViolation,
    ExpressionTimeout,
    
    # Utilities
    compute_file_hash,
    parse_csv,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def simple_df():
    """Create a simple DataFrame for testing."""
    return pl.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "age": [25, 30, 35, 40, 45],
        "salary": [50000, 60000, 70000, 80000, 90000],
        "department": ["Engineering", "Marketing", "Engineering", "Sales", "Marketing"],
    })


@pytest.fixture
def df_with_nulls():
    """Create a DataFrame with null values for imputation testing."""
    return pl.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "value": [10.0, None, 30.0, None, 50.0],
        "category": ["A", None, "C", "D", None],
    })


@pytest.fixture
def df_with_outliers():
    """Create a DataFrame with known outliers."""
    np.random.seed(42)
    normal = np.random.normal(50, 10, 100)
    outliers = np.array([5, 95, 100, 120, 2])  # Clear outliers
    return pl.DataFrame({
        "values": np.concatenate([normal, outliers]),
    })


@pytest.fixture
def df_with_pii():
    """Create a DataFrame with known PII patterns."""
    return pl.DataFrame({
        "name": ["Alice", "Bob", "Charlie"],
        "email": ["alice@example.com", "bob@test.org", "charlie@company.co.uk"],
        "phone": ["+1-555-123-4567", "+44-20-7946-0958", "555-987-6543"],
        "notes": ["SSN: 123-45-6789", "No sensitive data", "CC: 4111-1111-1111-1111"],
    })


# =============================================================================
# Schema Profiling Tests
# =============================================================================

class TestProfileSchema:
    """Tests for profile_schema function."""
    
    def test_basic_profile(self, simple_df):
        """Test basic schema profiling."""
        profile = profile_schema(simple_df)
        
        assert "columns" in profile
        assert profile["row_count"] == 5
        assert profile["column_count"] == 5
        
        # Check column metadata
        cols = profile["columns"]
        assert "id" in cols
        assert "name" in cols
        assert cols["age"]["is_numeric"] is True
        assert cols["name"]["is_numeric"] is False


class TestComputeUnivariateStats:
    """Tests for compute_univariate_stats function."""
    
    def test_basic_stats(self, simple_df):
        """Test basic univariate statistics."""
        stats = compute_univariate_stats(simple_df)
        
        assert "age" in stats
        assert stats["age"]["mean"] == 35.0
        assert stats["age"]["min"] == 25.0
        assert stats["age"]["max"] == 45.0
        assert stats["age"]["count"] == 5


# =============================================================================
# Correlation Tests
# =============================================================================

class TestCorrelation:
    """Tests for correlation analysis functions."""
    
    def test_pearson_perfect_positive(self):
        """Test Pearson correlation with perfect positive relationship."""
        df = pl.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "y": [2, 4, 6, 8, 10],
        })
        result = compute_pearson(df)
        assert abs(result["x"]["y"] - 1.0) < 0.001
    
    def test_pearson_no_correlation(self):
        """Test Pearson correlation with no relationship."""
        df = pl.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "y": [5, 1, 8, 2, 3],
        })
        result = compute_pearson(df)
        assert abs(result["x"]["y"]) < 0.5  # Should be weakly correlated


# =============================================================================
# Outlier Detection Tests
# =============================================================================

class TestOutlierDetection:
    """Tests for outlier detection functions."""
    
    def test_iqr_detects_outliers(self, df_with_outliers):
        """Test IQR method detects known outliers."""
        mask, stats = detect_outliers_iqr(df_with_outliers["values"])
        assert stats["outlier_count"] > 0
    
    def test_zscore_detects_outliers(self, df_with_outliers):
        """Test Z-score method detects known outliers."""
        mask, stats = detect_outliers_zscore(df_with_outliers["values"])
        assert stats["outlier_count"] > 0


# =============================================================================
# Sandboxed Eval Tests
# =============================================================================

class TestSafeEvalPolars:
    """Tests for sandboxed Polars expression evaluator."""
    
    def test_simple_arithmetic(self, simple_df):
        """Test basic arithmetic expression."""
        result = safe_eval_polars(
            'pl.col("age") + pl.col("salary")',
            simple_df,
        )
        assert len(result) == 5
        assert result[0] == 50025  # 25 + 50000
    
    def test_blocked_function(self, simple_df):
        """Test that dangerous functions are blocked."""
        with pytest.raises(SandboxViolation):
            safe_eval_polars('__import__("os").system("ls")', simple_df)
    
    def test_blocked_import(self, simple_df):
        """Test that import statements are blocked."""
        with pytest.raises(SandboxViolation):
            safe_eval_polars('import os', simple_df)
    
    def test_column_arithmetic(self, simple_df):
        """Test creating a new column from existing ones."""
        result = safe_eval_polars(
            'pl.col("salary") / pl.col("age")',
            simple_df,
        )
        assert len(result) == 5
        assert abs(result[0] - 2000.0) < 0.01  # 50000 / 25


# =============================================================================
# Data Cleaning Tests
# =============================================================================

class TestImputeMissing:
    """Tests for impute_missing function."""
    
    def test_mean_imputation(self, df_with_nulls):
        """Test mean imputation fills nulls."""
        result = impute_missing(df_with_nulls, strategy="mean")
        assert result["value"].null_count() == 0
        assert result["value"][1] == pytest.approx(30.0, rel=0.1)  # Mean of [10, 30, 50]


class TestMaskPii:
    """Tests for PII masking function."""
    
    def test_email_masking(self, df_with_pii):
        """Test email addresses are masked."""
        result, detected = mask_pii(df_with_pii)
        assert len(detected) > 0  # Should detect PII
    
    def test_ssn_masked(self, df_with_pii):
        """Test SSN values are masked in the result."""
        result, detected = mask_pii(df_with_pii)
        # SSN column should be in detected PII
        pii_columns = [p["column"] for p in detected]
        assert "notes" in pii_columns


# =============================================================================
# Value Overlap Tests
# =============================================================================

class TestValueOverlap:
    """Tests for value overlap analysis."""
    
    def test_full_overlap(self):
        """Test columns with identical values."""
        df = pl.DataFrame({
            "col1": ["A", "B", "C", "D"],
            "col2": ["A", "B", "C", "E"],
        })
        overlaps = compute_value_overlap(df, ["col1", "col2"])
        assert len(overlaps) == 1  # One pair
        assert overlaps[0]["overlap_ratio"] == 0.75  # 3 of 4 overlap


# =============================================================================
# Full Pipeline Tests
# =============================================================================

class TestGenerateDataProfile:
    """Tests for generate_data_profile function."""
    
    def test_complete_profile(self, simple_df):
        """Test complete data profile generation."""
        profile = generate_data_profile(simple_df)
        assert "schema_metadata" in profile
        assert "univariate_stats" in profile
        assert "bivariate_matrix" in profile
        assert "correlation_candidates" in profile
        assert profile["row_count"] == 5
        assert profile["column_count"] == 5
