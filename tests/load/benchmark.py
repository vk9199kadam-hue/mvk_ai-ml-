# =============================================================================
# AutoInsight AI — Performance Benchmark Script (Phase 5, Day 45)
# Run: python tests/load/benchmark.py
# Measures: dashboard load times, API latency, cache effectiveness
# =============================================================================

import asyncio
import json
import logging
import time
from datetime import datetime
from statistics import median, stdev
from typing import Any, Dict, List

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"
NUM_REQUESTS = 50  # Sample size per endpoint
CONCURRENCY = 10   # Parallel requests


# ── Benchmark Results ─────────────────────────────────────────────────────

class BenchmarkResult:
    def __init__(self, name: str):
        self.name = name
        self.times: List[float] = []
        self.status_codes: List[int] = []
        self.errors: List[str] = []

    def add(self, elapsed: float, status: int, error: str = ""):
        self.times.append(elapsed)
        self.status_codes.append(status)
        if error:
            self.errors.append(error)

    @property
    def avg_ms(self) -> float:
        return sum(self.times) / len(self.times) * 1000 if self.times else 0

    @property
    def median_ms(self) -> float:
        return median(self.times) * 1000 if self.times else 0

    @property
    def p95_ms(self) -> float:
        if not self.times:
            return 0
        sorted_times = sorted(self.times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx] * 1000

    @property
    def p99_ms(self) -> float:
        if not self.times:
            return 0
        sorted_times = sorted(self.times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[idx] * 1000

    @property
    def min_ms(self) -> float:
        return min(self.times) * 1000 if self.times else 0

    @property
    def max_ms(self) -> float:
        return max(self.times) * 1000 if self.times else 0

    @property
    def success_rate(self) -> float:
        if not self.status_codes:
            return 0
        success = sum(1 for s in self.status_codes if s < 500)
        return success / len(self.status_codes) * 100

    @property
    def std_dev_ms(self) -> float:
        return stdev(self.times) * 1000 if len(self.times) > 1 else 0

    def summary(self) -> Dict[str, Any]:
        return {
            "endpoint": self.name,
            "samples": len(self.times),
            "avg_ms": round(self.avg_ms, 2),
            "median_ms": round(self.median_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "std_dev_ms": round(self.std_dev_ms, 2),
            "success_rate": round(self.success_rate, 1),
            "errors": len(self.errors),
        }


# ── Benchmark Runner ──────────────────────────────────────────────────────

async def benchmark_endpoint(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    name: str,
    json_data: Any = None,
    num_requests: int = NUM_REQUESTS,
) -> BenchmarkResult:
    """Benchmark a single endpoint with multiple requests."""
    result = BenchmarkResult(name)

    async def single_request():
        start = time.perf_counter()
        try:
            if method == "GET":
                response = await client.get(url)
            elif method == "POST":
                response = await client.post(url, json=json_data)
            elapsed = time.perf_counter() - start
            result.add(elapsed, response.status_code)
        except Exception as e:
            elapsed = time.perf_counter() - start
            result.add(elapsed, 0, str(e))

    # Run requests concurrently
    tasks = [single_request() for _ in range(num_requests)]
    await asyncio.gather(*tasks)

    return result


# ── Cache Benchmark ───────────────────────────────────────────────────────

async def benchmark_cache_effectiveness(
    client: httpx.AsyncClient,
    url: str,
    name: str,
    num_requests: int = 20,
) -> Dict[str, Any]:
    """Benchmark cache effectiveness by measuring first vs subsequent requests."""
    uncached = BenchmarkResult(f"{name} (uncached)")
    cached = BenchmarkResult(f"{name} (cached)")

    # First request (cold cache)
    start = time.perf_counter()
    response = await client.get(url)
    uncached.add(time.perf_counter() - start, response.status_code)

    # Wait a bit then measure cached
    time.sleep(0.1)
    for _ in range(num_requests):
        start = time.perf_counter()
        response = await client.get(url)
        cached.add(time.perf_counter() - start, response.status_code)

    return {
        "endpoint": name,
        "uncached_ms": round(uncached.avg_ms, 2),
        "cached_avg_ms": round(cached.avg_ms, 2),
        "improvement_pct": round(
            (1 - cached.avg_ms / uncached.avg_ms) * 100 if uncached.avg_ms > 0 else 0,
            1,
        ),
        "cached_samples": num_requests,
    }


# ── Main Benchmark ─────────────────────────────────────────────────────────

async def run_benchmarks():
    """Run all performance benchmarks and print results."""
    logger.info("=" * 60)
    logger.info("AutoInsight AI — Performance Benchmark")
    logger.info(f"Base URL: {BASE_URL}")
    logger.info(f"Requests per endpoint: {NUM_REQUESTS}")
    logger.info(f"Concurrency: {CONCURRENCY}")
    logger.info("=" * 60)

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=30.0,
        limits=httpx.Limits(max_connections=CONCURRENCY),
    ) as client:

        results = []

        # 1. Health endpoint
        logger.info("\n📡 Benchmarking health endpoints...")
        results.append(await benchmark_endpoint(
            client, "GET", "/health", "GET /health"
        ))
        results.append(await benchmark_endpoint(
            client, "GET", "/health/ready", "GET /health/ready"
        ))

        # 2. System info
        logger.info("📡 Benchmarking system info...")
        results.append(await benchmark_endpoint(
            client, "GET", "/api/v1/system/info", "GET /api/v1/system/info"
        ))

        # 3. Auth endpoints
        logger.info("📡 Benchmarking auth endpoints...")
        results.append(await benchmark_endpoint(
            client, "POST", "/api/v1/auth/login",
            "POST /api/v1/auth/login",
            json_data={"email": "admin@autoinsight.com", "password": "password"},
            num_requests=20,
        ))

        # 4. NLQ query
        logger.info("📡 Benchmarking NLQ query...")
        results.append(await benchmark_endpoint(
            client, "POST", "/api/v1/nlq/query",
            "POST /api/v1/nlq/query",
            json_data={
                "query": "What are the key trends in this dataset?",
                "dataset_id": "default-dataset",
            },
        ))

        # 5. Pipeline status
        logger.info("📡 Benchmarking pipeline endpoints...")
        results.append(await benchmark_endpoint(
            client, "GET", "/api/v1/pipeline/status/test-001",
            "GET /api/v1/pipeline/status/{id}",
        ))

        # 6. Report endpoints
        logger.info("📡 Benchmarking report endpoints...")
        results.append(await benchmark_endpoint(
            client, "GET", "/api/v1/reports/test-report",
            "GET /api/v1/reports/{id}",
        ))

        # 7. Dashboard
        logger.info("📡 Benchmarking dashboard...")
        results.append(await benchmark_endpoint(
            client, "GET", "/api/v1/dashboard/test-dash",
            "GET /api/v1/dashboard/{id}",
        ))

        # 8. Admin
        logger.info("📡 Benchmarking admin endpoints...")
        results.append(await benchmark_endpoint(
            client, "GET", "/api/v1/admin/users",
            "GET /api/v1/admin/users",
        ))

        # ── Print Results ───────────────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info("BENCHMARK RESULTS")
        logger.info("=" * 60)
        logger.info(
            f"{'Endpoint':<40} {'Avg(ms)':<10} {'P95(ms)':<10} "
            f"{'P99(ms)':<10} {'Min(ms)':<10} {'Max(ms)':<10} {'OK%':<8}"
        )
        logger.info("-" * 98)

        all_pass = True
        for r in results:
            s = r.summary()
            logger.info(
                f"{s['endpoint']:<40} {s['avg_ms']:<10.1f} {s['p95_ms']:<10.1f} "
                f"{s['p99_ms']:<10.1f} {s['min_ms']:<10.1f} {s['max_ms']:<10.1f} "
                f"{s['success_rate']:<7.1f}%"
            )
            if s['avg_ms'] > 3000:  # Dashboard target: <3s
                logger.warning(f"  ⚠ Endpoint exceeds 3s target: {s['avg_ms']:.0f}ms")
                all_pass = False

        # ── Dashboard Load Test ──────────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info("DASHBOARD LOAD TEST (<3s target)")
        logger.info("=" * 60)
        dash_result = await benchmark_endpoint(
            client, "GET", "/api/v1/dashboard/test-dash",
            "GET /api/v1/dashboard/{id} (LOAD TEST)",
            num_requests=100,
        )
        dash = dash_result.summary()
        logger.info(
            f"Dashboard P95: {dash['p95_ms']:.1f}ms — "
            f"{'✅ PASS (<3000ms)' if dash['p95_ms'] < 3000 else '❌ FAIL (>3000ms)'}"
        )

        # ── Cache Effectiveness ──────────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info("CACHE EFFECTIVENESS")
        logger.info("=" * 60)
        cache_result = await benchmark_cache_effectiveness(
            client, "/api/v1/system/info", "GET /api/v1/system/info"
        )
        logger.info(
            f"{cache_result['endpoint']}: "
            f"Uncached={cache_result['uncached_ms']}ms → "
            f"Cached={cache_result['cached_avg_ms']}ms "
            f"({cache_result['improvement_pct']}% improvement)"
        )

        # ── Summary ──────────────────────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info("OVERALL VERDICT")
        logger.info("=" * 60)
        if all_pass:
            logger.info("✅ ALL ENDPOINTS PASS — <3s dashboard load target met")
        else:
            logger.info("⚠ SOME ENDPOINTS EXCEED 3s — review warnings above")

        total_time = sum(r.avg_ms * len(r.times) for r in results)
        total_requests = sum(len(r.times) for r in results)
        logger.info(
            f"Total requests: {total_requests} | "
            f"Total time: {total_time/1000:.1f}s"
        )


# ── Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(run_benchmarks())
