from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum


class TimeGranularity(str, Enum):
    """Time granularity options"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class MetricType(str, Enum):
    """Available metric types"""
    TICKET_COUNT = "ticket_count"
    TICKET_VOLUME = "ticket_volume"  # Alias for ticket_count
    RESPONSE_TIME = "response_time"
    RESOLUTION_TIME = "resolution_time"
    SENTIMENT_SCORE = "sentiment_score"
    AVG_SENTIMENT = "avg_sentiment"  # Alias for sentiment_score
    CATEGORY_DISTRIBUTION = "category_distribution"
    CHANNEL_DISTRIBUTION = "channel_distribution"
    PRIORITY_DISTRIBUTION = "priority_distribution"
    STATUS_DISTRIBUTION = "status_distribution"


class ExportFormat(str, Enum):
    """Export format options"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


class TimeSeriesDataPoint(BaseModel):
    """Single data point in time series"""
    timestamp: datetime
    value: float
    count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = {}


class TimeSeriesResponse(BaseModel):
    """Time series analytics response"""
    metric_type: str
    granularity: TimeGranularity
    start_date: datetime
    end_date: datetime
    data_points: List[TimeSeriesDataPoint]
    total_count: int
    average_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class AggregationQuery(BaseModel):
    """Query parameters for aggregation"""
    metric_types: List[MetricType]
    start_date: datetime
    end_date: datetime
    granularity: TimeGranularity = TimeGranularity.DAILY
    filters: Optional[Dict[str, Any]] = {}
    group_by: Optional[List[str]] = []


class AggregationResult(BaseModel):
    """Result of aggregation query"""
    metric_type: str
    granularity: TimeGranularity
    total_count: int
    sum_value: Optional[float] = None
    avg_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    breakdown: Optional[Dict[str, Any]] = {}
    time_series: Optional[List[TimeSeriesDataPoint]] = []


class AnalyticsOverview(BaseModel):
    """Comprehensive analytics overview"""
    organization_id: int
    period_start: datetime
    period_end: datetime
    metrics: Dict[str, AggregationResult]
    generated_at: datetime


class ExportRequest(BaseModel):
    """Request for data export"""
    metric_types: List[MetricType]
    start_date: datetime
    end_date: datetime
    format: ExportFormat = ExportFormat.JSON
    granularity: TimeGranularity = TimeGranularity.DAILY
    filters: Optional[Dict[str, Any]] = {}
    include_raw_data: bool = False


class RealTimeMetric(BaseModel):
    """Real-time metric update"""
    metric_type: str
    value: float
    timestamp: datetime
    organization_id: int
    metadata: Optional[Dict[str, Any]] = {}


class DashboardMetrics(BaseModel):
    """Dashboard summary metrics"""
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    avg_response_time_hours: Optional[float] = None
    avg_resolution_time_hours: Optional[float] = None
    sentiment_breakdown: Dict[str, int]
    category_breakdown: Dict[str, int]
    channel_breakdown: Dict[str, int]
    priority_breakdown: Dict[str, int]
    trend_data: Optional[Dict[str, List[TimeSeriesDataPoint]]] = {}


class PerformanceMetrics(BaseModel):
    """System performance metrics"""
    response_time_p50: Optional[float] = None
    response_time_p95: Optional[float] = None
    response_time_p99: Optional[float] = None
    resolution_time_p50: Optional[float] = None
    resolution_time_p95: Optional[float] = None
    resolution_time_p99: Optional[float] = None
    sla_compliance_rate: Optional[float] = None


class AnalyticsFilter(BaseModel):
    """Filter parameters for analytics queries"""
    status: Optional[List[str]] = None
    priority: Optional[List[str]] = None
    channel: Optional[List[str]] = None
    category: Optional[List[str]] = None
    assigned_to: Optional[int] = None
    date_field: str = "created_at"  # created_at, resolved_at, closed_at
