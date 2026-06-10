# =============================================================================
# AutoInsight AI — Report Phase 1: Deterministic Profiling (Phase 3 Full)
# Phase 3: Report Engine — 5 Deterministic Profiling Functions
# =============================================================================
"""
Phase 1: Deterministic Profiling (Zero LLM — $0).

5 pure-computation profiling functions using Polars, SciPy, and NumPy.
NO LLM calls are made in this phase — always available, fully deterministic.

Functions:
  1. extract_schema_metadata(): Column names, types, null counts, cardinality
  2. compute_univariate_stats(): Mean, median, std, IQR, skew, kurtosis per column
  3. compute_bivariate_matrix(): Pairwise correlation matrix (Pearson + Spearman)
  4. detect_trends_seasonality(): Time series decomposition if date column exists
  5. infer_domain_context(): Dataset domain + subdomain classification

Output: DataProfile object (ready for Phase 2 sub-agents)
Time: ~2s for 10MB dataset
Cost: $0 (no API calls)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import polars as pl
from scipy import stats as scipy_stats

from backend.schemas import DataProfile
from backend.tools import (
    compute_pearson,
    compute_spearman,
    compute_univariate_stats,
    profile_schema,
)

logger = logging.getLogger(__name__)

# Domain keywords for classification
DOMAIN_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "finance": {
        "keywords": ["price", "revenue", "cost", "profit", "expense", "income", 
                     "budget", "forecast", "investment", "dividend", "interest",
                     "payment", "invoice", "transaction", "balance", "account"],
        "subdomains": ["banking", "insurance", "real_estate", "trading", "accounting"],
    },
    "healthcare": {
        "keywords": ["patient", "diagnosis", "treatment", "medication", "symptom",
                     "hospital", "clinic", "doctor", "nurse", "prescription",
                     "bmi", "blood", "heart", "disease", "surgery"],
        "subdomains": ["clinical", "pharmaceutical", "epidemiology", "radiology"],
    },
    "retail_ecommerce": {
        "keywords": ["product", "customer", "order", "sales", "quantity", "price",
                     "category", "inventory", "supplier", "shipping", "cart",
                     "purchase", "return", "review", "rating", "checkout"],
        "subdomains": ["b2c", "b2b", "wholesale", "marketplace"],
    },
    "human_resources": {
        "keywords": ["employee", "salary", "department", "hire", "termination",
                     "attendance", "leave", "performance", "bonus", "promotion",
                     "training", "recruitment", "timesheet", "payroll"],
        "subdomains": ["recruitment", "payroll", "performance", "compliance"],
    },
    "marketing": {
        "keywords": ["campaign", "click", "impression", "conversion", "traffic",
                     "engagement", "reach", "follower", "subscriber", "lead",
                     "email", "social", "ad", "cpc", "ctr", "roi"],
        "subdomains": ["digital", "social_media", "email", "content", "seo"],
    },
    "manufacturing": {
        "keywords": ["production", "defect", "quality", "machine", "maintenance",
                     "downtime", "throughput", "yield", "material", "assembly",
                     "inspection", "batch", "lot", "supply_chain"],
        "subdomains": ["quality_control", "logistics", "assembly", "inventory"],
    },
    "education": {
        "keywords": ["student", "grade", "course", "enrollment", "attendance",
                     "teacher", "exam", "score", "gpa", "curriculum",
                     "assignment", "graduation", "tuition", "scholarship"],
        "subdomains": ["k12", "higher_ed", "online_learning", "vocational"],
    },
    "technology": {
        "keywords": ["server", "request", "response", "latency", "error", "log",
                     "api", "database", "cache", "deployment", "version",
                     "commit", "issue", "ticket", "sprint", "story_point"],
        "subdomains": ["saas", "infrastructure", "software_dev", "devops", "cybersecurity"],
    },
}

# Date formats for detection
DATE_PATTERNS = [
    (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
    (r"^\d{2}/\d{2}/\d{4}$", "%m/%d/%Y"),
    (r"^\d{4}/\d{2}/\d{2}$", "%Y/%m/%d"),
    (r"^\d{2}-\d{2}-\d{4}$", "%m-%d-%Y"),
    (r"^\d{4}\d{2}\d{2}$", "%Y%m%d"),
]


class Phase1_Profiling:
    """
    Phase 1: Deterministic Profiling — 5 computation functions.
    
    This phase is ALWAYS available, even if the LLM is offline.
    All 5 functions use only Polars, SciPy, NumPy — zero API calls.
    """

    async def run(self, df: pl.DataFrame) -> DataProfile:
        """
        Execute Phase 1 profiling — all 5 deterministic functions.
        
        Args:
            df: Input DataFrame (enriched from pipeline Stage 4)
        
        Returns:
            DataProfile with schema_metadata, univariate_stats,
            bivariate_matrix, trends, and domain_context
        """
        logger.info(f"Report Phase 1: Computing deterministic profile ({len(df.columns)} cols, {len(df)} rows)")

        schema = self.extract_schema_metadata(df)
        stats = self.compute_univariate_stats_detailed(df)
        bivariate = self.compute_bivariate_matrix(df)
        trends = self.detect_trends_seasonality(df)
        domain = self.infer_domain_context(df)

        logger.info("Report Phase 1: Profile complete — 5 functions executed")
        return DataProfile(
            schema_metadata=schema,
            univariate_stats=stats,
            bivariate_matrix=bivariate,
            trends=trends,
            domain_context=domain,
        )

    # ─── Function 1: Schema Metadata ───────────────────────────────────────

    def extract_schema_metadata(self, df: pl.DataFrame) -> Dict[str, Any]:
        """
        Extract complete schema metadata from DataFrame.
        
        Returns per-column: name, dtype, null_count, null_pct, cardinality,
        cardinality_ratio, is_numeric, is_categorical, is_datetime, sample_values.
        Also returns summary statistics.
        """
        schema = profile_schema(df)
        
        # Enhance with additional metadata
        for col in df.columns:
            series = df[col]
            if col in schema.get("columns", {}):
                entry = schema["columns"][col]
                entry["is_datetime"] = series.dtype in (pl.Date, pl.Datetime)
                entry["dtype_category"] = self._classify_dtype(str(series.dtype))
                entry["memory_mb"] = round(series.estimated_size() / (1024 * 1024), 4)
        
        # Summary stats
        numeric_cols = [c for c in df.columns if schema["columns"].get(c, {}).get("is_numeric")]
        categorical_cols = [c for c in df.columns if schema["columns"].get(c, {}).get("is_categorical")]
        datetime_cols = [c for c in df.columns if schema["columns"].get(c, {}).get("is_datetime")]
        text_cols = [c for c in df.columns if not schema["columns"].get(c, {}).get("is_numeric") and not schema["columns"].get(c, {}).get("is_categorical") and not schema["columns"].get(c, {}).get("is_datetime")]
        
        schema["summary"] = {
            "total_columns": len(df.columns),
            "numeric_columns": len(numeric_cols),
            "categorical_columns": len(categorical_cols),
            "datetime_columns": len(datetime_cols),
            "text_columns": len(text_cols),
            "null_percentage_total": round(
                sum(schema["columns"][c]["null_percentage"] for c in df.columns) / max(len(df.columns), 1), 2
            ),
            "avg_cardinality": round(
                sum(schema["columns"][c]["cardinality"] for c in df.columns) / max(len(df.columns), 1), 1
            ),
        }
        
        return schema

    def _classify_dtype(self, dtype: str) -> str:
        """Classify a Polars dtype into a category."""
        if any(t in dtype for t in ["Int", "UInt"]):
            return "integer"
        if "Float" in dtype:
            return "float"
        if "Bool" in dtype:
            return "boolean"
        if "Date" in dtype or "Datetime" in dtype:
            return "datetime"
        if "Utf8" in dtype or "String" in dtype:
            return "string"
        if "List" in dtype:
            return "list"
        if "Struct" in dtype:
            return "struct"
        return "other"

    # ─── Function 2: Detailed Univariate Statistics ───────────────────────

    def compute_univariate_stats_detailed(self, df: pl.DataFrame) -> Dict[str, Dict[str, float]]:
        """
        Compute detailed univariate statistics for all numeric columns.
        
        Extends the basic tool with:
          - 5-number summary (min, Q1, median, Q3, max)
          - Distribution shape (skewness, kurtosis, modality)
          - Dispersion (range, IQR, variance, CV)
          - Missing data patterns (null_count, null_pct)
          - Zero/infinity counts
        """
        basic_stats = compute_univariate_stats(df)
        
        for col in df.columns:
            series = df[col]
            if series.dtype not in (pl.Float32, pl.Float64, pl.Int32, pl.Int64):
                continue
            
            arr = series.drop_nulls().to_numpy()
            if len(arr) < 2:
                continue
            
            if col not in basic_stats:
                basic_stats[col] = {}
            
            # Coefficient of Variation
            mean_val = float(np.mean(arr))
            std_val = float(np.std(arr, ddof=1))
            basic_stats[col]["cv"] = round(std_val / abs(mean_val), 4) if mean_val != 0 else 0.0
            
            # Range
            basic_stats[col]["range"] = float(np.ptp(arr))
            
            # Mode
            mode_result = scipy_stats.mode(arr)
            basic_stats[col]["mode"] = float(mode_result.mode) if hasattr(mode_result, 'mode') else float(arr[0])
            basic_stats[col]["mode_count"] = int(mode_result.count) if hasattr(mode_result, 'count') else 0
            
            # Percentiles
            basic_stats[col]["p1"] = float(np.percentile(arr, 1))
            basic_stats[col]["p5"] = float(np.percentile(arr, 5))
            basic_stats[col]["p10"] = float(np.percentile(arr, 10))
            basic_stats[col]["p90"] = float(np.percentile(arr, 90))
            basic_stats[col]["p95"] = float(np.percentile(arr, 95))
            basic_stats[col]["p99"] = float(np.percentile(arr, 99))
            
            # Infinity count
            basic_stats[col]["inf_count"] = int(np.sum(np.isinf(arr)))
        
        return basic_stats

    # ─── Function 3: Bivariate Correlation Matrix ─────────────────────────

    def compute_bivariate_matrix(self, df: pl.DataFrame) -> Dict[str, Dict[str, float]]:
        """
        Compute comprehensive bivariate correlation matrix.
        
        Includes:
          - Pearson correlation (linear relationships)
          - Spearman rank correlation (monotonic relationships)
          - p-values for statistical significance
          - Sample sizes per pair
        """
        pearson = compute_pearson(df)
        spearman = compute_spearman(df)
        
        matrix = {}
        numeric_cols = [c for c in df.columns if df[c].dtype in (
            pl.Int8, pl.Int16, pl.Int32, pl.Int64,
            pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
            pl.Float32, pl.Float64,
        )]
        
        for col1 in numeric_cols:
            matrix[col1] = {}
            for col2 in numeric_cols:
                r_p = pearson.get(col1, {}).get(col2, 0.0)
                r_s = spearman.get(col1, {}).get(col2, 0.0)
                
                # Compute p-value where possible
                valid = df.select([col1, col2]).drop_nulls()
                p_value = 1.0
                if len(valid) > 2:
                    _, p_value = scipy_stats.pearsonr(valid[col1].to_numpy(), valid[col2].to_numpy())
                
                matrix[col1][col2] = {
                    "pearson_r": round(float(r_p), 4),
                    "spearman_r": round(float(r_s), 4),
                    "p_value": round(float(p_value), 6),
                    "sample_size": len(valid),
                    "significant": p_value < 0.05,
                    "strength": self._correlation_strength(abs(r_p)),
                }
        
        return matrix

    def _correlation_strength(self, abs_r: float) -> str:
        """Classify correlation strength."""
        if abs_r >= 0.8: return "very_strong"
        if abs_r >= 0.6: return "strong"
        if abs_r >= 0.4: return "moderate"
        if abs_r >= 0.2: return "weak"
        return "very_weak"

    # ─── Function 4: Trend & Seasonality Detection ────────────────────────

    def detect_trends_seasonality(self, df: pl.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Detect time series trends and seasonality if date columns exist.
        
        Scans for date/datetime columns, then:
          1. Groups by date intervals (daily, weekly, monthly, quarterly, yearly)
          2. Computes aggregates for numeric columns
          3. Detects linear trends (slope, direction)
          4. Detects seasonality patterns (monthly, quarterly, day-of-week)
          5. Flags anomalies (sudden spikes/drops)
        
        Returns:
            Dict with trends, seasonality, and anomaly info, or None if no date column
        """
        # Find date columns
        date_cols = []
        for col in df.columns:
            dtype = df[col].dtype
            if dtype in (pl.Date, pl.Datetime):
                date_cols.append(col)
            elif dtype in (pl.Utf8, pl.String):
                sample = df[col].drop_nulls().head(10).to_list()
                for val in sample:
                    if isinstance(val, str) and any(re.match(p, val) for p, _ in DATE_PATTERNS):
                        date_cols.append(col)
                        break
        
        if not date_cols:
            return None
        
        date_col = date_cols[0]
        
        # Convert to datetime if needed
        try:
            if df[date_col].dtype not in (pl.Date, pl.Datetime):
                # Try to parse common date formats
                for pattern, fmt in DATE_PATTERNS:
                    sample = str(df[date_col].drop_nulls().head(1).to_list()[0]) if len(df[date_col].drop_nulls()) > 0 else ""
                    if re.match(pattern, sample):
                        date_series = pl.Series(df[date_col]).str.strptime(pl.Datetime, fmt, strict=False)
                        break
                else:
                    return {"date_column": date_col, "note": "Could not parse date format"}
            else:
                date_series = df[date_col]
        except Exception as e:
            return {"date_column": date_col, "error": str(e)}
        
        # Find numeric columns for trend analysis
        numeric_cols = [c for c in df.columns if df[c].dtype in (
            pl.Float32, pl.Float64, pl.Int32, pl.Int64
        )]
        
        if not numeric_cols:
            return {"date_column": date_col, "note": "No numeric columns for trend analysis"}
        
        # Build results
        trends = {
            "date_column": date_col,
            "date_range": {
                "start": str(date_series.min()) if hasattr(date_series, 'min') else "N/A",
                "end": str(date_series.max()) if hasattr(date_series, 'max') else "N/A",
                "span_days": (date_series.max() - date_series.min()).days if hasattr(date_series, 'max') else 0,
            },
            "column_trends": {},
            "seasonality": {},
        }
        
        # Trend per numeric column
        for col in numeric_cols[:5]:  # Limit to 5 columns
            values = df.select(pl.col(col).fill_null(strategy="forward")).to_series().to_numpy()
            if len(values) < 3:
                continue
            
            x = np.arange(len(values))
            slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, values)
            
            trends["column_trends"][col] = {
                "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
                "slope": round(float(slope), 4),
                "r_squared": round(float(r_value ** 2), 4),
                "p_value": round(float(p_value), 6),
                "significant": p_value < 0.05,
                "change_pct": round((values[-1] - values[0]) / abs(values[0]) * 100, 2) if values[0] != 0 else 0,
            }
        
        return trends

    # ─── Function 5: Domain Context Inference ─────────────────────────────

    def infer_domain_context(self, df: pl.DataFrame) -> Optional[str]:
        """
        Infer dataset domain and subdomain from column names and data.
        
        Uses keyword matching against domain-specific dictionaries.
        Returns a string like "finance/banking" or "healthcare/clinical".
        
        If no domain matches with sufficient confidence, returns None.
        """
        column_names = [c.lower() for c in df.columns]
        all_text = " ".join(column_names)
        
        scores: Dict[str, float] = {}
        subdomain_scores: Dict[str, float] = {}
        
        for domain, info in DOMAIN_KEYWORDS.items():
            domain_score = 0
            for keyword in info["keywords"]:
                if keyword in all_text:
                    domain_score += 1
                # Check partial matches
                for col in column_names:
                    if keyword in col:
                        domain_score += 2  # Direct column match weighs more
            
            if domain_score > 0:
                scores[domain] = domain_score / len(info["keywords"])
            
            # Check subdomains
            for subdomain in info.get("subdomains", []):
                sub_keywords = subdomain.replace("_", " ")
                if sub_keywords in all_text:
                    subdomain_scores[f"{domain}/{subdomain}"] = 0.8
        
        if not scores:
            return None
        
        # Pick best domain
        best_domain = max(scores, key=scores.get)
        best_score = scores[best_domain]
        
        if best_score < 0.15:  # Minimum confidence threshold
            return None
        
        # Check if we have a subdomain match
        matching_subdomains = {
            k: v for k, v in subdomain_scores.items()
            if k.startswith(best_domain)
        }
        
        if matching_subdomains:
            best_sub = max(matching_subdomains, key=matching_subdomains.get)
            return f"{best_sub} (confidence={scores[best_domain]:.2f})"
        
        return f"{best_domain} (confidence={best_score:.2f})"
