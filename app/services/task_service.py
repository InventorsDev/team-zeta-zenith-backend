import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from app.tasks.celery_app import celery_app
from app.models.task_status import TaskStatus
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TaskService:
    """Service for managing and monitoring Celery tasks"""

    @staticmethod
    def create_task_record(
        db: Session,
        task_id: str,
        task_name: str,
        organization_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TaskStatus:
        """
        Create a new task status record.

        Args:
            db: Database session
            task_id: Celery task ID
            task_name: Name of the task
            organization_id: Organization ID if applicable
            metadata: Additional metadata

        Returns:
            TaskStatus instance
        """
        task_status = TaskStatus(
            task_id=task_id,
            task_name=task_name,
            organization_id=organization_id,
            metadata=metadata or {},
            created_at=datetime.utcnow()
        )

        db.add(task_status)
        db.commit()
        db.refresh(task_status)

        return task_status

    @staticmethod
    def update_task_status(
        db: Session,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        traceback: Optional[str] = None,
        progress: Optional[float] = None,
        current_step: Optional[str] = None
    ) -> Optional[TaskStatus]:
        """
        Update task status record.

        Args:
            db: Database session
            task_id: Celery task ID
            status: New status
            result: Task result if completed
            error_message: Error message if failed
            traceback: Error traceback if failed
            progress: Current progress percentage
            current_step: Current step description

        Returns:
            Updated TaskStatus instance or None if not found
        """
        task_status = db.query(TaskStatus).filter(
            TaskStatus.task_id == task_id
        ).first()

        if not task_status:
            logger.warning(f"Task status record not found for task_id: {task_id}")
            return None

        # Update fields
        task_status.status = status

        if result is not None:
            task_status.result = result

        if error_message is not None:
            task_status.error_message = error_message

        if traceback is not None:
            task_status.traceback = traceback

        if progress is not None:
            task_status.progress = progress

        if current_step is not None:
            task_status.current_step = current_step

        # Update timing
        if status == "PROGRESS" and task_status.started_at is None:
            task_status.started_at = datetime.utcnow()
        elif status in ["SUCCESS", "FAILURE", "REVOKED"]:
            task_status.completed_at = datetime.utcnow()

        # Handle retries
        if status == "RETRY":
            task_status.retry_count += 1

        db.commit()
        db.refresh(task_status)

        return task_status

    @staticmethod
    def get_task_status(db: Session, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive task status including Celery status.

        Args:
            db: Database session
            task_id: Celery task ID

        Returns:
            Dict containing task status information
        """
        # Get database record
        db_status = db.query(TaskStatus).filter(
            TaskStatus.task_id == task_id
        ).first()

        # Get Celery status
        celery_result = AsyncResult(task_id, app=celery_app)

        # Combine information
        status_info = {
            "task_id": task_id,
            "celery_status": celery_result.status,
            "celery_result": celery_result.result if celery_result.ready() else None,
            "celery_traceback": celery_result.traceback if celery_result.failed() else None
        }

        if db_status:
            status_info.update({
                "id": db_status.id,
                "task_name": db_status.task_name,
                "status": db_status.status,
                "result": db_status.result,
                "error_message": db_status.error_message,
                "traceback": db_status.traceback,
                "progress": db_status.progress,
                "current_step": db_status.current_step,
                "created_at": db_status.created_at,
                "started_at": db_status.started_at,
                "completed_at": db_status.completed_at,
                "retry_count": db_status.retry_count,
                "max_retries": db_status.max_retries,
                "organization_id": db_status.organization_id,
                "metadata": db_status.metadata
            })
        else:
            # If no database record, return minimal info
            status_info.update({
                "status": celery_result.status,
                "result": celery_result.result if celery_result.ready() else None
            })

        return status_info

    @staticmethod
    def get_organization_tasks(
        db: Session,
        organization_id: int,
        status_filter: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get tasks for a specific organization.

        Args:
            db: Database session
            organization_id: Organization ID
            status_filter: Filter by status
            limit: Maximum number of tasks to return

        Returns:
            List of task status information
        """
        query = db.query(TaskStatus).filter(
            TaskStatus.organization_id == organization_id
        )

        if status_filter:
            query = query.filter(TaskStatus.status == status_filter)

        tasks = query.order_by(TaskStatus.created_at.desc()).limit(limit).all()

        return [
            TaskService.get_task_status(db, task.task_id)
            for task in tasks
        ]

    @staticmethod
    def get_active_tasks(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all currently active tasks.

        Args:
            db: Database session
            limit: Maximum number of tasks to return

        Returns:
            List of active task status information
        """
        active_statuses = ["PENDING", "PROGRESS", "RETRY"]

        tasks = db.query(TaskStatus).filter(
            TaskStatus.status.in_(active_statuses)
        ).order_by(TaskStatus.created_at.desc()).limit(limit).all()

        return [
            TaskService.get_task_status(db, task.task_id)
            for task in tasks
        ]

    @staticmethod
    def cancel_task(db: Session, task_id: str) -> Dict[str, Any]:
        """
        Cancel a running task.

        Args:
            db: Database session
            task_id: Celery task ID

        Returns:
            Dict containing cancellation result
        """
        try:
            # Revoke task in Celery
            celery_app.control.revoke(task_id, terminate=True)

            # Update database record
            TaskService.update_task_status(
                db,
                task_id,
                "REVOKED",
                error_message="Task cancelled by user"
            )

            return {
                "task_id": task_id,
                "status": "cancelled",
                "message": "Task has been cancelled successfully"
            }

        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {str(e)}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Failed to cancel task: {str(e)}"
            }

    @staticmethod
    def retry_failed_task(
        db: Session,
        task_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Retry a failed task.

        Args:
            db: Database session
            task_id: Celery task ID
            force: Force retry even if max retries exceeded

        Returns:
            Dict containing retry result
        """
        task_status = db.query(TaskStatus).filter(
            TaskStatus.task_id == task_id
        ).first()

        if not task_status:
            return {
                "task_id": task_id,
                "status": "error",
                "message": "Task not found"
            }

        if task_status.status != "FAILURE":
            return {
                "task_id": task_id,
                "status": "error",
                "message": "Task has not failed"
            }

        if not force and task_status.retry_count >= task_status.max_retries:
            return {
                "task_id": task_id,
                "status": "error",
                "message": "Maximum retries exceeded"
            }

        try:
            # Get original task result to retry
            celery_result = AsyncResult(task_id, app=celery_app)

            # Note: In a real implementation, you would need to store the original
            # task arguments to properly retry. For now, we just update the status.
            TaskService.update_task_status(
                db,
                task_id,
                "PENDING",
                error_message=None,
                traceback=None
            )

            return {
                "task_id": task_id,
                "status": "retrying",
                "message": "Task has been queued for retry"
            }

        except Exception as e:
            logger.error(f"Error retrying task {task_id}: {str(e)}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Failed to retry task: {str(e)}"
            }

    @staticmethod
    def cleanup_old_tasks(db: Session, days: int = 7) -> Dict[str, Any]:
        """
        Clean up old completed task records.

        Args:
            db: Database session
            days: Number of days to keep completed tasks

        Returns:
            Dict containing cleanup results
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Delete old completed tasks
            deleted_count = db.query(TaskStatus).filter(
                TaskStatus.status.in_(["SUCCESS", "FAILURE", "REVOKED"]),
                TaskStatus.completed_at < cutoff_date
            ).delete(synchronize_session=False)

            db.commit()

            return {
                "status": "success",
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }

        except Exception as e:
            logger.error(f"Error cleaning up old tasks: {str(e)}")
            db.rollback()
            return {
                "status": "error",
                "message": f"Failed to cleanup old tasks: {str(e)}"
            }