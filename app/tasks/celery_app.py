from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "zenith",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.ml_tasks",
        "app.tasks.sync_tasks",
        "app.tasks.ticket_processing",
        "app.tasks.analytics_tasks",
        "app.tasks.alert_tasks",
        "app.tasks.cleanup_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    result_expires=3600,  # 1 hour
    broker_connection_retry_on_startup=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
)

celery_app.conf.beat_schedule = {
    "sync-slack-tickets": {
        "task": "app.tasks.sync_tasks.sync_slack_tickets",
        "schedule": 300.0,  # Every 5 minutes
    },
    "process-email-tickets": {
        "task": "app.tasks.sync_tasks.process_email_tickets",
        "schedule": 600.0,  # Every 10 minutes
    },
    "evaluate-alert-rules": {
        "task": "evaluate_alert_rules",
        "schedule": 300.0,  # Every 5 minutes - evaluate all active alert rules
    },
    "cleanup-old-alerts": {
        "task": "cleanup_old_alerts",
        "schedule": 86400.0,  # Every 24 hours - cleanup old resolved alerts
        "kwargs": {"days": 90},  # Delete alerts older than 90 days
    },
    "cleanup-old-tasks": {
        "task": "app.tasks.cleanup_tasks.cleanup_old_task_results",
        "schedule": 3600.0,  # Every hour
    },
    "train-organization-models": {
        "task": "app.tasks.ml_tasks.train_all_organizations_task",
        "schedule": 86400.0,  # Every 24 hours
    },
}

if __name__ == "__main__":
    celery_app.start()