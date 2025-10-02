# Analytics API Documentation

## Overview

The Analytics API provides comprehensive time-series analytics, aggregation queries, export functionality, and real-time updates via WebSocket. All queries are optimized with Redis caching for performance.

## Features

- ✅ Time-series data with multiple granularities (hourly, daily, weekly, monthly, quarterly, yearly)
- ✅ Complex aggregation queries with filtering and grouping
- ✅ Redis caching for expensive queries
- ✅ Export functionality (CSV, JSON, Excel)
- ✅ Real-time analytics via WebSocket
- ✅ Automatic cache invalidation on data changes
- ✅ Dashboard metrics and performance percentiles

## API Endpoints

### 1. Time-Series Analytics

**GET** `/api/v1/analytics/time-series/{metric_type}`

Get time-series data with specified granularity.

**Parameters:**
- `metric_type` (path): Type of metric (ticket_count, response_time, resolution_time, sentiment_score)
- `start_date` (query, required): Start date for analysis
- `end_date` (query, required): End date for analysis
- `granularity` (query): Time granularity (hourly, daily, weekly, monthly, quarterly, yearly) - default: daily
- `status` (query): Filter by ticket status (can be multiple)
- `priority` (query): Filter by priority (can be multiple)
- `channel` (query): Filter by channel (can be multiple)
- `category` (query): Filter by category (can be multiple)
- `use_cache` (query): Use cached results - default: true

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/analytics/time-series/ticket_count?start_date=2025-01-01T00:00:00&end_date=2025-01-31T23:59:59&granularity=daily" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "metric_type": "ticket_count",
  "granularity": "daily",
  "start_date": "2025-01-01T00:00:00",
  "end_date": "2025-01-31T23:59:59",
  "data_points": [
    {
      "timestamp": "2025-01-01T00:00:00",
      "value": 45.0,
      "count": 45,
      "metadata": {}
    }
  ],
  "total_count": 1234,
  "average_value": 39.8,
  "min_value": 12.0,
  "max_value": 89.0
}
```

### 2. Aggregated Analytics

**POST** `/api/v1/analytics/aggregations`

Get complex aggregated analytics with grouping and filtering.

**Request Body:**
```json
{
  "metric_types": ["ticket_count", "response_time", "resolution_time"],
  "start_date": "2025-01-01T00:00:00",
  "end_date": "2025-01-31T23:59:59",
  "granularity": "daily",
  "filters": {
    "status": ["open", "in_progress"],
    "priority": ["high", "urgent"]
  },
  "group_by": ["status", "priority"]
}
```

**Response:**
```json
{
  "organization_id": 1,
  "query": { ... },
  "results": [
    {
      "metric_type": "ticket_count",
      "granularity": "daily",
      "total_count": 567,
      "sum_value": null,
      "avg_value": 18.3,
      "min_value": 5.0,
      "max_value": 42.0,
      "breakdown": {
        "status": {
          "open": 234,
          "in_progress": 333
        },
        "priority": {
          "high": 189,
          "urgent": 378
        }
      },
      "time_series": [ ... ]
    }
  ],
  "generated_at": "2025-10-02T12:34:56"
}
```

### 3. Dashboard Metrics

**GET** `/api/v1/analytics/dashboard`

Get comprehensive dashboard metrics with trends.

**Parameters:**
- `start_date` (query): Start date (default: 30 days ago)
- `end_date` (query): End date (default: now)
- `use_cache` (query): Use cached results - default: true

**Response:**
```json
{
  "total_tickets": 1234,
  "open_tickets": 456,
  "resolved_tickets": 678,
  "avg_response_time_hours": 2.5,
  "avg_resolution_time_hours": 24.3,
  "sentiment_breakdown": {
    "positive": 500,
    "neutral": 400,
    "negative": 334
  },
  "category_breakdown": {
    "billing": 345,
    "technical": 567,
    "general": 322
  },
  "channel_breakdown": {
    "email": 678,
    "slack": 345,
    "zendesk": 211
  },
  "priority_breakdown": {
    "low": 234,
    "medium": 567,
    "high": 345,
    "urgent": 88
  },
  "trend_data": {
    "ticket_count": [ ... ],
    "response_time": [ ... ],
    "resolution_time": [ ... ]
  }
}
```

### 4. Performance Metrics

**GET** `/api/v1/analytics/performance`

Get performance metrics including percentiles and SLA compliance.

**Parameters:**
- `start_date` (query): Start date (default: 30 days ago)
- `end_date` (query): End date (default: now)
- `use_cache` (query): Use cached results - default: true

**Response:**
```json
{
  "response_time_p50": 1.5,
  "response_time_p95": 4.2,
  "response_time_p99": 8.7,
  "resolution_time_p50": 12.3,
  "resolution_time_p95": 48.5,
  "resolution_time_p99": 96.2,
  "sla_compliance_rate": null
}
```

### 5. Distribution Analytics

**GET** `/api/v1/analytics/distribution/{field}`

Get distribution of values for a specific field.

**Parameters:**
- `field` (path): Field name (status, priority, channel, category, etc.)
- `start_date` (query, required): Start date for analysis
- `end_date` (query, required): End date for analysis
- `status` (query): Filter by status
- `priority` (query): Filter by priority
- `use_cache` (query): Use cached results - default: true

**Response:**
```json
{
  "field": "status",
  "distribution": {
    "open": 456,
    "in_progress": 234,
    "resolved": 678,
    "closed": 123
  },
  "total": 1491,
  "period": {
    "start": "2025-01-01T00:00:00",
    "end": "2025-01-31T23:59:59"
  }
}
```

### 6. Export Analytics

**POST** `/api/v1/analytics/export`

Export analytics data in CSV, JSON, or Excel format.

**Request Body:**
```json
{
  "metric_types": ["ticket_count", "response_time"],
  "start_date": "2025-01-01T00:00:00",
  "end_date": "2025-01-31T23:59:59",
  "format": "csv",
  "granularity": "daily",
  "filters": {},
  "include_raw_data": false
}
```

**Response:**
- For CSV: Returns a downloadable CSV file
- For JSON: Returns JSON data directly
- For Excel: Returns JSON with note (requires openpyxl)

### 7. Cache Management

**DELETE** `/api/v1/analytics/cache`

Invalidate analytics cache for the organization.

**Parameters:**
- `pattern` (query): Cache pattern to invalidate (optional, defaults to all)

**Response:**
```json
{
  "message": "Cache invalidated successfully",
  "organization_id": 1,
  "pattern": "all analytics data"
}
```

**POST** `/api/v1/analytics/refresh-cache`

Refresh analytics cache in the background.

**Response:**
```json
{
  "message": "Cache refresh initiated in background",
  "organization_id": 1
}
```

## WebSocket API

### Real-Time Analytics Stream

**WebSocket** `ws://localhost:8000/api/v1/ws/analytics/{organization_id}?token={jwt_token}`

Connect to receive real-time analytics updates.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/analytics/1?token=YOUR_JWT_TOKEN');

ws.onopen = () => {
  console.log('Connected to analytics stream');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

**Client Messages:**

1. Subscribe to metrics:
```json
{
  "type": "subscribe",
  "metrics": ["ticket_count", "response_time"],
  "interval": 30
}
```

2. Unsubscribe:
```json
{
  "type": "unsubscribe"
}
```

3. Ping (keepalive):
```json
{
  "type": "ping"
}
```

**Server Messages:**

1. Connection confirmation:
```json
{
  "type": "connected",
  "organization_id": 1,
  "timestamp": "2025-10-02T12:34:56",
  "message": "Connected to real-time analytics"
}
```

2. Subscription data:
```json
{
  "type": "subscription_data",
  "organization_id": 1,
  "timestamp": "2025-10-02T12:34:56",
  "metrics": {
    "ticket_count": {
      "data_points": [ ... ],
      "average_value": 45.2,
      "total_count": 234
    }
  }
}
```

3. Periodic updates:
```json
{
  "type": "periodic_update",
  "organization_id": 1,
  "timestamp": "2025-10-02T12:35:26",
  "metrics": {
    "ticket_count": {
      "value": 3.0,
      "count": 3,
      "timestamp": "2025-10-02T12:35:00"
    }
  },
  "dashboard_snapshot": {
    "total_tickets": 1234,
    "open_tickets": 456,
    "resolved_tickets": 678,
    "avg_response_time_hours": 2.5
  }
}
```

4. Metric update (broadcast):
```json
{
  "type": "metric_update",
  "organization_id": 1,
  "metric_type": "ticket_count",
  "value": 1.0,
  "timestamp": "2025-10-02T12:35:45"
}
```

## Caching Strategy

### Cache Keys
Cache keys are generated using MD5 hashes of query parameters:
- Format: `{prefix}:org={org_id}:metric={type}:start={date}:end={date}:...`

### Cache TTL
- Default: 1 hour (3600 seconds)
- Configurable per query

### Cache Invalidation

Automatic invalidation occurs on:
- **Ticket Creation**: Invalidates ticket_count, dashboard, distribution caches
- **Ticket Update**: Invalidates relevant metric caches based on changed fields
- **First Response**: Invalidates response_time, performance, dashboard caches
- **Resolution**: Invalidates resolution_time, performance, dashboard, status distribution caches

Manual invalidation:
```bash
# Invalidate all caches for organization
DELETE /api/v1/analytics/cache

# Invalidate specific pattern
DELETE /api/v1/analytics/cache?pattern=dashboard

# Refresh all caches in background
POST /api/v1/analytics/refresh-cache
```

## Metric Types

- `ticket_count`: Number of tickets created
- `response_time`: Average time to first response (in hours)
- `resolution_time`: Average time to resolution (in hours)
- `sentiment_score`: Average sentiment score
- `category_distribution`: Distribution of ticket categories
- `channel_distribution`: Distribution of ticket channels
- `priority_distribution`: Distribution of ticket priorities
- `status_distribution`: Distribution of ticket statuses

## Time Granularities

- `hourly`: Hour-by-hour breakdown
- `daily`: Day-by-day breakdown
- `weekly`: Week-by-week breakdown
- `monthly`: Month-by-month breakdown
- `quarterly`: Quarter-by-quarter breakdown
- `yearly`: Year-by-year breakdown

## Export Formats

- `json`: JSON format (direct response)
- `csv`: CSV file (downloadable)
- `excel`: Excel file (requires openpyxl - currently returns JSON)

## Database Schema

### analytics_metrics
Stores time-series metric data:
- `organization_id`: Organization reference
- `metric_type`: Type of metric
- `granularity`: Time granularity
- `timestamp`: Time bucket
- `value`, `count`: Metric values
- `min_value`, `max_value`, `avg_value`, `sum_value`: Aggregated stats
- `breakdown`: JSON field for dimensional breakdowns

### analytics_snapshots
Stores periodic snapshots for faster querying:
- `organization_id`: Organization reference
- `snapshot_type`: Type of snapshot
- `snapshot_date`: Snapshot date
- `data`: JSON snapshot data
- `generated_at`: Generation timestamp
- `is_complete`: Completion flag

## Migration

Run the migration to create analytics tables:

```bash
alembic upgrade head
```

This will execute migration `004_add_analytics_tables.py`

## Usage Examples

### Python Client

```python
import requests
from datetime import datetime, timedelta

# Configuration
API_URL = "http://localhost:8000/api/v1"
TOKEN = "your_jwt_token"
headers = {"Authorization": f"Bearer {TOKEN}"}

# Get time-series data
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=30)

response = requests.get(
    f"{API_URL}/analytics/time-series/ticket_count",
    params={
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "granularity": "daily"
    },
    headers=headers
)
data = response.json()

# Get dashboard metrics
response = requests.get(
    f"{API_URL}/analytics/dashboard",
    headers=headers
)
dashboard = response.json()

# Export to CSV
export_request = {
    "metric_types": ["ticket_count", "response_time"],
    "start_date": start_date.isoformat(),
    "end_date": end_date.isoformat(),
    "format": "csv",
    "granularity": "daily"
}

response = requests.post(
    f"{API_URL}/analytics/export",
    json=export_request,
    headers=headers
)

with open("analytics_export.csv", "wb") as f:
    f.write(response.content)
```

### JavaScript Client (WebSocket)

```javascript
class AnalyticsClient {
  constructor(orgId, token) {
    this.orgId = orgId;
    this.token = token;
    this.ws = null;
  }

  connect() {
    this.ws = new WebSocket(
      `ws://localhost:8000/api/v1/ws/analytics/${this.orgId}?token=${this.token}`
    );

    this.ws.onopen = () => {
      console.log('Connected to analytics stream');
      this.subscribe(['ticket_count', 'response_time']);
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('Disconnected from analytics stream');
      // Reconnect logic here
    };
  }

  subscribe(metrics) {
    this.send({
      type: 'subscribe',
      metrics: metrics,
      interval: 30
    });
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  handleMessage(data) {
    switch (data.type) {
      case 'connected':
        console.log('Connection confirmed:', data);
        break;
      case 'subscription_data':
        console.log('Initial subscription data:', data);
        break;
      case 'periodic_update':
        console.log('Periodic update:', data);
        this.updateDashboard(data);
        break;
      case 'metric_update':
        console.log('Metric update:', data);
        break;
    }
  }

  updateDashboard(data) {
    // Update your dashboard UI here
    console.log('Dashboard snapshot:', data.dashboard_snapshot);
  }
}

// Usage
const client = new AnalyticsClient(1, 'your_jwt_token');
client.connect();
```

## Performance Considerations

1. **Use Caching**: Always use caching for repeated queries (default: enabled)
2. **Appropriate Granularity**: Use appropriate time granularity for your date range
3. **Filter Early**: Apply filters to reduce data volume
4. **Export Limits**: Be mindful of data volumes when exporting
5. **WebSocket Interval**: Don't set too low interval for real-time updates (min 30s recommended)

## Troubleshooting

### Cache Not Working
- Verify Redis is running and accessible
- Check Redis connection in logs
- Manually invalidate cache if stale: `DELETE /api/v1/analytics/cache`

### Slow Queries
- Check database indexes on tickets table
- Use appropriate granularity for date range
- Enable caching
- Consider using snapshots for historical data

### WebSocket Disconnects
- Implement reconnection logic in client
- Use ping/pong for keepalive
- Check token expiration

## Next Steps

1. Run migration: `alembic upgrade head`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure Redis in `.env`
4. Test endpoints with the examples above
5. Integrate WebSocket for real-time updates
