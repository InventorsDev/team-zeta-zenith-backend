from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import csv
import io
import json

from app.database.connection import get_db
from app.services.analytics_service import AnalyticsService
from app.cache.cache_manager import CacheManager
from app.cache.redis_client import get_redis_client
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.analytics import (
    TimeGranularity,
    MetricType,
    ExportFormat,
    AggregationQuery,
    ExportRequest,
    AnalyticsFilter
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    """Dependency to get analytics service with cache"""
    redis_client = get_redis_client()
    cache_manager = CacheManager(redis_client) if redis_client else None
    return AnalyticsService(db, cache_manager)


@router.get("/time-series/{metric_type}")
async def get_time_series(
    metric_type: MetricType,
    start_date: datetime = Query(..., description="Start date for analysis"),
    end_date: datetime = Query(..., description="End date for analysis"),
    granularity: TimeGranularity = Query(TimeGranularity.DAILY, description="Time granularity"),
    status: Optional[List[str]] = Query(None, description="Filter by status"),
    priority: Optional[List[str]] = Query(None, description="Filter by priority"),
    channel: Optional[List[str]] = Query(None, description="Filter by channel"),
    category: Optional[List[str]] = Query(None, description="Filter by category"),
    use_cache: bool = Query(True, description="Use cached results"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Get time-series analytics data with multiple granularities"""

    filters = {}
    if status:
        filters["status"] = status
    if priority:
        filters["priority"] = priority
    if channel:
        filters["channel"] = channel
    if category:
        filters["category"] = category

    result = analytics_service.get_time_series(
        organization_id=current_user.organization_id,
        metric_type=metric_type.value,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity.value,
        filters=filters,
        use_cache=use_cache
    )

    return result


@router.post("/aggregations")
async def get_aggregations(
    query: AggregationQuery,
    use_cache: bool = Query(True, description="Use cached results"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Get complex aggregated analytics with grouping and filtering"""

    results = analytics_service.get_aggregation(
        query=query,
        organization_id=current_user.organization_id,
        use_cache=use_cache
    )

    return {
        "organization_id": current_user.organization_id,
        "query": query.dict(),
        "results": results,
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/dashboard")
async def get_dashboard_metrics(
    start_date: Optional[datetime] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (default: now)"),
    use_cache: bool = Query(True, description="Use cached results"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Get comprehensive dashboard metrics with trends"""

    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    metrics = analytics_service.get_dashboard_metrics(
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
        use_cache=use_cache
    )

    return metrics


@router.get("/performance")
async def get_performance_metrics(
    start_date: Optional[datetime] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[datetime] = Query(None, description="End date (default: now)"),
    use_cache: bool = Query(True, description="Use cached results"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Get performance metrics including percentiles and SLA compliance"""

    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    metrics = analytics_service.get_performance_metrics(
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
        use_cache=use_cache
    )

    return metrics


@router.get("/distribution/{field}")
async def get_distribution(
    field: str,
    start_date: datetime = Query(..., description="Start date for analysis"),
    end_date: datetime = Query(..., description="End date for analysis"),
    status: Optional[List[str]] = Query(None, description="Filter by status"),
    priority: Optional[List[str]] = Query(None, description="Filter by priority"),
    use_cache: bool = Query(True, description="Use cached results"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Get distribution of values for a specific field"""

    filters = {}
    if status:
        filters["status"] = status
    if priority:
        filters["priority"] = priority

    distribution = analytics_service.get_distribution(
        organization_id=current_user.organization_id,
        field=field,
        start_date=start_date,
        end_date=end_date,
        filters=filters,
        use_cache=use_cache
    )

    return {
        "field": field,
        "distribution": distribution,
        "total": sum(distribution.values()),
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    }


@router.post("/export")
async def export_analytics(
    export_request: ExportRequest,
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Export analytics data in CSV, JSON, or Excel format"""

    # Get the data
    export_data = analytics_service.export_data(
        organization_id=current_user.organization_id,
        metric_types=[mt.value for mt in export_request.metric_types],
        start_date=export_request.start_date,
        end_date=export_request.end_date,
        format=export_request.format.value,
        granularity=export_request.granularity.value,
        filters=export_request.filters
    )

    # Format based on requested format
    if export_request.format == ExportFormat.JSON:
        return JSONResponse(content=export_data)

    elif export_request.format == ExportFormat.CSV:
        # Convert to CSV
        output = io.StringIO()

        # Write header
        output.write(f"# Analytics Export\n")
        output.write(f"# Organization ID: {export_data['organization_id']}\n")
        output.write(f"# Export Date: {export_data['export_date']}\n")
        output.write(f"# Period: {export_data['period']['start']} to {export_data['period']['end']}\n")
        output.write(f"# Granularity: {export_data['granularity']}\n\n")

        # Write data for each metric
        for metric_type, data_points in export_data['metrics'].items():
            output.write(f"\n# Metric: {metric_type}\n")

            if data_points:
                writer = csv.DictWriter(output, fieldnames=['timestamp', 'value', 'count'])
                writer.writeheader()
                for point in data_points:
                    writer.writerow({
                        'timestamp': point['timestamp'],
                        'value': point['value'],
                        'count': point.get('count', '')
                    })

        # Create streaming response
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=analytics_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )

    elif export_request.format == ExportFormat.EXCEL:
        # For Excel, we'll return JSON with a note (requires openpyxl library)
        return JSONResponse(
            content={
                "message": "Excel export requires openpyxl library. Returning JSON format.",
                "data": export_data
            }
        )


@router.delete("/cache")
async def invalidate_cache(
    pattern: Optional[str] = Query(None, description="Cache pattern to invalidate"),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Invalidate analytics cache for the organization"""

    analytics_service.invalidate_cache(
        organization_id=current_user.organization_id,
        pattern=pattern
    )

    return {
        "message": "Cache invalidated successfully",
        "organization_id": current_user.organization_id,
        "pattern": pattern or "all analytics data"
    }


@router.post("/refresh-cache")
async def refresh_cache(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Refresh analytics cache in the background"""

    def refresh_all_caches():
        """Background task to refresh caches"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        # Refresh dashboard metrics
        analytics_service.get_dashboard_metrics(
            organization_id=current_user.organization_id,
            start_date=start_date,
            end_date=end_date,
            use_cache=False
        )

        # Refresh performance metrics
        analytics_service.get_performance_metrics(
            organization_id=current_user.organization_id,
            start_date=start_date,
            end_date=end_date,
            use_cache=False
        )

        # Refresh common distributions
        for field in ['status', 'priority', 'channel', 'category']:
            analytics_service.get_distribution(
                organization_id=current_user.organization_id,
                field=field,
                start_date=start_date,
                end_date=end_date,
                use_cache=False
            )

    background_tasks.add_task(refresh_all_caches)

    return {
        "message": "Cache refresh initiated in background",
        "organization_id": current_user.organization_id
    }


# Legacy endpoints (for backward compatibility)
@router.get("/overview")
async def get_analytics_overview(
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Get comprehensive analytics overview (legacy endpoint)"""

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    metrics = analytics_service.get_dashboard_metrics(
        organization_id=current_user.organization_id,
        start_date=start_date,
        end_date=end_date,
        use_cache=True
    )

    return {
        "basic_stats": metrics.dict(),
        "generated_at": datetime.utcnow().isoformat()
    }
