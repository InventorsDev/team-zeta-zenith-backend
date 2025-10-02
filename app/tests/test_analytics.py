import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketChannel
from app.models.organization import Organization
from app.database.repositories.analytics_repository import AnalyticsRepository
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import AggregationQuery, MetricType, TimeGranularity


class TestAnalyticsRepository:
    """Test analytics repository functions"""

    def test_get_time_series_ticket_count(self, db: Session, test_organization: Organization):
        """Test getting time-series ticket count data"""
        repo = AnalyticsRepository(db)

        # Create test tickets
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        for i in range(10):
            ticket = Ticket(
                title=f"Test Ticket {i}",
                description=f"Description {i}",
                organization_id=test_organization.id,
                channel=TicketChannel.EMAIL,
                status=TicketStatus.OPEN,
                priority=TicketPriority.MEDIUM,
                customer_email=f"test{i}@example.com",
                created_at=start_date + timedelta(days=i % 5)
            )
            db.add(ticket)
        db.commit()

        # Get time series
        result = repo.get_time_series(
            organization_id=test_organization.id,
            metric_type="ticket_count",
            start_date=start_date,
            end_date=end_date,
            granularity="daily"
        )

        assert len(result) > 0
        assert all(hasattr(point, 'timestamp') for point in result)
        assert all(hasattr(point, 'value') for point in result)

    def test_get_distribution(self, db: Session, test_organization: Organization):
        """Test getting distribution of field values"""
        repo = AnalyticsRepository(db)

        # Create tickets with different statuses
        statuses = [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED]
        for i, status in enumerate(statuses * 3):
            ticket = Ticket(
                title=f"Test Ticket {i}",
                description=f"Description {i}",
                organization_id=test_organization.id,
                channel=TicketChannel.EMAIL,
                status=status,
                priority=TicketPriority.MEDIUM,
                customer_email=f"test{i}@example.com"
            )
            db.add(ticket)
        db.commit()

        # Get distribution
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow()

        distribution = repo.get_distribution(
            organization_id=test_organization.id,
            field='status',
            start_date=start_date,
            end_date=end_date
        )

        assert len(distribution) > 0
        assert 'open' in distribution or 'in_progress' in distribution or 'resolved' in distribution

    def test_get_dashboard_metrics(self, db: Session, test_organization: Organization):
        """Test getting dashboard metrics"""
        repo = AnalyticsRepository(db)

        # Create test tickets
        for i in range(5):
            ticket = Ticket(
                title=f"Test Ticket {i}",
                description=f"Description {i}",
                organization_id=test_organization.id,
                channel=TicketChannel.EMAIL,
                status=TicketStatus.OPEN if i % 2 == 0 else TicketStatus.RESOLVED,
                priority=TicketPriority.HIGH,
                customer_email=f"test{i}@example.com",
                sentiment_score=0.5 if i % 2 == 0 else -0.3
            )
            db.add(ticket)
        db.commit()

        # Get dashboard metrics
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        metrics = repo.get_dashboard_metrics(
            organization_id=test_organization.id,
            start_date=start_date,
            end_date=end_date
        )

        assert 'total_tickets' in metrics
        assert 'open_tickets' in metrics
        assert 'resolved_tickets' in metrics
        assert metrics['total_tickets'] >= 5


class TestAnalyticsService:
    """Test analytics service with caching"""

    def test_get_time_series_with_cache(self, db: Session, test_organization: Organization):
        """Test time-series with caching"""
        service = AnalyticsService(db, cache_manager=None)  # No cache for this test

        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        # First call
        result1 = service.get_time_series(
            organization_id=test_organization.id,
            metric_type="ticket_count",
            start_date=start_date,
            end_date=end_date,
            granularity="daily",
            use_cache=False
        )

        assert result1.metric_type == "ticket_count"
        assert result1.granularity == "daily"
        assert isinstance(result1.data_points, list)

    def test_get_aggregation(self, db: Session, test_organization: Organization):
        """Test aggregation queries"""
        service = AnalyticsService(db, cache_manager=None)

        query = AggregationQuery(
            metric_types=[MetricType.TICKET_COUNT],
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow(),
            granularity=TimeGranularity.DAILY,
            filters={},
            group_by=["status"]
        )

        results = service.get_aggregation(
            query=query,
            organization_id=test_organization.id,
            use_cache=False
        )

        assert len(results) == 1
        assert results[0].metric_type == "ticket_count"

    def test_get_dashboard_metrics(self, db: Session, test_organization: Organization):
        """Test dashboard metrics"""
        service = AnalyticsService(db, cache_manager=None)

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()

        metrics = service.get_dashboard_metrics(
            organization_id=test_organization.id,
            start_date=start_date,
            end_date=end_date,
            use_cache=False
        )

        assert metrics.total_tickets >= 0
        assert metrics.open_tickets >= 0
        assert metrics.resolved_tickets >= 0

    def test_export_data(self, db: Session, test_organization: Organization):
        """Test data export"""
        service = AnalyticsService(db, cache_manager=None)

        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        export_data = service.export_data(
            organization_id=test_organization.id,
            metric_types=["ticket_count"],
            start_date=start_date,
            end_date=end_date,
            format="json",
            granularity="daily"
        )

        assert 'organization_id' in export_data
        assert 'metrics' in export_data
        assert 'ticket_count' in export_data['metrics']


class TestAnalyticsAPI:
    """Test analytics API endpoints"""

    @pytest.mark.asyncio
    async def test_time_series_endpoint(self, client, auth_headers, test_organization):
        """Test time-series endpoint"""
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        response = client.get(
            f"/api/v1/analytics/time-series/ticket_count",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "granularity": "daily"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert 'metric_type' in data
        assert 'data_points' in data

    @pytest.mark.asyncio
    async def test_dashboard_endpoint(self, client, auth_headers, test_organization):
        """Test dashboard endpoint"""
        response = client.get(
            "/api/v1/analytics/dashboard",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert 'total_tickets' in data
        assert 'open_tickets' in data

    @pytest.mark.asyncio
    async def test_export_endpoint(self, client, auth_headers, test_organization):
        """Test export endpoint"""
        export_request = {
            "metric_types": ["ticket_count"],
            "start_date": (datetime.utcnow() - timedelta(days=7)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "format": "json",
            "granularity": "daily"
        }

        response = client.post(
            "/api/v1/analytics/export",
            json=export_request,
            headers=auth_headers
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cache_invalidation_endpoint(self, client, auth_headers, test_organization):
        """Test cache invalidation endpoint"""
        response = client.delete(
            "/api/v1/analytics/cache",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert 'message' in data
        assert 'Cache invalidated successfully' in data['message']


# Fixtures
@pytest.fixture
def test_organization(db: Session):
    """Create a test organization"""
    org = Organization(
        name="Test Organization",
        slug="test-org"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def auth_headers():
    """Mock authentication headers"""
    return {
        "Authorization": "Bearer test_token"
    }
