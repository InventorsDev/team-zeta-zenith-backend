from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, JSON
from sqlalchemy.sql import func
from app.database.base import Base


class TaskStatus(Base):
    """Model for tracking Celery task status and results"""

    __tablename__ = "task_status"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), unique=True, index=True, nullable=False)
    task_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, PROGRESS, SUCCESS, FAILURE, RETRY, REVOKED
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)

    # Progress tracking
    progress = Column(Float, default=0.0)
    current_step = Column(String(255), nullable=True)
    total_steps = Column(Integer, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Retry information
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Organization context
    organization_id = Column(Integer, nullable=True)

    # Additional metadata
    metadata = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<TaskStatus(id={self.id}, task_id='{self.task_id}', status='{self.status}')>"