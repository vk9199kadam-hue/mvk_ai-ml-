# =============================================================================
# AutoInsight AI — Stage 4: Column Engineering & UDM Assembly - Phase 2
# Phase 2: Core Pipeline — Full Enhanced Implementation
# =============================================================================
"""
Stage 4: Column Engineering & UnifiedDataModel Assembly (Phase 2 Enhanced).

Materializes derived column expressions, validates output types, and assembles
the final visualization-ready enriched dataset (UnifiedDataModel).

This stage is FULLY DETERMINISTIC — no LLM calls.
Safety is enforced via AST-based sandboxed Polars evaluation.

Pipeline Position: Stage 4 of 4 (Final Pipeline Stage)
Input:  UnifiedDataModel (from Stage 3) + Cleaned DataFrame
Output: Complete UnifiedDataModel with materialized columns + viz schema
LLM:    None (fully deterministic)

Flow:
  1. Evaluate each derived column expression (safe Polars eval)
  2. Validate output types against schema
  3. Check for NaN/Inf in numeric results
  4. Record audit trail per column
  5. Generate final visualization schema from relationships
  6. Generate recommended dashboard layout
  7. Return complete UnifiedDataModel
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from backend.schemas import (
    ChartType,
    DerivedColumn,
    Relationship,
    TransformationAudit,
    UnifiedDataModel,
)
from backend.tools import safe_eval_polars, SandboxViolation

logger = logging.getLogger(__name__)

# Maximum execution time for a single derived column expression (seconds)
MAX_EXPRESSION_TIMEOUT = 5


class ColumnEngineError(Exception):
    """Base exception for column engineering errors."""
    pass


class Stage4_ColumnEngine:
    """
    Stage 4: Column Engineering & UDM Assembly.

    Takes the UnifiedDataModel from Stage 3 and:
      1. Safely evaluates Polars expressions for derived columns
      2. Validates output data types against expected schema
      3. Checks for NaN/Inf in numeric results
      4. Records audit trail for each transformation
      5. Assembles the final enriched dataset
      6. Generates visualization schema and dashboard layout
    """

    async def run(
        self,
        df: pl.DataFrame,
        udm: UnifiedDataModel,
    ) -> UnifiedDataModel:
        """
        Execute Stage 4 column engineering.

        Args:
            df: Cleaned DataFrame from Stage 2
            udm: UnifiedDataModel from Stage 3 (with relationships + derived columns)

        Returns:
            Complete UnifiedDataModel with materialized derived columns,
            audit trail, visualization schema, and dashboard layout

        Raises:
            ColumnEngineError: If column engineering fails
        """
        logger.info(
            f"Stage 4: Engineering {len(udm.derived_columns)} derived columns, "
            f"{len(udm.relationships)} relationships"
        )

        # ── Step 1: Evaluate Derived Columns ──────────────────────────────
        successful_columns = []
        for col_def in udm.derived_columns:
            try:
                logger.info(f"Stage 4: Evaluating '{col_def.name}' = {col_def.expression}")

                # Execute the expression safely
                result = await self._evaluate_safely(col_def, df)

                # Validate the result
                validation = self._validate_result(result, col_def, df)

                if validation["passed"]:
                    successful_columns.append(col_def)
                    udm.transformation_audit.append(
                        TransformationAudit(
                            step="column_engineering",
                            column=col_def.name,
                            description=f"Derived column '{col_def.name}' = {col_def.expression}",
                            expression=col_def.expression,
                            timestamp=datetime.utcnow(),
                            status="completed",
                        ).model_dump()
                    )
                    logger.debug(f"Stage 4: '{col_def.name}' validated successfully")
                else:
                    logger.warning(
                        f"Stage 4: '{col_def.name}' validation failed: "
                        f"{validation['errors']}"
                    )
                    udm.transformation_audit.append(
                        TransformationAudit(
                            step="column_engineering",
                            column=col_def.name,
                            description=f"Validation failed: {validation['errors']}",
                            expression=col_def.expression,
                            timestamp=datetime.utcnow(),
                            status="failed",
                        ).model_dump()
                    )

            except SandboxViolation as e:
                logger.error(f"Stage 4: Sandbox violation for '{col_def.name}': {e}")
                udm.transformation_audit.append(
                    TransformationAudit(
                        step="column_engineering",
                        column=col_def.name,
                        description=f"Sandbox violation: {e}",
                        expression=col_def.expression,
                        timestamp=datetime.utcnow(),
                        status="failed",
                    ).model_dump()
                )

            except Exception as e:
                logger.error(f"Stage 4: Failed to evaluate '{col_def.name}': {e}")
                udm.transformation_audit.append(
                    TransformationAudit(
                        step="column_engineering",
                        column=col_def.name,
                        description=f"Evaluation error: {e}",
                        expression=col_def.expression,
                        timestamp=datetime.utcnow(),
                        status="failed",
                    ).model_dump()
                )

        # Update derived columns with only successful ones
        udm.derived_columns = successful_columns

        # ── Step 2: Generate Visualization Schema ─────────────────────────
        udm.final_viz_schema = self._generate_viz_schema(udm.relationships)
        udm.recommended_dashboard_layout = self._generate_dashboard_layout(
            udm.relationships
        )

        logger.info(
            f"Stage 4: Complete — "
            f"{len(successful_columns)}/{len(udm.derived_columns)} columns materialized, "
            f"{len(udm.relationships)} relationships, "
            f"{len(udm.transformation_audit)} audit entries"
        )

        return udm

    async def _evaluate_safely(
        self,
        col_def: DerivedColumn,
        df: pl.DataFrame,
    ) -> pl.Series:
        """
        Safely evaluate a derived column expression.

        Args:
            col_def: Derived column definition
            df: DataFrame to evaluate against

        Returns:
            Resulting Polars Series
        """
        # Check column references exist
        referenced = re.findall(r'pl\.col\("([^"]+)"\)', col_def.expression)
        for ref_col in referenced:
            if ref_col not in df.columns:
                raise ColumnEngineError(
                    f"Expression references unknown column '{ref_col}'"
                )

        # Check for dangerous patterns
        dangerous = ["__import__", "eval(", "exec(", "os.", "sys.", "subprocess"]
        for pattern in dangerous:
            if pattern in col_def.expression:
                raise SandboxViolation(
                    f"Dangerous pattern detected in expression: '{pattern}'"
                )

        # Evaluate
        result = safe_eval_polars(
            col_def.expression,
            df,
            timeout_seconds=MAX_EXPRESSION_TIMEOUT,
        )

        return result

    def _validate_result(
        self,
        result: pl.Series,
        col_def: DerivedColumn,
        df: pl.DataFrame,
    ) -> Dict[str, Any]:
        """
        Validate a derived column result.

        Checks:
          - Type matches expected type
          - Length matches DataFrame
          - No NaN or Inf values (for numeric types)
          - Not all values are null
          - Validation rules pass

        Args:
            result: Evaluated series
            col_def: Column definition with expected type/rules
            df: Original DataFrame

        Returns:
            Dict with passed (bool) and errors (list)
        """
        errors = []

        # Check length
        if len(result) != len(df):
            errors.append(
                f"Length mismatch: expected {len(df)}, got {len(result)}"
            )

        # Check type
        actual_type = str(result.dtype)
        expected_type = col_def.data_type.lower()
        type_match = expected_type in actual_type.lower()
        if not type_match:
            errors.append(
                f"Type mismatch: expected '{expected_type}', actual '{actual_type}'"
            )

        # Check NaN/Inf (numeric types only)
        if result.dtype in (pl.Float32, pl.Float64):
            nan_count = result.is_nan().sum() if hasattr(result, 'is_nan') else 0
            inf_mask = result.is_infinite() if hasattr(result, 'is_infinite') else None
            inf_count = int(inf_mask.sum()) if inf_mask is not None else 0

            if nan_count > 0:
                errors.append(f"Contains {nan_count} NaN values")
            if inf_count > 0:
                errors.append(f"Contains {inf_count} infinite values")

        # Check not all null
        if result.null_count() == len(result):
            errors.append("All values are null")

        # Check custom validation rules
        for rule in col_def.validation_rules:
            rule_result = self._check_validation_rule(rule, result)
            if not rule_result["passed"]:
                errors.append(f"Validation rule '{rule}' failed: {rule_result.get('message', '')}")

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "actual_type": actual_type,
        }

    def _check_validation_rule(
        self,
        rule: str,
        series: pl.Series,
    ) -> Dict[str, Any]:
        """Check a single validation rule against a series."""
        if rule == "no_zero_denominator":
            zero_count = (series == 0).sum() if hasattr(series, 'sum') else 0
            if int(zero_count) > 0:
                return {"passed": False, "message": f"Contains {zero_count} zero values"}
            return {"passed": True}

        if rule == "non_negative":
            if series.dtype in (pl.Float32, pl.Float64, pl.Int64):
                neg_count = (series < 0).sum() if hasattr(series, 'sum') else 0
                if int(neg_count) > 0:
                    return {"passed": False, "message": f"Contains {neg_count} negative values"}
            return {"passed": True}

        if rule == "no_null":
            if series.null_count() > 0:
                return {"passed": False, "message": f"Contains {series.null_count()} null values"}
            return {"passed": True}

        # Unknown rule — pass by default
        return {"passed": True}

    def _generate_viz_schema(
        self,
        relationships: List[Relationship],
    ) -> Dict[str, Any]:
        """Generate visualization schema from relationships."""
        charts = []
        for rel in relationships:
            chart_type = rel.chart_hint
            if isinstance(chart_type, ChartType):
                chart_type = chart_type.value

            charts.append({
                "id": f"chart-{rel.source_column}-{rel.target_column}".replace(
                    " ", "_"
                ),
                "type": chart_type,
                "title": f"{rel.source_column} vs {rel.target_column}",
                "mark": self._chart_type_to_mark(chart_type),
                "encoding": {
                    "x": {"field": rel.source_column, "type": "quantitative"},
                    "y": {"field": rel.target_column, "type": "quantitative"},
                    "color": {
                        "field": rel.source_column,
                        "type": "nominal",
                        "legend": {"title": rel.source_column},
                    },
                    "tooltip": [
                        {"field": rel.source_column, "type": "quantitative"},
                        {"field": rel.target_column, "type": "quantitative"},
                    ],
                },
                "confidence": rel.confidence,
                "description": rel.description,
                "analytical_purpose": rel.analytical_purpose,
                "width": 400,
                "height": 300,
            })

        return {
            "charts": charts,
            "theme": "light",
            "interactivity": {
                "zoom": True,
                "pan": True,
                "hover_tooltips": True,
                "drill_down": True,
                "brush": True,
            },
            "config": {
                "default_width": 400,
                "default_height": 300,
                "color_scheme": "tableau10",
                "background": "#ffffff",
                "title_font_size": 14,
                "label_font_size": 11,
            },
        }

    def _chart_type_to_mark(self, chart_type: str) -> str:
        """Convert chart type to Vega-Lite mark type."""
        mapping = {
            "bar": "bar",
            "line": "line",
            "scatter": "point",
            "heatmap": "rect",
            "box": "box-plot",
            "pie": "arc",
            "histogram": "bar",
            "area": "area",
            "bubble": "circle",
            "treemap": "rect",
        }
        return mapping.get(chart_type, "point")

    def _generate_dashboard_layout(
        self,
        relationships: List[Relationship],
    ) -> Dict[str, Any]:
        """Generate recommended dashboard layout."""
        layout = {
            "grid_columns": 2,
            "responsive_breakpoints": {
                "mobile": {"columns": 1, "breakpoint_px": 480},
                "tablet": {"columns": 2, "breakpoint_px": 768},
                "desktop": {"columns": 3, "breakpoint_px": 1024},
            },
            "chart_positions": [],
            "filters": {
                "global": True,
                "linked_brushing": True,
                "filter_types": ["range", "dropdown", "search"],
            },
            "kpi_section": {
                "enabled": True,
                "position": "top",
                "max_kpis": 4,
            },
        }

        for idx, rel in enumerate(relationships):
            layout["chart_positions"].append({
                "id": f"chart-{rel.source_column}-{rel.target_column}".replace(
                    " ", "_"
                ),
                "priority": idx,
                "width": 1,
                "height": 1,
                "x": idx % 2,
                "y": idx // 2,
            })

        return layout
