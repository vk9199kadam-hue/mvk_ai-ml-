# =============================================================================
# AutoInsight AI — Load Testing (Phase 5, Day 47)
# Locust tests for 100 concurrent users, NLQ stress test
# =============================================================================
# Run with: locust -f tests/load/locustfile.py --host=http://localhost:8000
# Web UI: http://localhost:8089
# Headless: locust -f tests/load/locustfile.py --headless -u 100 -r 10 --run-time 5m
# =============================================================================

import json
import random
import time
from typing import Any, Dict, Optional

from locust import HttpUser, LoadTestShape, TaskSet, between, task, events
from locust.runners import MasterRunner, WorkerRunner


# ── Test Data ──────────────────────────────────────────────────────────────

SAMPLE_EMAILS = [
    "admin@autoinsight.com",
    "analyst@autoinsight.com",
    "viewer@autoinsight.com",
]

SAMPLE_PASSWORDS = ["password"]

NLQ_QUERIES = [
    "What are the key trends in this dataset?",
    "Show me the correlation between age and salary",
    "Which columns have the most missing values?",
    "What insights can you extract from this data?",
    "Create a summary dashboard layout",
    "Are there any anomalies I should investigate?",
    "What is the average value across all numeric columns?",
    "Show me the distribution of categories",
    "Find outliers in the dataset",
    "Generate a report summary",
    "What columns have the highest correlation?",
    "Show me trends over time",
    "What data quality issues exist?",
    "Recommend visualizations for this data",
    "Summarize the key statistical findings",
]

REPORT_FORMATS = ["html", "md", "pdf", "xlsx"]


# ── Event Handlers ─────────────────────────────────────────────────────────

@events.init_command_line_parser.add_listener
def init_parser(parser):
    """Add custom command line arguments."""
    parser.add_argument(
        "--nlq-only",
        action="store_true",
        help="Run only NLQ query tests",
        default=False,
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help="Run only authentication tests",
        default=False,
    )


# ── User Behavior: Anonymous ──────────────────────────────────────────────

class AnonymousUserBehavior(TaskSet):
    """Simulates unauthenticated user browsing public endpoints."""

    @task(3)
    def health_check(self):
        """Check system health."""
        with self.client.get(
            "/health",
            name="GET /health",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Health check failed: {response.status_code}")

    @task(2)
    def readiness_check(self):
        """Check system readiness."""
        self.client.get(
            "/health/ready",
            name="GET /health/ready",
        )

    @task(1)
    def system_info(self):
        """Get system configuration."""
        self.client.get(
            "/api/v1/system/info",
            name="GET /api/v1/system/info",
        )


# ── User Behavior: Authenticated ──────────────────────────────────────────

class AuthenticatedUserBehavior(TaskSet):
    """Simulates authenticated user performing various operations."""

    def on_start(self):
        """Login on start — acquire JWT token."""
        email = random.choice(SAMPLE_EMAILS)
        password = random.choice(SAMPLE_PASSWORDS)

        with self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            name="POST /api/v1/auth/login",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("data", {}).get("access_token", "")
                self.client.headers.update({
                    "Authorization": f"Bearer {self.token}"
                })
                self.logged_in = True
            else:
                self.logged_in = False
                response.failure(f"Login failed: {response.status_code}")

    @task(5)
    def nlq_query(self):
        """Execute NLQ query."""
        if not self.logged_in:
            return

        query = random.choice(NLQ_QUERIES)
        with self.client.post(
            "/api/v1/nlq/query",
            json={
                "query": query,
                "dataset_id": "default-dataset",
            },
            name="POST /api/v1/nlq/query",
            catch_response=True,
        ) as response:
            if response.status_code not in (200, 202):
                response.failure(f"NLQ query failed: {response.status_code}")

    @task(3)
    def get_report(self):
        """Get report status."""
        if not self.logged_in:
            return

        self.client.get(
            f"/api/v1/reports/{random.choice(['report-001', 'report-002', 'report-003'])}",
            name="GET /api/v1/reports/{id}",
        )

    @task(2)
    def dashboard(self):
        """Get dashboard."""
        if not self.logged_in:
            return

        self.client.get(
            f"/api/v1/dashboard/{random.choice(['dash-001', 'dash-002'])}",
            name="GET /api/v1/dashboard/{id}",
        )

    @task(2)
    def pipeline_status(self):
        """Check pipeline status."""
        if not self.logged_in:
            return

        self.client.get(
            f"/api/v1/pipeline/status/{random.choice(['pipe-001', 'pipe-002', 'pipe-003'])}",
            name="GET /api/v1/pipeline/status/{id}",
        )

    @task(1)
    def pipeline_diff(self):
        """Get pipeline cleaning diff."""
        if not self.logged_in:
            return

        self.client.get(
            f"/api/v1/pipeline/diff/{random.choice(['pipe-001', 'pipe-002'])}",
            name="GET /api/v1/pipeline/diff/{id}",
        )

    @task(1)
    def token_refresh(self):
        """Refresh JWT token."""
        if not self.logged_in:
            return

        self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": self.token},
            name="POST /api/v1/auth/refresh",
        )

    @task(1)
    def admin_list_users(self):
        """List users (admin only)."""
        if not self.logged_in:
            return

        self.client.get(
            "/api/v1/admin/users",
            name="GET /api/v1/admin/users",
        )


# ── User Behavior: NLQ Stress Test ────────────────────────────────────────

class NLQStressTestBehavior(TaskSet):
    """Heavy NLQ query load test — simulates repeated NLQ queries."""

    def on_start(self):
        """Login on start."""
        with self.client.post(
            "/api/v1/auth/login",
            json={"email": "analyst@autoinsight.com", "password": "password"},
            name="POST /api/v1/auth/login (NLQ stress)",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("data", {}).get("access_token", "")
                self.client.headers.update({
                    "Authorization": f"Bearer {self.token}"
                })

    @task(10)
    def nlq_query(self):
        """Execute NLQ query with high frequency."""
        query = random.choice(NLQ_QUERIES)
        self.client.post(
            "/api/v1/nlq/query",
            json={"query": query, "dataset_id": "stress-test-dataset"},
            name="POST /api/v1/nlq/query (stress)",
        )

    @task(1)
    def nlq_with_report(self):
        """NLQ query + report generation combo."""
        query = random.choice(NLQ_QUERIES)
        self.client.post(
            "/api/v1/nlq/query",
            json={
                "query": query,
                "dataset_id": "stress-test-dataset",
                "generate_report": True,
            },
            name="POST /api/v1/nlq/query + report",
        )


# ── User Classes ───────────────────────────────────────────────────────────

class AnonymousUser(HttpUser):
    """Simulates anonymous web traffic."""
    tasks = [AnonymousUserBehavior]
    wait_time = between(1, 5)
    weight = 2


class AuthenticatedUser(HttpUser):
    """Simulates regular authenticated user."""
    tasks = [AuthenticatedUserBehavior]
    wait_time = between(2, 8)
    weight = 5


class NLQStressUser(HttpUser):
    """Simulates heavy NLQ query user."""
    tasks = [NLQStressTestBehavior]
    wait_time = between(0.5, 2)
    weight = 3


# ── Load Test Shape ────────────────────────────────────────────────────────

class StepLoadShape(LoadTestShape):
    """Gradually increases load to find breaking point.
    
    Use with: locust -f tests/load/locustfile.py --shape StepLoadShape
    """
    """Gradually increases load to find breaking point.
    
    Stages:
      1. Warm-up: 10 users for 1 min
      2. Normal: 50 users for 2 min
      3. Peak: 100 users for 3 min
      4. Stress: 150 users for 2 min
      5. Cooldown: 25 users for 1 min
    """

    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 2},
        {"duration": 120, "users": 50, "spawn_rate": 5},
        {"duration": 180, "users": 100, "spawn_rate": 10},
        {"duration": 120, "users": 150, "spawn_rate": 15},
        {"duration": 60, "users": 25, "spawn_rate": 5},
    ]

    def tick(self):
        """Determine current stage."""
        running_time = self.get_running_time()

        for stage in self.stages:
            if running_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])

        return None
