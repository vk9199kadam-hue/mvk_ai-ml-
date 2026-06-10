# =============================================================================
# AutoInsight AI — Test Suite Package
# Phase 1: Foundation — Unit Tests
# =============================================================================
"""
Test suite for AutoInsight AI.

Test coverage targets:
  - schemas.py: 100% (all Pydantic models)
  - tools.py: 90% (all deterministic functions)
  - auth.py: 90% (JWT + password + RBAC)
  - Overall: 80%+

Test types:
  - unit: Individual function/class tests (pytest)
  - integration: Multi-module tests (pytest + httpx)
  - e2e: Full pipeline tests (Phase 2+)
"""
