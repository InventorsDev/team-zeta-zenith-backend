import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from celery import current_task
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.database.connection import get_db
from app.services.task_service import TaskService
from app.models.task_status import TaskStatus

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.cleanup_tasks.cleanup_old_task_results")
def cleanup_old_task_results(self, days: int = 7) -> Dict[str, Any]:
    """
    Clean up old task results and logs.

    Args:
        days: Number of days to keep completed tasks

    Returns:
        Dict containing cleanup results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "initializing", "progress": 10}
        )

        db: Session = next(get_db())

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "cleaning_database", "progress": 30}
        )

        # Clean up database records
        db_cleanup_result = TaskService.cleanup_old_tasks(db, days)

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "cleaning_celery_results", "progress": 60}
        )

        # Clean up Celery result backend
        cutoff_timestamp = datetime.utcnow() - timedelta(days=days)

        # Note: This would typically use celery_app.backend.cleanup()
        # but the implementation depends on the backend type
        celery_cleanup_count = 0
        try:
            # For Redis backend, you might want to implement custom cleanup
            # This is a placeholder for the actual implementation
            celery_cleanup_count = 0  # Implement actual Redis cleanup here
        except Exception as e:
            logger.warning(f"Could not cleanup Celery results: {str(e)}")

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        result = {
            "database_cleanup": db_cleanup_result,
            "celery_cleanup_count": celery_cleanup_count,
            "cutoff_days": days,
            "status": "success"
        }

        logger.info(f"Cleanup completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in cleanup_old_task_results: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise


@celery_app.task(bind=True, name="app.tasks.cleanup_tasks.cleanup_failed_tasks")
def cleanup_failed_tasks(self, max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Clean up tasks that have been stuck in PENDING or PROGRESS state.

    Args:
        max_age_hours: Maximum age in hours for stuck tasks

    Returns:
        Dict containing cleanup results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "initializing", "progress": 10}
        )

        db: Session = next(get_db())

        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "identifying_stuck_tasks", "progress": 30}
        )

        # Find stuck tasks
        stuck_tasks = db.query(TaskStatus).filter(
            TaskStatus.status.in_(["PENDING", "PROGRESS"]),
            TaskStatus.created_at < cutoff_time
        ).all()

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "updating_stuck_tasks", "progress": 60}
        )

        updated_count = 0
        for task in stuck_tasks:
            try:
                # Check if the task is actually still running in Celery
                from celery.result import AsyncResult
                celery_result = AsyncResult(task.task_id, app=celery_app)

                if celery_result.status in ["PENDING", "STARTED"]:
                    # Task might still be running, leave it alone
                    continue

                # Mark as failed
                task.status = "FAILURE"
                task.error_message = f"Task stuck in {task.status} state for {max_age_hours} hours"
                task.completed_at = datetime.utcnow()
                updated_count += 1

            except Exception as e:
                logger.error(f"Error processing stuck task {task.task_id}: {str(e)}")

        db.commit()

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        result = {
            "stuck_tasks_found": len(stuck_tasks),
            "stuck_tasks_updated": updated_count,
            "max_age_hours": max_age_hours,
            "status": "success"
        }

        logger.info(f"Stuck task cleanup completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in cleanup_failed_tasks: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise


@celery_app.task(bind=True, name="app.tasks.cleanup_tasks.health_check_tasks")
def health_check_tasks(self) -> Dict[str, Any]:
    """
    Perform health check on the task system.

    Returns:
        Dict containing health check results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "checking_celery_status", "progress": 20}
        )

        # Check Celery broker connection
        broker_status = "unknown"
        try:
            celery_app.control.ping(timeout=5)
            broker_status = "connected"
        except Exception:
            broker_status = "disconnected"

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "checking_database", "progress": 40}
        )

        # Check database connection
        db_status = "unknown"
        task_count = 0
        try:
            db: Session = next(get_db())
            task_count = db.query(TaskStatus).count()
            db_status = "connected"
        except Exception:
            db_status = "disconnected"

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "checking_worker_status", "progress": 60}
        )

        # Check worker status
        worker_status = "unknown"
        active_workers = 0
        try:
            stats = celery_app.control.stats()
            active_workers = len(stats) if stats else 0
            worker_status = "active" if active_workers > 0 else "no_workers"
        except Exception:
            worker_status = "error"

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "getting_queue_stats", "progress": 80}
        )

        # Get queue statistics
        queue_stats = {}
        try:
            inspect = celery_app.control.inspect()
            queue_stats = {
                "active": inspect.active(),
                "scheduled": inspect.scheduled(),
                "reserved": inspect.reserved()
            }
        except Exception as e:
            logger.warning(f"Could not get queue stats: {str(e)}")

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        result = {
            "broker_status": broker_status,
            "database_status": db_status,
            "worker_status": worker_status,
            "active_workers": active_workers,
            "total_tasks_in_db": task_count,
            "queue_stats": queue_stats,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success"
        }

        logger.info(f"Health check completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in health_check_tasks: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise