# Celery Setup for Team Zeta Zenith Backend

This document explains how to set up and use Celery for asynchronous task processing in the Team Zeta Zenith backend application.

## Overview

The application uses Celery with Redis as the message broker for:
- ML classification of tickets
- Background synchronization with external services (Slack, Email)
- Scheduled data processing tasks
- Model training and retraining
- System maintenance and cleanup

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  Celery Worker  │    │     Redis       │
│                 │    │                 │    │                 │
│  - Web API      │◄──►│  - ML Tasks     │◄──►│  - Broker       │
│  - Task Trigger │    │  - Sync Tasks   │    │  - Results      │
│  - Monitoring   │    │  - Cleanup      │    │  - Cache        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  Celery Beat    │
                       │                 │
                       │  - Scheduler    │
                       │  - Periodic     │
                       │    Tasks        │
                       └─────────────────┘
```

## Configuration

### Environment Variables

Required environment variables in `.env`:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/zenith
# OR for development
DATABASE_URL=sqlite:///./zenith.db
```

### Celery Settings

The Celery app is configured in `app/tasks/celery_app.py` with:
- JSON serialization for tasks and results
- 30-minute task time limits
- Result expiration after 1 hour
- Automatic retry on broker connection issues

## Task Types

### 1. ML Processing Tasks (`app/tasks/ml_tasks.py`)

- `classify_ticket_task`: Classify individual tickets
- `batch_classify_tickets_task`: Classify multiple tickets
- `train_organization_model_task`: Train model for organization
- `train_all_organizations_task`: Train models for all organizations

### 2. Sync Tasks (`app/tasks/sync_tasks.py`)

- `sync_slack_tickets`: Sync tickets from Slack
- `process_email_tickets`: Process email tickets
- `sync_organization_data`: Full organization sync
- `manual_sync_trigger`: Manual sync trigger

### 3. Cleanup Tasks (`app/tasks/cleanup_tasks.py`)

- `cleanup_old_task_results`: Remove old task records
- `cleanup_failed_tasks`: Handle stuck tasks
- `health_check_tasks`: System health monitoring

## Scheduled Tasks

Celery Beat runs these tasks automatically:

| Task | Schedule | Description |
|------|----------|-------------|
| `sync_slack_tickets` | Every 5 minutes | Sync Slack messages |
| `process_email_tickets` | Every 10 minutes | Process emails |
| `cleanup_old_task_results` | Every hour | Clean old records |
| `train_all_organizations_task` | Daily | Retrain models |

## Running with Docker

### Development Setup

```bash
# Start all services (Redis, FastAPI, Celery worker, Beat, Flower)
docker-compose -f docker-compose.dev.yml up

# Or start individual services
docker-compose -f docker-compose.dev.yml up redis
docker-compose -f docker-compose.dev.yml up backend
docker-compose -f docker-compose.dev.yml up celery_worker
```

### Production Setup

```bash
# Start all services with PostgreSQL
docker-compose up -d

# Scale workers
docker-compose up -d --scale celery_worker=3
```

## Running Manually (Development)

### Start Redis
```bash
redis-server
```

### Start Celery Worker
```bash
# General worker
python scripts/start_celery_worker.py worker --worker-type general

# ML worker (for intensive tasks)
python scripts/start_celery_worker.py worker --worker-type ml --concurrency 1

# Sync worker (for integrations)
python scripts/start_celery_worker.py worker --worker-type sync
```

### Start Celery Beat (Scheduler)
```bash
python scripts/start_celery_worker.py beat
```

### Start Flower (Monitoring)
```bash
python scripts/start_celery_worker.py flower --port 5555
```

## Monitoring

### API Endpoints

The application provides REST endpoints for task monitoring:

- `GET /api/v1/tasks/status/{task_id}` - Get task status
- `GET /api/v1/tasks/organization/{org_id}` - Get organization tasks
- `GET /api/v1/tasks/active` - Get active tasks
- `POST /api/v1/tasks/cancel/{task_id}` - Cancel task
- `POST /api/v1/tasks/retry/{task_id}` - Retry failed task
- `GET /api/v1/tasks/health` - System health check

### Flower Dashboard

Access Flower at http://localhost:5555 to monitor:
- Active workers
- Task queues
- Task history
- Worker statistics
- Broker status

### Task Triggering Endpoints

- `POST /api/v1/tasks/ml/classify-ticket` - Trigger ticket classification
- `POST /api/v1/tasks/ml/batch-classify` - Batch classification
- `POST /api/v1/tasks/ml/train-model` - Train organization model
- `POST /api/v1/tasks/sync/slack` - Manual Slack sync
- `POST /api/v1/tasks/sync/email` - Manual email sync

## Error Handling

### Retry Logic

Tasks automatically retry with exponential backoff:
- Default: 3 retries
- Retry delay: 60 seconds, then 120, then 180
- Failed tasks are logged with full tracebacks

### Monitoring Failed Tasks

```bash
# Check failed tasks
curl http://localhost:8000/api/v1/tasks/active

# Retry specific task
curl -X POST http://localhost:8000/api/v1/tasks/retry/task-id
```

### Stuck Task Cleanup

The system automatically identifies and handles stuck tasks:
- Tasks stuck in PENDING/PROGRESS for >24 hours are marked as failed
- Cleanup runs hourly via scheduled task

## Performance Tuning

### Worker Configuration

For different workloads:

```bash
# CPU-intensive ML tasks
celery -A app.tasks.celery_app worker --concurrency=1 --queues=ml_tasks

# I/O-bound sync tasks
celery -A app.tasks.celery_app worker --concurrency=4 --queues=sync_tasks

# General tasks
celery -A app.tasks.celery_app worker --concurrency=2
```

### Resource Limits (Docker)

```yaml
# In docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '2.0'
    reservations:
      memory: 2G
      cpus: '1.0'
```

## Troubleshooting

### Common Issues

1. **Celery worker not starting**
   - Check Redis connection
   - Verify environment variables
   - Check logs: `docker-compose logs celery_worker`

2. **Tasks not executing**
   - Verify worker is consuming from correct queue
   - Check broker connectivity
   - Review task routing configuration

3. **High memory usage**
   - Reduce worker concurrency
   - Implement task result cleanup
   - Monitor for memory leaks in ML models

4. **Database connection errors**
   - Ensure database is accessible from worker containers
   - Check connection pooling settings
   - Verify database credentials

### Debugging

```bash
# View worker logs
docker-compose logs -f celery_worker

# Check task status via API
curl http://localhost:8000/api/v1/tasks/status/task-id

# Monitor Redis
redis-cli monitor

# Celery inspect commands
celery -A app.tasks.celery_app inspect active
celery -A app.tasks.celery_app inspect stats
```

## Security Considerations

1. **Network isolation**: Use Docker networks
2. **Credential management**: Store sensitive data in environment variables
3. **Resource limits**: Prevent resource exhaustion
4. **Access control**: Secure monitoring endpoints
5. **Data encryption**: Use Redis AUTH and SSL in production

## Next Steps

1. Set up monitoring and alerting for failed tasks
2. Implement custom task routing for different priorities
3. Add metrics collection and dashboards
4. Configure log aggregation for distributed workers
5. Implement task result persistence for audit trails