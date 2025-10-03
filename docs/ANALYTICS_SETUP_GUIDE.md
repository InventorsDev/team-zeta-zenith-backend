# Analytics API Setup Guide

## Quick Start

Follow these steps to set up and run the comprehensive analytics API.

## Prerequisites

- Python 3.8+
- PostgreSQL database
- Redis server (optional, for caching)
- pip and virtualenv

## Step 1: Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt
```

## Step 2: Configure Environment

Update your `.env` file with the following configurations:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/yourdb

# Redis (optional - analytics will work without it, but without caching)
REDIS_URL=redis://localhost:6379/0

# Other configurations
SECRET_KEY=your-secret-key
ENVIRONMENT=development
```

## Step 3: Run Database Migration

```bash
# Run migrations to create analytics tables
alembic upgrade head
```

This will create:
- `analytics_metrics` table
- `analytics_snapshots` table
- All necessary indexes

## Step 4: Start Redis (Optional but Recommended)

### Using Docker:
```bash
docker run -d -p 6379:6379 redis:alpine
```

### Using Redis directly:
```bash
redis-server
```

### Verify Redis connection:
```bash
redis-cli ping
# Should return: PONG
```

## Step 5: Start the Application

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Step 6: Verify Installation

### Test API Status:
```bash
curl http://localhost:8000/api/v1/status
```

### Test Analytics Endpoint:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/v1/analytics/dashboard"
```

### Access API Documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Step 7: Test WebSocket Connection

### Using Python:
```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/api/v1/ws/analytics/1?token=YOUR_JWT_TOKEN"
    async with websockets.connect(uri) as websocket:
        # Receive connection message
        message = await websocket.recv()
        print(f"Received: {message}")

        # Subscribe to metrics
        await websocket.send(json.dumps({
            "type": "subscribe",
            "metrics": ["ticket_count", "response_time"],
            "interval": 30
        }))

        # Receive updates
        while True:
            message = await websocket.recv()
            print(f"Update: {message}")

asyncio.run(test_websocket())
```

### Using JavaScript (Browser):
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/analytics/1?token=YOUR_JWT_TOKEN');

ws.onopen = () => {
    console.log('Connected');
    ws.send(JSON.stringify({
        type: 'subscribe',
        metrics: ['ticket_count'],
        interval: 30
    }));
};

ws.onmessage = (event) => {
    console.log('Received:', JSON.parse(event.data));
};
```

## API Usage Examples

### 1. Get Time-Series Data

```bash
curl -X GET "http://localhost:8000/api/v1/analytics/time-series/ticket_count?start_date=2025-01-01T00:00:00&end_date=2025-01-31T23:59:59&granularity=daily" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. Get Dashboard Metrics

```bash
curl -X GET "http://localhost:8000/api/v1/analytics/dashboard" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Export to CSV

```bash
curl -X POST "http://localhost:8000/api/v1/analytics/export" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metric_types": ["ticket_count", "response_time"],
    "start_date": "2025-01-01T00:00:00",
    "end_date": "2025-01-31T23:59:59",
    "format": "csv",
    "granularity": "daily"
  }' --output analytics_export.csv
```

### 4. Invalidate Cache

```bash
curl -X DELETE "http://localhost:8000/api/v1/analytics/cache" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Complex Aggregation

```bash
curl -X POST "http://localhost:8000/api/v1/analytics/aggregations" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metric_types": ["ticket_count", "response_time"],
    "start_date": "2025-01-01T00:00:00",
    "end_date": "2025-01-31T23:59:59",
    "granularity": "daily",
    "filters": {
      "status": ["open", "in_progress"],
      "priority": ["high", "urgent"]
    },
    "group_by": ["status", "priority"]
  }'
```

## Troubleshooting

### Issue: Redis connection fails
**Solution:**
- Verify Redis is running: `redis-cli ping`
- Check REDIS_URL in .env file
- Analytics will still work without Redis, but without caching

### Issue: WebSocket connection fails
**Solution:**
- Ensure WebSocket support is enabled in your reverse proxy (if using one)
- Check firewall settings
- Verify JWT token is valid

### Issue: Slow queries
**Solution:**
- Enable Redis caching
- Check database indexes: `\d analytics_metrics` in psql
- Use appropriate time granularity
- Add filters to reduce data volume

### Issue: Migration fails
**Solution:**
```bash
# Check current migration version
alembic current

# Downgrade if needed
alembic downgrade -1

# Upgrade again
alembic upgrade head
```

### Issue: Import errors
**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Verify installations
python -c "import app.models.analytics; print('Success')"
```

## Testing

### Run Tests:
```bash
# Run all tests
pytest

# Run analytics tests only
pytest app/tests/test_analytics.py

# Run with coverage
pytest --cov=app/services/analytics_service --cov-report=html
```

### Manual Testing Checklist:
- [ ] Database migration successful
- [ ] Redis connection working
- [ ] API endpoints responding
- [ ] WebSocket connection established
- [ ] Cache invalidation working
- [ ] Export functionality working (CSV/JSON)
- [ ] Time-series data accurate
- [ ] Dashboard metrics correct
- [ ] Performance metrics calculated

## Performance Tuning

### Database Optimization:
```sql
-- Analyze tables for better query planning
ANALYZE analytics_metrics;
ANALYZE analytics_snapshots;

-- Check index usage
SELECT * FROM pg_stat_user_indexes
WHERE schemaname = 'public'
AND indexrelname LIKE 'ix_analytics%';
```

### Redis Configuration:
```bash
# In redis.conf, set appropriate memory limit
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence (optional)
save 900 1
save 300 10
save 60 10000
```

### Application Settings:
```python
# In analytics_service.py, adjust cache TTL
self.default_cache_ttl = 3600  # 1 hour (adjust as needed)
```

## Monitoring

### Check Redis Usage:
```bash
redis-cli info stats
redis-cli info memory
```

### Monitor Database:
```sql
-- Check slow queries
SELECT * FROM pg_stat_statements
WHERE query LIKE '%analytics%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check table sizes
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE tablename LIKE 'analytics_%';
```

### Application Logs:
```bash
# View analytics logs
tail -f logs/analytics.log

# Search for errors
grep -i "error" logs/analytics.log
```

## Production Deployment

### 1. Environment Setup:
```bash
ENVIRONMENT=production
DEBUG=false
REDIS_URL=redis://production-redis:6379/0
DATABASE_URL=postgresql://prod_user:pass@prod-db:5432/prod_db
```

### 2. Use Production Server:
```bash
# Using Gunicorn with Uvicorn workers
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log
```

### 3. Configure Nginx (if using):
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /api/v1/ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 4. Setup Systemd Service:
```ini
[Unit]
Description=Analytics API
After=network.target redis.service postgresql.service

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/app
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
KillSignal=SIGQUIT
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

## Maintenance

### Regular Tasks:
```bash
# Clean old analytics snapshots (older than 90 days)
DELETE FROM analytics_snapshots WHERE snapshot_date < NOW() - INTERVAL '90 days';

# Vacuum tables
VACUUM ANALYZE analytics_metrics;
VACUUM ANALYZE analytics_snapshots;

# Clear Redis cache
redis-cli FLUSHDB
```

### Backup:
```bash
# Backup database
pg_dump -h localhost -U user -d dbname -t analytics_metrics -t analytics_snapshots > analytics_backup.sql

# Backup Redis
redis-cli SAVE
cp /var/lib/redis/dump.rdb /backup/redis_$(date +%Y%m%d).rdb
```

## Support

For issues or questions:
1. Check the documentation: `docs/ANALYTICS_API.md`
2. Review implementation summary: `docs/ANALYTICS_IMPLEMENTATION_SUMMARY.md`
3. Check application logs
4. Run tests to verify functionality

## Next Steps

After setup is complete:
1. ✅ Review API documentation
2. ✅ Test all endpoints
3. ✅ Set up monitoring and alerts
4. ✅ Configure backup schedules
5. ✅ Implement rate limiting (if needed)
6. ✅ Set up SSL/TLS for production
7. ✅ Configure CORS policies
8. ✅ Set up log rotation

## Success Indicators

Your analytics API is properly set up when:
- ✅ All migrations run successfully
- ✅ API endpoints return data
- ✅ WebSocket connections work
- ✅ Redis caching is operational
- ✅ Exports generate correctly
- ✅ Cache invalidation triggers properly
- ✅ Tests pass successfully
- ✅ Performance is acceptable (<200ms for cached queries)

Happy analyzing! 📊
