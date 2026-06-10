# =============================================================================
# AutoInsight AI — NLQ Chat & Dashboard Package
# Phase 1: Foundation — NLQ Stubs
# =============================================================================
"""
Natural Language Query (NLQ) Chat & Dashboard Auto-Layout Package.

Stage 6 of the system — provides:
  - NLQ Chat: Natural language querying of datasets
  - Dashboard: Auto-generated interactive visualizations

Both run in parallel after Stage 4 completes the UnifiedDataModel.
"""

from backend.nlq.chat import NLQChat
from backend.nlq.dashboard import DashboardEngine

__all__ = ["NLQChat", "DashboardEngine"]
