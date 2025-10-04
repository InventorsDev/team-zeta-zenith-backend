from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case, extract, text
from datetime import datetime, timedelta
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketChannel
from app.models.analytics import AnalyticsMetric, AnalyticsSnapshot, TimeGranularity, MetricType
from app.schemas.analytics import TimeSeriesDataPoint
from app.core.config import get_settings
from .base_repository import BaseRepository


class AnalyticsRepository(BaseRepository):
    """Repository for analytics data with complex aggregations"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.is_sqlite = "sqlite" in self.settings.database_url_complete

    # Time-series queries
    def get_time_series(
        self,
        organization_id: int,
        metric_type: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "daily",
        filters: Dict[str, Any] = None
    ) -> List[TimeSeriesDataPoint]:
        """Get time-series data with specified granularity"""

        # Build base query
        query = self.db.query(Ticket).filter(
            Ticket.organization_id == organization_id,
            Ticket.created_at >= start_date,
            Ticket.created_at <= end_date
        )

        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)

        # Define time grouping based on granularity
        date_trunc = self._get_date_trunc_expression(granularity)

        if metric_type == "ticket_count":
            results = (
                query.with_entities(
                    date_trunc.label('timestamp'),
                    func.count(Ticket.id).label('count')
                )
                .group_by('timestamp')
                .order_by('timestamp')
                .all()
            )
            return [
                TimeSeriesDataPoint(
                    timestamp=r.timestamp,
                    value=float(r.count),
                    count=r.count
                )
                for r in results
            ]

        elif metric_type == "response_time":
            results = (
                query.filter(Ticket.first_response_at.isnot(None))
                .with_entities(
                    date_trunc.label('timestamp'),
                    func.avg(
                        self._get_time_diff_hours(Ticket.first_response_at, Ticket.created_at)
                    ).label('avg_hours'),
                    func.count(Ticket.id).label('count')
                )
                .group_by('timestamp')
                .order_by('timestamp')
                .all()
            )
            return [
                TimeSeriesDataPoint(
                    timestamp=r.timestamp,
                    value=float(r.avg_hours or 0),
                    count=r.count
                )
                for r in results
            ]

        elif metric_type == "resolution_time":
            results = (
                query.filter(Ticket.resolved_at.isnot(None))
                .with_entities(
                    date_trunc.label('timestamp'),
                    func.avg(
                        self._get_time_diff_hours(Ticket.resolved_at, Ticket.created_at)
                    ).label('avg_hours'),
                    func.count(Ticket.id).label('count')
                )
                .group_by('timestamp')
                .order_by('timestamp')
                .all()
            )
            return [
                TimeSeriesDataPoint(
                    timestamp=r.timestamp,
                    value=float(r.avg_hours or 0),
                    count=r.count
                )
                for r in results
            ]

        elif metric_type == "sentiment_score":
            results = (
                query.filter(Ticket.sentiment_score.isnot(None))
                .with_entities(
                    date_trunc.label('timestamp'),
                    func.avg(Ticket.sentiment_score).label('avg_sentiment'),
                    func.count(Ticket.id).label('count')
                )
                .group_by('timestamp')
                .order_by('timestamp')
                .all()
            )
            return [
                TimeSeriesDataPoint(
                    timestamp=r.timestamp,
                    value=float(r.avg_sentiment or 0),
                    count=r.count
                )
                for r in results
            ]

        return []

    def get_aggregation(
        self,
        organization_id: int,
        metric_type: str,
        start_date: datetime,
        end_date: datetime,
        filters: Dict[str, Any] = None,
        group_by: List[str] = None
    ) -> Dict[str, Any]:
        """Get aggregated metrics with optional grouping"""

        query = self.db.query(Ticket).filter(
            Ticket.organization_id == organization_id,
            Ticket.created_at >= start_date,
            Ticket.created_at <= end_date
        )

        if filters:
            query = self._apply_filters(query, filters)

        if metric_type == "ticket_count":
            if group_by:
                return self._group_by_aggregation(query, group_by)
            else:
                count = query.count()
                return {"total_count": count, "metric_type": metric_type}

        elif metric_type == "response_time":
            query = query.filter(Ticket.first_response_at.isnot(None))
            time_diff = self._get_time_diff_hours(Ticket.first_response_at, Ticket.created_at)
            stats = query.with_entities(
                func.avg(time_diff).label('avg'),
                func.min(time_diff).label('min'),
                func.max(time_diff).label('max'),
                func.count(Ticket.id).label('count')
            ).first()

            return {
                "metric_type": metric_type,
                "avg_value": float(stats.avg or 0),
                "min_value": float(stats.min or 0),
                "max_value": float(stats.max or 0),
                "total_count": stats.count
            }

        elif metric_type == "resolution_time":
            query = query.filter(Ticket.resolved_at.isnot(None))
            time_diff = self._get_time_diff_hours(Ticket.resolved_at, Ticket.created_at)
            stats = query.with_entities(
                func.avg(time_diff).label('avg'),
                func.min(time_diff).label('min'),
                func.max(time_diff).label('max'),
                func.count(Ticket.id).label('count')
            ).first()

            return {
                "metric_type": metric_type,
                "avg_value": float(stats.avg or 0),
                "min_value": float(stats.min or 0),
                "max_value": float(stats.max or 0),
                "total_count": stats.count
            }

        return {}

    def get_distribution(
        self,
        organization_id: int,
        field: str,
        start_date: datetime,
        end_date: datetime,
        filters: Dict[str, Any] = None
    ) -> Dict[str, int]:
        """Get distribution of values for a field"""

        query = self.db.query(Ticket).filter(
            Ticket.organization_id == organization_id,
            Ticket.created_at >= start_date,
            Ticket.created_at <= end_date
        )

        if filters:
            query = self._apply_filters(query, filters)

        if hasattr(Ticket, field):
            column = getattr(Ticket, field)
            results = (
                query.with_entities(
                    column.label('value'),
                    func.count(Ticket.id).label('count')
                )
                .group_by('value')
                .all()
            )

            return {str(r.value): r.count for r in results}

        return {}

    def get_percentiles(
        self,
        organization_id: int,
        metric_type: str,
        start_date: datetime,
        end_date: datetime,
        percentiles: List[int] = [50, 95, 99],
        filters: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """Calculate percentiles for a metric"""

        query = self.db.query(Ticket).filter(
            Ticket.organization_id == organization_id,
            Ticket.created_at >= start_date,
            Ticket.created_at <= end_date
        )

        if filters:
            query = self._apply_filters(query, filters)

        if metric_type == "response_time":
            query = query.filter(Ticket.first_response_at.isnot(None))
            values = [
                (r.first_response_at - r.created_at).total_seconds() / 3600
                for r in query.all()
            ]
        elif metric_type == "resolution_time":
            query = query.filter(Ticket.resolved_at.isnot(None))
            values = [
                (r.resolved_at - r.created_at).total_seconds() / 3600
                for r in query.all()
            ]
        else:
            return {}

        if not values:
            return {}

        import numpy as np
        values_array = np.array(values)

        result = {}
        for p in percentiles:
            result[f"p{p}"] = float(np.percentile(values_array, p))

        return result

    def get_dashboard_metrics(
        self,
        organization_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard metrics"""

        base_query = self.db.query(Ticket).filter(
            Ticket.organization_id == organization_id,
            Ticket.created_at >= start_date,
            Ticket.created_at <= end_date
        )

        # Total counts
        total_tickets = base_query.count()
        open_tickets = base_query.filter(Ticket.status == TicketStatus.OPEN).count()
        resolved_tickets = base_query.filter(Ticket.status == TicketStatus.RESOLVED).count()

        # Response time
        response_time_query = base_query.filter(Ticket.first_response_at.isnot(None))
        avg_response_time = response_time_query.with_entities(
            func.avg(self._get_time_diff_hours(Ticket.first_response_at, Ticket.created_at))
        ).scalar()

        # Resolution time
        resolution_time_query = base_query.filter(Ticket.resolved_at.isnot(None))
        avg_resolution_time = resolution_time_query.with_entities(
            func.avg(self._get_time_diff_hours(Ticket.resolved_at, Ticket.created_at))
        ).scalar()

        # Distributions
        sentiment_breakdown = self._get_sentiment_distribution(base_query)
        category_breakdown = self.get_distribution(organization_id, 'category', start_date, end_date)
        channel_breakdown = self.get_distribution(organization_id, 'channel', start_date, end_date)
        priority_breakdown = self.get_distribution(organization_id, 'priority', start_date, end_date)

        return {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "resolved_tickets": resolved_tickets,
            "avg_response_time_hours": float(avg_response_time or 0),
            "avg_resolution_time_hours": float(avg_resolution_time or 0),
            "sentiment_breakdown": sentiment_breakdown,
            "category_breakdown": category_breakdown,
            "channel_breakdown": channel_breakdown,
            "priority_breakdown": priority_breakdown
        }

    # Helper methods
    def _get_time_diff_hours(self, end_time, start_time):
        """Get time difference in hours (database-agnostic)"""
        if self.is_sqlite:
            # SQLite: Use julianday which returns days, multiply by 24 for hours
            return (func.julianday(end_time) - func.julianday(start_time)) * 24
        else:
            # PostgreSQL: Use extract epoch to get seconds, divide by 3600 for hours
            return extract('epoch', end_time - start_time) / 3600

    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to query"""
        if filters.get("status"):
            query = query.filter(Ticket.status.in_(filters["status"]))
        if filters.get("priority"):
            query = query.filter(Ticket.priority.in_(filters["priority"]))
        if filters.get("channel"):
            query = query.filter(Ticket.channel.in_(filters["channel"]))
        if filters.get("category"):
            query = query.filter(Ticket.category.in_(filters["category"]))
        if filters.get("assigned_to"):
            query = query.filter(Ticket.assigned_to == filters["assigned_to"])

        return query

    def _get_date_trunc_expression(self, granularity: str):
        """Get date truncation expression based on granularity"""
        if self.is_sqlite:
            # SQLite-compatible date truncation using strftime
            # Always return datetime format (YYYY-MM-DD HH:MM:SS) for consistency
            if granularity == "hourly":
                return func.strftime('%Y-%m-%d %H:00:00', Ticket.created_at)
            elif granularity == "daily":
                return func.strftime('%Y-%m-%d 00:00:00', Ticket.created_at)
            elif granularity == "weekly":
                # Get start of week (Monday) with time component
                return func.strftime('%Y-%m-%d 00:00:00', Ticket.created_at, 'weekday 0', '-6 days')
            elif granularity == "monthly":
                return func.strftime('%Y-%m-01 00:00:00', Ticket.created_at)
            elif granularity == "quarterly":
                # SQLite doesn't have native quarter support, use monthly and group in application
                return func.strftime('%Y-%m-01 00:00:00', Ticket.created_at)
            elif granularity == "yearly":
                return func.strftime('%Y-01-01 00:00:00', Ticket.created_at)
            else:
                return func.strftime('%Y-%m-%d 00:00:00', Ticket.created_at)
        else:
            # PostgreSQL date_trunc function
            if granularity == "hourly":
                return func.date_trunc('hour', Ticket.created_at)
            elif granularity == "daily":
                return func.date_trunc('day', Ticket.created_at)
            elif granularity == "weekly":
                return func.date_trunc('week', Ticket.created_at)
            elif granularity == "monthly":
                return func.date_trunc('month', Ticket.created_at)
            elif granularity == "quarterly":
                return func.date_trunc('quarter', Ticket.created_at)
            elif granularity == "yearly":
                return func.date_trunc('year', Ticket.created_at)
            else:
                return func.date_trunc('day', Ticket.created_at)

    def _group_by_aggregation(self, query, group_by: List[str]) -> Dict[str, Any]:
        """Perform group by aggregation"""
        result = {}

        for field in group_by:
            if hasattr(Ticket, field):
                column = getattr(Ticket, field)
                grouped = (
                    query.with_entities(
                        column.label('group_value'),
                        func.count(Ticket.id).label('count')
                    )
                    .group_by('group_value')
                    .all()
                )
                result[field] = {str(r.group_value): r.count for r in grouped}

        return result

    def _get_sentiment_distribution(self, query) -> Dict[str, int]:
        """Get sentiment distribution (positive, neutral, negative)"""
        results = query.filter(Ticket.sentiment_score.isnot(None)).with_entities(
            case(
                (Ticket.sentiment_score > 0.3, 'positive'),
                (Ticket.sentiment_score < -0.3, 'negative'),
                else_='neutral'
            ).label('sentiment_category'),
            func.count(Ticket.id).label('count')
        ).group_by('sentiment_category').all()

        return {r.sentiment_category: r.count for r in results}
