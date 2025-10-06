"""
Performance Monitoring Middleware - Tracks API endpoint performance
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor and log API endpoint performance

    Features:
    - Tracks response times for all endpoints
    - Logs slow endpoints (>200ms)
    - Maintains rolling statistics (95th percentile, avg, max)
    - Alerts on performance degradation
    """

    def __init__(
        self,
        app,
        slow_threshold_ms: float = 200,
        very_slow_threshold_ms: float = 1000,
        stats_window_size: int = 1000,
    ):
        """
        Initialize performance monitoring

        Args:
            app: FastAPI application
            slow_threshold_ms: Log warning if response time exceeds this (ms)
            very_slow_threshold_ms: Log error if response time exceeds this (ms)
            stats_window_size: Number of requests to keep for statistics
        """
        super().__init__(app)
        self.slow_threshold = slow_threshold_ms / 1000  # Convert to seconds
        self.very_slow_threshold = very_slow_threshold_ms / 1000
        self.stats_window_size = stats_window_size

        # Store response times per endpoint (rolling window)
        self.endpoint_times: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=stats_window_size)
        )

        # Last stats log time per endpoint
        self.last_stats_log: dict[str, datetime] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance"""
        # Skip health check and docs
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time
        duration_ms = duration * 1000

        # Endpoint identifier
        endpoint = f"{request.method} {request.url.path}"

        # Store timing data
        self.endpoint_times[endpoint].append(duration)

        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Log slow requests
        if duration > self.very_slow_threshold:
            logger.error(
                f"Very slow endpoint: {endpoint} took {duration_ms:.2f}ms "
                f"(threshold: {self.very_slow_threshold*1000}ms)"
            )
            self._log_endpoint_stats(endpoint)

        elif duration > self.slow_threshold:
            logger.warning(
                f"Slow endpoint: {endpoint} took {duration_ms:.2f}ms "
                f"(threshold: {self.slow_threshold*1000}ms)"
            )

        # Periodically log statistics (every 100 requests per endpoint)
        if len(self.endpoint_times[endpoint]) % 100 == 0:
            self._log_endpoint_stats(endpoint)

        return response

    def _log_endpoint_stats(self, endpoint: str):
        """Log performance statistics for an endpoint"""
        times = list(self.endpoint_times[endpoint])
        if not times:
            return

        # Skip if logged recently (within last 5 minutes)
        last_log = self.last_stats_log.get(endpoint)
        if last_log and datetime.now() - last_log < timedelta(minutes=5):
            return

        times_ms = [t * 1000 for t in times]
        times_sorted = sorted(times_ms)

        count = len(times_ms)
        avg = sum(times_ms) / count
        min_time = times_sorted[0]
        max_time = times_sorted[-1]

        # Calculate percentiles
        p50_idx = int(count * 0.50)
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)

        p50 = times_sorted[p50_idx] if p50_idx < count else times_sorted[-1]
        p95 = times_sorted[p95_idx] if p95_idx < count else times_sorted[-1]
        p99 = times_sorted[p99_idx] if p99_idx < count else times_sorted[-1]

        logger.info(
            f"Performance stats for {endpoint} (n={count}):\n"
            f"  Min: {min_time:.2f}ms\n"
            f"  Avg: {avg:.2f}ms\n"
            f"  Max: {max_time:.2f}ms\n"
            f"  P50: {p50:.2f}ms\n"
            f"  P95: {p95:.2f}ms\n"
            f"  P99: {p99:.2f}ms"
        )

        # Alert if P95 exceeds threshold
        if p95 > self.slow_threshold * 1000:
            logger.warning(
                f"Performance alert: {endpoint} P95 latency ({p95:.2f}ms) "
                f"exceeds threshold ({self.slow_threshold*1000}ms)"
            )

        self.last_stats_log[endpoint] = datetime.now()

    def get_stats(self) -> dict:
        """Get current performance statistics"""
        stats = {}
        for endpoint, times in self.endpoint_times.items():
            if not times:
                continue

            times_ms = [t * 1000 for t in times]
            times_sorted = sorted(times_ms)
            count = len(times_ms)

            p95_idx = int(count * 0.95)
            stats[endpoint] = {
                "count": count,
                "avg_ms": sum(times_ms) / count,
                "min_ms": times_sorted[0],
                "max_ms": times_sorted[-1],
                "p95_ms": times_sorted[p95_idx] if p95_idx < count else times_sorted[-1],
            }

        return stats


# Singleton instance for accessing stats
_performance_monitor = None


def get_performance_monitor() -> PerformanceMonitoringMiddleware:
    """Get the global performance monitor instance"""
    global _performance_monitor
    return _performance_monitor


def set_performance_monitor(monitor: PerformanceMonitoringMiddleware):
    """Set the global performance monitor instance"""
    global _performance_monitor
    _performance_monitor = monitor
