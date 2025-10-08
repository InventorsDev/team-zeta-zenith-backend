# Deployment Guide

Complete guide for deploying the AI-Powered Customer Support Analyzer backend to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Database Setup](#database-setup)
4. [Application Deployment](#application-deployment)
5. [Monitoring Setup](#monitoring-setup)
6. [Security Checklist](#security-checklist)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **OS**: Ubuntu 22.04 LTS or later (recommended)
- **CPU**: 4+ cores
- **RAM**: 8GB+ (16GB recommended for ML workloads)
- **Storage**: 50GB+ SSD
- **Python**: 3.12+
- **PostgreSQL**: 15+
- **Redis**: 7+

### Required Services

- Domain name with SSL certificate
- SMTP server for email notifications (optional)
- Slack workspace for notifications (optional)

## Environment Configuration

### 1. Create Environment File

```bash
cp .env.example .env
```

### 2. Configure Environment Variables

```bash
# Application
APP_NAME="AI-Powered Customer Support Analyzer"
APP_VERSION="1.0.0"
ENVIRONMENT="production"
API_V1_PREFIX="/api/v1"

# Security
SECRET_KEY="<generate-secure-random-key-min-32-chars>"
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database - PostgreSQL
DATABASE_URL="postgresql://zenith_user:secure_password@localhost:5432/zenith_db"
POSTGRES_USER="zenith_user"
POSTGRES_PASSWORD="<secure-password>"
POSTGRES_DB="zenith_db"
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"

# Redis & Celery
REDIS_URL="redis://localhost:6379/0"
CELERY_BROKER_URL="redis://localhost:6379/1"
CELERY_RESULT_BACKEND="redis://localhost:6379/2"

# CORS - Add your frontend URLs
BACKEND_CORS_ORIGINS="https://app.yourdomain.com,https://yourdomain.com"

# External Integrations (optional)
OPENAI_API_KEY="<your-openai-key>"
SLACK_BOT_TOKEN="<your-slack-bot-token>"
SLACK_WEBHOOK_URL="<your-slack-webhook>"
ZENDESK_SUBDOMAIN="<your-subdomain>"
ZENDESK_EMAIL="<zendesk-email>"
ZENDESK_API_TOKEN="<zendesk-api-token>"

# Email Configuration (optional)
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USER="<email>"
SMTP_PASSWORD="<password>"

# Logging
LOG_LEVEL="INFO"
```

## Database Setup

### 1. Install PostgreSQL

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

### 2. Create Database and User

```bash
sudo -u postgres psql

CREATE DATABASE zenith_db;
CREATE USER zenith_user WITH ENCRYPTED PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE zenith_db TO zenith_user;
\q
```

### 3. Apply Migrations

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head
```

### 4. Optimize PostgreSQL for Production

Edit `/etc/postgresql/15/main/postgresql.conf`:

```conf
# Memory Settings
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 16MB

# Checkpoint Settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# Query Planning
default_statistics_target = 100
random_page_cost = 1.1

# Connection Settings
max_connections = 100
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

## Application Deployment

### Method 1: Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml up -d --build

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### Method 2: Systemd Service

#### 1. Create Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. Create Systemd Service File

Create `/etc/systemd/system/zenith-api.service`:

```ini
[Unit]
Description=Zenith API Service
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=zenith
Group=zenith
WorkingDirectory=/opt/zenith/team-zeta-zenith-backend
Environment="PATH=/opt/zenith/team-zeta-zenith-backend/venv/bin"
ExecStart=/opt/zenith/team-zeta-zenith-backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 3. Create Celery Worker Service

Create `/etc/systemd/system/zenith-celery-worker.service`:

```ini
[Unit]
Description=Zenith Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=zenith
Group=zenith
WorkingDirectory=/opt/zenith/team-zeta-zenith-backend
Environment="PATH=/opt/zenith/team-zeta-zenith-backend/venv/bin"
ExecStart=/opt/zenith/team-zeta-zenith-backend/venv/bin/celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 4. Create Celery Beat Service

Create `/etc/systemd/system/zenith-celery-beat.service`:

```ini
[Unit]
Description=Zenith Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=zenith
Group=zenith
WorkingDirectory=/opt/zenith/team-zeta-zenith-backend
Environment="PATH=/opt/zenith/team-zeta-zenith-backend/venv/bin"
ExecStart=/opt/zenith/team-zeta-zenith-backend/venv/bin/celery -A app.tasks.celery_app beat --loglevel=info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 5. Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable zenith-api zenith-celery-worker zenith-celery-beat
sudo systemctl start zenith-api zenith-celery-worker zenith-celery-beat

# Check status
sudo systemctl status zenith-api
sudo systemctl status zenith-celery-worker
sudo systemctl status zenith-celery-beat
```

### Method 3: Nginx Reverse Proxy

#### 1. Install Nginx

```bash
sudo apt install nginx
```

#### 2. Configure Nginx

Create `/etc/nginx/sites-available/zenith`:

```nginx
upstream zenith_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Logging
    access_log /var/log/nginx/zenith_access.log;
    error_log /var/log/nginx/zenith_error.log;

    # Proxy Settings
    location / {
        proxy_pass http://zenith_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files (if any)
    location /static {
        alias /opt/zenith/team-zeta-zenith-backend/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # File upload size
    client_max_body_size 10M;
}
```

#### 3. Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/zenith /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Monitoring Setup

### 1. Application Monitoring

The application includes built-in monitoring:

- **Performance Monitoring**: Automatic tracking of endpoint response times
- **Slow Query Detection**: Logs queries >100ms
- **Database Connection Pool**: Monitors connection usage
- **Rate Limiting**: Tracks rate limit violations

### 2. Health Checks

```bash
# API health check
curl https://api.yourdomain.com/health

# Expected response:
{
  "status": "healthy",
  "app_name": "AI-Powered Customer Support Analyzer",
  "version": "1.0.0",
  "environment": "production",
  "database": "connected"
}
```

### 3. Log Management

#### Application Logs

```bash
# View API logs
sudo journalctl -u zenith-api -f

# View Celery worker logs
sudo journalctl -u zenith-celery-worker -f

# View Nginx logs
tail -f /var/log/nginx/zenith_access.log
tail -f /var/log/nginx/zenith_error.log
```

#### Log Rotation

Create `/etc/logrotate.d/zenith`:

```
/var/log/zenith/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    create 0640 zenith zenith
    sharedscripts
    postrotate
        systemctl reload zenith-api
    endscript
}
```

### 4. Metrics Collection

#### Prometheus Integration (Optional)

The app exposes Prometheus metrics at `/metrics`:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'zenith-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

## Security Checklist

### Pre-Deployment

- [ ] Strong `SECRET_KEY` generated (min 32 characters)
- [ ] All default passwords changed
- [ ] CORS origins properly configured
- [ ] SSL/TLS certificates installed
- [ ] Firewall rules configured (only ports 80, 443, 22 open)
- [ ] Database access restricted to localhost or private network
- [ ] Redis password set (if exposed)

### Post-Deployment

- [ ] Run security scan: `safety check`
- [ ] Test authentication flows
- [ ] Verify rate limiting is active
- [ ] Check audit logs are being created
- [ ] Test backup and restore procedures
- [ ] Set up automated backups

### Ongoing

- [ ] Regular dependency updates
- [ ] Monitor security advisories
- [ ] Review audit logs weekly
- [ ] Rotate API keys quarterly
- [ ] Update SSL certificates before expiry

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -U zenith_user -d zenith_db -h localhost

# View PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

#### 2. Redis Connection Errors

```bash
# Check Redis is running
sudo systemctl status redis

# Test connection
redis-cli ping

# View Redis logs
sudo journalctl -u redis -f
```

#### 3. Celery Workers Not Processing Tasks

```bash
# Check worker status
sudo systemctl status zenith-celery-worker

# Restart workers
sudo systemctl restart zenith-celery-worker

# View worker logs
sudo journalctl -u zenith-celery-worker -n 100
```

#### 4. High Memory Usage

```bash
# Check memory usage
free -h
docker stats  # If using Docker

# Restart services
sudo systemctl restart zenith-api
sudo systemctl restart zenith-celery-worker
```

#### 5. Slow API Response Times

- Check database query performance
- Review Redis cache hit rates
- Monitor connection pool usage
- Check Nginx access logs for bottlenecks

### Performance Tuning

#### Database

```sql
-- Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

#### Redis

```bash
# Check memory usage
redis-cli info memory

# Monitor commands
redis-cli monitor

# Check hit rate
redis-cli info stats | grep keyspace
```

## Backup and Recovery

### Database Backups

```bash
# Create backup
pg_dump -U zenith_user zenith_db > backup_$(date +%Y%m%d).sql

# Restore backup
psql -U zenith_user zenith_db < backup_20240101.sql

# Automated daily backups (cron)
0 2 * * * pg_dump -U zenith_user zenith_db | gzip > /backups/zenith_$(date +\%Y\%m\%d).sql.gz
```

### Redis Backups

```bash
# Create snapshot
redis-cli SAVE

# Copy dump file
cp /var/lib/redis/dump.rdb /backups/redis_$(date +%Y%m%d).rdb
```

## Scaling

### Horizontal Scaling

1. **Load Balancer**: Add Nginx load balancer
2. **Multiple API Instances**: Run multiple Uvicorn workers
3. **Database Read Replicas**: Set up PostgreSQL replication
4. **Redis Cluster**: For high-availability caching

### Vertical Scaling

1. Increase worker count in Uvicorn
2. Increase PostgreSQL connection pool size
3. Add more Redis memory
4. Upgrade server resources

## Support

For issues and questions:
- Documentation: Check README.md and API docs
- Issues: GitHub Issues
- Email: support@example.com
