import logging
from typing import Dict, Any, Optional
from celery import current_task
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.database.connection import get_db
from app.ml.classification.classifier import TicketClassifier
from app.ml.training.train_classifier import ModelTrainer
from app.models.ticket import Ticket
from app.models.organization import Organization
from app.models.classification import ClassificationResult
from app.services.alert_service import AlertService
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(bind=True, name="app.tasks.ml_tasks.classify_ticket")
def classify_ticket_task(self, ticket_id: int, organization_id: int) -> Dict[str, Any]:
    """
    Asynchronously classify a ticket using ML models.

    Args:
        ticket_id: ID of the ticket to classify
        organization_id: ID of the organization the ticket belongs to

    Returns:
        Dict containing classification results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "initializing", "progress": 10}
        )

        db: Session = next(get_db())

        # Get ticket
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "loading_model", "progress": 30}
        )

        # Initialize classifier
        classifier = TicketClassifier(organization_id=organization_id)

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "classifying", "progress": 60}
        )

        # Perform classification
        classification_result = classifier.classify_ticket(
            subject=ticket.subject,
            description=ticket.description,
            priority=ticket.priority
        )

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "saving_results", "progress": 80}
        )

        # Save classification result to database
        db_classification = ClassificationResult(
            ticket_id=ticket_id,
            category=classification_result.get("category"),
            urgency=classification_result.get("urgency"),
            sentiment=classification_result.get("sentiment"),
            confidence_score=classification_result.get("confidence", 0.0),
            model_version=classification_result.get("model_version"),
            processing_time=classification_result.get("processing_time"),
            metadata=classification_result.get("metadata", {})
        )

        db.add(db_classification)

        # Update ticket with classification results
        ticket.category = classification_result.get("category")
        ticket.urgency = classification_result.get("urgency")
        ticket.sentiment = classification_result.get("sentiment")

        db.commit()

        # Trigger alerts if high urgency
        if classification_result.get("urgency") == "high":
            AlertService.create_urgency_alert(db, ticket_id, classification_result)

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        logger.info(f"Successfully classified ticket {ticket_id}")

        return {
            "ticket_id": ticket_id,
            "classification": classification_result,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error classifying ticket {ticket_id}: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise


@celery_app.task(bind=True, name="app.tasks.ml_tasks.train_organization_model")
def train_organization_model_task(self, organization_id: int) -> Dict[str, Any]:
    """
    Train ML model for a specific organization.

    Args:
        organization_id: ID of the organization to train model for

    Returns:
        Dict containing training results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "initializing", "progress": 5}
        )

        db: Session = next(get_db())

        # Verify organization exists
        organization = db.query(Organization).filter(
            Organization.id == organization_id
        ).first()

        if not organization:
            raise ValueError(f"Organization with ID {organization_id} not found")

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "preparing_data", "progress": 20}
        )

        # Initialize trainer
        trainer = ModelTrainer(organization_id=organization_id)

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "training_model", "progress": 40}
        )

        # Train the model
        training_result = trainer.train_model()

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "evaluating_model", "progress": 70}
        )

        # Evaluate model performance
        evaluation_result = trainer.evaluate_model()

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "saving_model", "progress": 90}
        )

        # Save model
        model_path = trainer.save_model()

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        logger.info(f"Successfully trained model for organization {organization_id}")

        return {
            "organization_id": organization_id,
            "training_result": training_result,
            "evaluation_result": evaluation_result,
            "model_path": model_path,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error training model for organization {organization_id}: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise


@celery_app.task(bind=True, name="app.tasks.ml_tasks.train_all_organizations_task")
def train_all_organizations_task(self) -> Dict[str, Any]:
    """
    Train ML models for all organizations that have sufficient data.

    Returns:
        Dict containing training results for all organizations
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "fetching_organizations", "progress": 10}
        )

        db: Session = next(get_db())

        # Get all organizations
        organizations = db.query(Organization).filter(
            Organization.is_active == True
        ).all()

        if not organizations:
            return {"message": "No active organizations found", "status": "success"}

        results = []
        total_orgs = len(organizations)

        for i, org in enumerate(organizations):
            progress = 10 + int((i / total_orgs) * 80)
            current_task.update_state(
                state="PROGRESS",
                meta={
                    "step": f"training_org_{org.id}",
                    "progress": progress,
                    "current_org": org.name
                }
            )

            try:
                # Check if organization has enough data for training
                ticket_count = db.query(Ticket).filter(
                    Ticket.organization_id == org.id
                ).count()

                if ticket_count < 50:  # Minimum threshold for training
                    logger.info(f"Skipping organization {org.id}: insufficient data ({ticket_count} tickets)")
                    results.append({
                        "organization_id": org.id,
                        "organization_name": org.name,
                        "status": "skipped",
                        "reason": f"Insufficient data: {ticket_count} tickets"
                    })
                    continue

                # Trigger training task for this organization
                training_task = train_organization_model_task.delay(org.id)

                results.append({
                    "organization_id": org.id,
                    "organization_name": org.name,
                    "task_id": training_task.id,
                    "status": "scheduled"
                })

            except Exception as e:
                logger.error(f"Error scheduling training for organization {org.id}: {str(e)}")
                results.append({
                    "organization_id": org.id,
                    "organization_name": org.name,
                    "status": "error",
                    "error": str(e)
                })

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        return {
            "total_organizations": total_orgs,
            "results": results,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error in train_all_organizations_task: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise


@celery_app.task(bind=True, name="app.tasks.ml_tasks.batch_classify_tickets")
def batch_classify_tickets_task(
    self,
    ticket_ids: list[int],
    organization_id: int
) -> Dict[str, Any]:
    """
    Classify multiple tickets in batch for better performance.

    Args:
        ticket_ids: List of ticket IDs to classify
        organization_id: ID of the organization

    Returns:
        Dict containing batch classification results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "initializing", "progress": 5}
        )

        db: Session = next(get_db())

        # Initialize classifier once for all tickets
        classifier = TicketClassifier(organization_id=organization_id)

        results = []
        total_tickets = len(ticket_ids)

        for i, ticket_id in enumerate(ticket_ids):
            progress = 5 + int((i / total_tickets) * 90)
            current_task.update_state(
                state="PROGRESS",
                meta={
                    "step": f"classifying_ticket_{ticket_id}",
                    "progress": progress,
                    "processed": i,
                    "total": total_tickets
                }
            )

            try:
                # Trigger individual classification task
                classification_task = classify_ticket_task.delay(ticket_id, organization_id)

                results.append({
                    "ticket_id": ticket_id,
                    "task_id": classification_task.id,
                    "status": "scheduled"
                })

            except Exception as e:
                logger.error(f"Error scheduling classification for ticket {ticket_id}: {str(e)}")
                results.append({
                    "ticket_id": ticket_id,
                    "status": "error",
                    "error": str(e)
                })

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        return {
            "total_tickets": total_tickets,
            "results": results,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error in batch_classify_tickets_task: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise