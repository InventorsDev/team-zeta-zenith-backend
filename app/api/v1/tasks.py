from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database.connection import get_db
from app.services.task_service import TaskService
from app.tasks.ml_tasks import (
    classify_ticket_task,
    train_organization_model_task,
    batch_classify_tickets_task
)
from app.tasks.sync_tasks import (
    sync_slack_tickets,
    process_email_tickets,
    sync_organization_data,
    manual_sync_trigger
)
from app.tasks.cleanup_tasks import (
    cleanup_old_task_results,
    cleanup_failed_tasks,
    health_check_tasks
)
from app.schemas.base import ResponseModel
from app.api.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/status/{task_id}", response_model=ResponseModel)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get status of a specific task"""
    try:
        task_status = TaskService.get_task_status(db, task_id)

        if not task_status:
            raise HTTPException(status_code=404, detail="Task not found")

        return ResponseModel(
            success=True,
            message="Task status retrieved successfully",
            data=task_status
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/organization/{organization_id}", response_model=ResponseModel)
async def get_organization_tasks(
    organization_id: int,
    status_filter: Optional[str] = Query(None, description="Filter by task status"),
    limit: int = Query(50, le=100, description="Maximum number of tasks to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get tasks for a specific organization"""
    try:
        tasks = TaskService.get_organization_tasks(
            db, organization_id, status_filter, limit
        )

        return ResponseModel(
            success=True,
            message="Organization tasks retrieved successfully",
            data={
                "organization_id": organization_id,
                "tasks": tasks,
                "count": len(tasks)
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=ResponseModel)
async def get_active_tasks(
    limit: int = Query(100, le=200, description="Maximum number of tasks to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all currently active tasks"""
    try:
        tasks = TaskService.get_active_tasks(db, limit)

        return ResponseModel(
            success=True,
            message="Active tasks retrieved successfully",
            data={
                "tasks": tasks,
                "count": len(tasks)
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{task_id}", response_model=ResponseModel)
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel a running task"""
    try:
        result = TaskService.cancel_task(db, task_id)

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return ResponseModel(
            success=True,
            message="Task cancelled successfully",
            data=result
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry/{task_id}", response_model=ResponseModel)
async def retry_task(
    task_id: str,
    force: bool = Query(False, description="Force retry even if max retries exceeded"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retry a failed task"""
    try:
        result = TaskService.retry_failed_task(db, task_id, force)

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return ResponseModel(
            success=True,
            message="Task retry initiated successfully",
            data=result
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/classify-ticket", response_model=ResponseModel)
async def trigger_ticket_classification(
    ticket_id: int,
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger ML classification for a specific ticket"""
    try:
        task = classify_ticket_task.delay(ticket_id, organization_id)

        # Create task record
        TaskService.create_task_record(
            db,
            task.id,
            "classify_ticket",
            organization_id,
            {"ticket_id": ticket_id}
        )

        return ResponseModel(
            success=True,
            message="Ticket classification task started",
            data={
                "task_id": task.id,
                "ticket_id": ticket_id,
                "organization_id": organization_id
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/batch-classify", response_model=ResponseModel)
async def trigger_batch_classification(
    ticket_ids: List[int],
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger batch ML classification for multiple tickets"""
    try:
        task = batch_classify_tickets_task.delay(ticket_ids, organization_id)

        # Create task record
        TaskService.create_task_record(
            db,
            task.id,
            "batch_classify_tickets",
            organization_id,
            {"ticket_ids": ticket_ids, "count": len(ticket_ids)}
        )

        return ResponseModel(
            success=True,
            message="Batch classification task started",
            data={
                "task_id": task.id,
                "ticket_count": len(ticket_ids),
                "organization_id": organization_id
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/train-model", response_model=ResponseModel)
async def trigger_model_training(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger ML model training for an organization"""
    try:
        task = train_organization_model_task.delay(organization_id)

        # Create task record
        TaskService.create_task_record(
            db,
            task.id,
            "train_organization_model",
            organization_id,
            {"organization_id": organization_id}
        )

        return ResponseModel(
            success=True,
            message="Model training task started",
            data={
                "task_id": task.id,
                "organization_id": organization_id
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/slack", response_model=ResponseModel)
async def trigger_slack_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger Slack tickets synchronization"""
    try:
        task = sync_slack_tickets.delay()

        # Create task record
        TaskService.create_task_record(
            db,
            task.id,
            "sync_slack_tickets",
            None,
            {"sync_type": "slack"}
        )

        return ResponseModel(
            success=True,
            message="Slack sync task started",
            data={"task_id": task.id}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/email", response_model=ResponseModel)
async def trigger_email_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger email tickets processing"""
    try:
        task = process_email_tickets.delay()

        # Create task record
        TaskService.create_task_record(
            db,
            task.id,
            "process_email_tickets",
            None,
            {"sync_type": "email"}
        )

        return ResponseModel(
            success=True,
            message="Email sync task started",
            data={"task_id": task.id}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/organization/{organization_id}", response_model=ResponseModel)
async def trigger_organization_sync(
    organization_id: int,
    sync_types: Optional[List[str]] = Query(None, description="Sync types: slack, email, all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger synchronization for a specific organization"""
    try:
        if sync_types:
            task = manual_sync_trigger.delay(organization_id, sync_types)
        else:
            task = sync_organization_data.delay(organization_id)

        # Create task record
        TaskService.create_task_record(
            db,
            task.id,
            "sync_organization_data",
            organization_id,
            {"organization_id": organization_id, "sync_types": sync_types}
        )

        return ResponseModel(
            success=True,
            message="Organization sync task started",
            data={
                "task_id": task.id,
                "organization_id": organization_id,
                "sync_types": sync_types
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup/old-tasks", response_model=ResponseModel)
async def trigger_cleanup_old_tasks(
    days: int = Query(7, ge=1, le=30, description="Number of days to keep completed tasks"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger cleanup of old task records"""
    try:
        task = cleanup_old_task_results.delay(days)

        # Create task record
        TaskService.create_task_record(
            db,
            task.id,
            "cleanup_old_task_results",
            None,
            {"cleanup_days": days}
        )

        return ResponseModel(
            success=True,
            message="Cleanup task started",
            data={
                "task_id": task.id,
                "cleanup_days": days
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup/failed-tasks", response_model=ResponseModel)
async def trigger_cleanup_failed_tasks(
    max_age_hours: int = Query(24, ge=1, le=168, description="Max age in hours for stuck tasks"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Trigger cleanup of stuck/failed tasks"""
    try:
        task = cleanup_failed_tasks.delay(max_age_hours)

        # Create task record
        TaskService.create_task_record(
            db,
            task.id,
            "cleanup_failed_tasks",
            None,
            {"max_age_hours": max_age_hours}
        )

        return ResponseModel(
            success=True,
            message="Failed task cleanup started",
            data={
                "task_id": task.id,
                "max_age_hours": max_age_hours
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=ResponseModel)
async def get_task_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get health status of the task system"""
    try:
        task = health_check_tasks.delay()

        # Wait a moment for the health check to complete
        result = task.get(timeout=10)

        return ResponseModel(
            success=True,
            message="Task system health check completed",
            data=result
        )

    except Exception as e:
        # Return partial health info even if full check fails
        return ResponseModel(
            success=False,
            message="Health check failed",
            data={
                "status": "error",
                "error": str(e),
                "timestamp": "N/A"
            }
        )