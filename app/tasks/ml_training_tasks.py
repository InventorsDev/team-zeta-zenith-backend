"""
ML Training Background Tasks
Handles periodic training of ML models
"""

import logging
from typing import Optional, Dict, Any
from celery import shared_task
from datetime import datetime

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def train_similarity_detector_task(self, organization_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Celery task to train similarity detector with existing tickets
    
    Args:
        organization_id: Optional organization ID to limit training scope
        
    Returns:
        Training results dictionary
    """
    try:
        from app.services.ml_service import ml_service
        
        logger.info(f"Starting scheduled similarity detector training for org: {organization_id}")
        start_time = datetime.utcnow()
        
        # Train the similarity detector
        result = ml_service.train_similarity_detector(organization_id)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        if result["success"]:
            logger.info(
                f"Scheduled similarity training completed successfully: "
                f"{result['tickets_processed']} tickets processed in {duration:.2f}s, "
                f"found {result.get('duplicates_found', 0)} potential duplicates"
            )
        else:
            logger.error(f"Scheduled similarity training failed: {result['error']}")
        
        # Add task metadata
        result.update({
            "task_id": self.request.id,
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "total_duration_seconds": duration
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Similarity detector training task failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "tickets_processed": 0,
            "task_id": self.request.id,
            "failed_at": datetime.utcnow().isoformat()
        }

@shared_task(bind=True)
def train_all_organizations_task(self) -> Dict[str, Any]:
    """
    Train similarity detector for all organizations separately
    
    Returns:
        Summary of training results for all organizations
    """
    try:
        from app.database.repositories.organization_repository import OrganizationRepository
        from app.database.connection import get_db
        from app.services.ml_service import ml_service
        
        logger.info("Starting similarity detector training for all organizations")
        start_time = datetime.utcnow()
        
        # Get database session
        db = next(get_db())
        org_repo = OrganizationRepository(db)
        
        # Get all active organizations
        organizations = org_repo.get_all(skip=0, limit=1000)
        active_orgs = [org for org in organizations if org.is_active]
        
        results = {
            "task_id": self.request.id,
            "started_at": start_time.isoformat(),
            "total_organizations": len(active_orgs),
            "organization_results": [],
            "summary": {
                "successful": 0,
                "failed": 0,
                "total_tickets_processed": 0,
                "total_duplicates_found": 0
            }
        }
        
        # Train for each organization
        for org in active_orgs:
            org_start = datetime.utcnow()
            org_result = ml_service.train_similarity_detector(org.id)
            org_end = datetime.utcnow()
            
            org_result.update({
                "organization_name": org.name,
                "organization_slug": org.slug,
                "duration_seconds": (org_end - org_start).total_seconds()
            })
            
            results["organization_results"].append(org_result)
            
            if org_result["success"]:
                results["summary"]["successful"] += 1
                results["summary"]["total_tickets_processed"] += org_result["tickets_processed"]
                results["summary"]["total_duplicates_found"] += org_result.get("duplicates_found", 0)
            else:
                results["summary"]["failed"] += 1
            
            logger.info(
                f"Organization {org.name} training: "
                f"{'SUCCESS' if org_result['success'] else 'FAILED'} - "
                f"{org_result['tickets_processed']} tickets"
            )
        
        # Global training (across all organizations)
        logger.info("Starting global similarity detector training")
        global_result = ml_service.train_similarity_detector(None)  # None = all orgs
        global_result["scope"] = "global"
        results["global_training"] = global_result
        
        end_time = datetime.utcnow()
        total_duration = (end_time - start_time).total_seconds()
        
        results.update({
            "completed_at": end_time.isoformat(),
            "total_duration_seconds": total_duration
        })
        
        logger.info(
            f"All organizations training completed: "
            f"{results['summary']['successful']}/{results['total_organizations']} successful, "
            f"{results['summary']['total_tickets_processed']} total tickets processed"
        )
        
        return results
        
    except Exception as e:
        logger.error(f"All organizations training task failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id,
            "failed_at": datetime.utcnow().isoformat()
        }
    finally:
        if 'db' in locals():
            db.close()

@shared_task
def daily_ml_training() -> Dict[str, Any]:
    """
    Daily scheduled task to train ML models
    This is the main task that should be scheduled via cron
    """
    logger.info("Starting daily ML training job")
    
    try:
        # For now, just train similarity detector globally
        # Can be extended to include other ML model training
        result = train_similarity_detector_task.delay(None)  # Global training
        
        return {
            "message": "Daily ML training started",
            "task_id": result.id,
            "scheduled_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to start daily ML training: {e}")
        return {
            "error": str(e),
            "failed_at": datetime.utcnow().isoformat()
        }