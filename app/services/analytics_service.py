from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import json
import hashlib

from app.database.repositories.analytics_repository import AnalyticsRepository
from app.cache.cache_manager import CacheManager
from app.schemas.analytics import (
    TimeSeriesDataPoint,
    TimeSeriesResponse,
    AggregationQuery,
    AggregationResult,
    DashboardMetrics,
    PerformanceMetrics,
    TimeGranularity,
    MetricType
)


class AnalyticsService:
    """Service for analytics with caching support"""

    def __init__(self, db: Session, cache_manager: CacheManager = None):
        self.db = db
        self.repository = AnalyticsRepository(db)
        self.cache_manager = cache_manager
        self.default_cache_ttl = 3600  # 1 hour

    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate a cache key from parameters"""
        key_data = f"{prefix}:" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cached_or_compute(self, cache_key: str, compute_func, ttl: int = None):
        """Get from cache or compute and cache"""
        if self.cache_manager:
            cached = self.cache_manager.get(cache_key)
            if cached:
                return json.loads(cached)

        result = compute_func()

        if self.cache_manager:
            self.cache_manager.set(
                cache_key,
                json.dumps(result, default=str),
                ttl or self.default_cache_ttl
            )

        return result

    def get_time_series(
        self,
        organization_id: int,
        metric_type: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "daily",
        filters: Dict[str, Any] = None,
        use_cache: bool = True
    ) -> TimeSeriesResponse:
        """Get time-series analytics with caching"""

        cache_key = self._generate_cache_key(
            "time_series",
            org=organization_id,
            metric=metric_type,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            gran=granularity,
            filters=json.dumps(filters or {})
        )

        def compute():
            data_points = self.repository.get_time_series(
                organization_id=organization_id,
                metric_type=metric_type,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                filters=filters
            )

            # Calculate statistics
            values = [dp.value for dp in data_points]
            total_count = sum(dp.count or 0 for dp in data_points)

            return {
                "metric_type": metric_type,
                "granularity": granularity,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "data_points": [dp.dict() for dp in data_points],
                "total_count": total_count,
                "average_value": sum(values) / len(values) if values else 0,
                "min_value": min(values) if values else 0,
                "max_value": max(values) if values else 0
            }

        if use_cache:
            result = self._get_cached_or_compute(cache_key, compute)
        else:
            result = compute()

        return TimeSeriesResponse(**result)

    def get_aggregation(
        self,
        query: AggregationQuery,
        organization_id: int,
        use_cache: bool = True
    ) -> List[AggregationResult]:
        """Get aggregated metrics with caching"""

        results = []

        for metric_type in query.metric_types:
            cache_key = self._generate_cache_key(
                "aggregation",
                org=organization_id,
                metric=metric_type.value,
                start=query.start_date.isoformat(),
                end=query.end_date.isoformat(),
                gran=query.granularity.value,
                filters=json.dumps(query.filters or {}),
                group_by=json.dumps(query.group_by or [])
            )

            def compute():
                # Get aggregation
                agg = self.repository.get_aggregation(
                    organization_id=organization_id,
                    metric_type=metric_type.value,
                    start_date=query.start_date,
                    end_date=query.end_date,
                    filters=query.filters,
                    group_by=query.group_by
                )

                # Get time series if needed
                time_series = []
                if query.granularity:
                    time_series_data = self.repository.get_time_series(
                        organization_id=organization_id,
                        metric_type=metric_type.value,
                        start_date=query.start_date,
                        end_date=query.end_date,
                        granularity=query.granularity.value,
                        filters=query.filters
                    )
                    time_series = [dp.dict() for dp in time_series_data]

                return {
                    "metric_type": metric_type.value,
                    "granularity": query.granularity.value,
                    "total_count": agg.get("total_count", 0),
                    "sum_value": agg.get("sum_value"),
                    "avg_value": agg.get("avg_value"),
                    "min_value": agg.get("min_value"),
                    "max_value": agg.get("max_value"),
                    "breakdown": agg.get("breakdown", {}),
                    "time_series": time_series
                }

            if use_cache:
                result = self._get_cached_or_compute(cache_key, compute)
            else:
                result = compute()

            results.append(AggregationResult(**result))

        return results

    def get_dashboard_metrics(
        self,
        organization_id: int,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> DashboardMetrics:
        """Get dashboard metrics with caching"""

        cache_key = self._generate_cache_key(
            "dashboard",
            org=organization_id,
            start=start_date.isoformat(),
            end=end_date.isoformat()
        )

        def compute():
            metrics = self.repository.get_dashboard_metrics(
                organization_id=organization_id,
                start_date=start_date,
                end_date=end_date
            )

            # Get trend data for the last 30 days
            trend_start = end_date - timedelta(days=30)
            trend_data = {}

            for metric_type in ["ticket_count", "response_time", "resolution_time"]:
                series = self.repository.get_time_series(
                    organization_id=organization_id,
                    metric_type=metric_type,
                    start_date=trend_start,
                    end_date=end_date,
                    granularity="daily"
                )
                trend_data[metric_type] = [dp.dict() for dp in series]

            metrics["trend_data"] = trend_data
            return metrics

        if use_cache:
            result = self._get_cached_or_compute(cache_key, compute)
        else:
            result = compute()

        return DashboardMetrics(**result)

    def get_performance_metrics(
        self,
        organization_id: int,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True
    ) -> PerformanceMetrics:
        """Get performance metrics (percentiles) with caching"""

        cache_key = self._generate_cache_key(
            "performance",
            org=organization_id,
            start=start_date.isoformat(),
            end=end_date.isoformat()
        )

        def compute():
            response_percentiles = self.repository.get_percentiles(
                organization_id=organization_id,
                metric_type="response_time",
                start_date=start_date,
                end_date=end_date,
                percentiles=[50, 95, 99]
            )

            resolution_percentiles = self.repository.get_percentiles(
                organization_id=organization_id,
                metric_type="resolution_time",
                start_date=start_date,
                end_date=end_date,
                percentiles=[50, 95, 99]
            )

            return {
                "response_time_p50": response_percentiles.get("p50"),
                "response_time_p95": response_percentiles.get("p95"),
                "response_time_p99": response_percentiles.get("p99"),
                "resolution_time_p50": resolution_percentiles.get("p50"),
                "resolution_time_p95": resolution_percentiles.get("p95"),
                "resolution_time_p99": resolution_percentiles.get("p99"),
                "sla_compliance_rate": None  # To be implemented based on SLA rules
            }

        if use_cache:
            result = self._get_cached_or_compute(cache_key, compute)
        else:
            result = compute()

        return PerformanceMetrics(**result)

    def get_distribution(
        self,
        organization_id: int,
        field: str,
        start_date: datetime,
        end_date: datetime,
        filters: Dict[str, Any] = None,
        use_cache: bool = True
    ) -> Dict[str, int]:
        """Get field distribution with caching"""

        cache_key = self._generate_cache_key(
            "distribution",
            org=organization_id,
            field=field,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            filters=json.dumps(filters or {})
        )

        def compute():
            return self.repository.get_distribution(
                organization_id=organization_id,
                field=field,
                start_date=start_date,
                end_date=end_date,
                filters=filters
            )

        if use_cache:
            return self._get_cached_or_compute(cache_key, compute)
        else:
            return compute()

    def invalidate_cache(self, organization_id: int, pattern: str = None):
        """Invalidate analytics cache"""
        if self.cache_manager:
            if pattern:
                # Invalidate specific pattern
                self.cache_manager.delete_pattern(f"*{pattern}*")
            else:
                # Invalidate all analytics cache for org
                patterns = [
                    f"*org={organization_id}*",
                    f"time_series*{organization_id}*",
                    f"aggregation*{organization_id}*",
                    f"dashboard*{organization_id}*",
                    f"performance*{organization_id}*",
                    f"distribution*{organization_id}*"
                ]
                for p in patterns:
                    self.cache_manager.delete_pattern(p)

    def export_data(
        self,
        organization_id: int,
        metric_types: List[str],
        start_date: datetime,
        end_date: datetime,
        format: str = "json",
        granularity: str = "daily",
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Export analytics data (to be used by export endpoints)"""

        export_data = {
            "organization_id": organization_id,
            "export_date": datetime.utcnow().isoformat(),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "granularity": granularity,
            "metrics": {}
        }

        for metric_type in metric_types:
            series = self.repository.get_time_series(
                organization_id=organization_id,
                metric_type=metric_type,
                start_date=start_date,
                end_date=end_date,
                granularity=granularity,
                filters=filters
            )

            export_data["metrics"][metric_type] = [
                {
                    "timestamp": dp.timestamp.isoformat(),
                    "value": dp.value,
                    "count": dp.count,
                    "metadata": dp.metadata
                }
                for dp in series
            ]

        return export_data
