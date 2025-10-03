from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base
from enum import Enum


class MetricType(str, Enum):
    """Types of metrics tracked"""
    TICKET_COUNT = "ticket_count"
    RESPONSE_TIME = "response_time"
    RESOLUTION_TIME = "resolution_time"
    SENTIMENT_SCORE = "sentiment_score"
    CATEGORY_DISTRIBUTION = "category_distribution"
    CHANNEL_DISTRIBUTION = "channel_distribution"
    PRIORITY_DISTRIBUTION = "priority_distribution"
    STATUS_DISTRIBUTION = "status_distribution"


class TimeGranularity(str, Enum):
    """Time granularity for analytics"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class AnalyticsMetric(Base):
    """Time-series analytics metrics storage"""

    __tablename__ = "analytics_metrics"

    # Relationships
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    organization = relationship("Organization")

    # Metric information
    metric_type = Column(String(100), nullable=False, index=True)
    granularity = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Metric values
    value = Column(Float, nullable=True)
    count = Column(Integer, nullable=True)
    metric_metadata = Column(JSON, nullable=True, default=dict)

    # Aggregated data
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    avg_value = Column(Float, nullable=True)
    sum_value = Column(Float, nullable=True)

    # Dimensional breakdowns (stored as JSON)
    breakdown = Column(JSON, nullable=True, default=dict)

    def __repr__(self):
        return f"<AnalyticsMetric(type='{self.metric_type}', granularity='{self.granularity}', timestamp='{self.timestamp}')>"


class AnalyticsSnapshot(Base):
    """Periodic snapshots of analytics data for faster querying"""

    __tablename__ = "analytics_snapshots"

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    organization = relationship("Organization")

    snapshot_type = Column(String(100), nullable=False)
    snapshot_date = Column(DateTime, nullable=False, index=True)

    # Snapshot data (comprehensive JSON)
    data = Column(JSON, nullable=False)

    # Metadata
    generated_at = Column(DateTime, default=datetime.utcnow)
    is_complete = Column(Integer, default=1)  # Boolean flag

    def __repr__(self):
        return f"<AnalyticsSnapshot(type='{self.snapshot_type}', date='{self.snapshot_date}')>"
