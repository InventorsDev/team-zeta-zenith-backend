import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from celery import current_task
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.database.connection import get_db
from app.integrations.slack.sync import SlackSyncService
from app.integrations.email.parser import EmailProcessor
from app.models.organization import Organization
from app.models.ticket import Ticket
from app.models.integration import SlackIntegration
from app.models.email_integration import EmailIntegration
from app.tasks.ml_tasks import classify_ticket_task

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.sync_tasks.sync_slack_tickets")
def sync_slack_tickets(self) -> Dict[str, Any]:
    """
    Synchronize tickets from all active Slack integrations.

    Returns:
        Dict containing sync results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "fetching_integrations", "progress": 10}
        )

        db: Session = next(get_db())

        # Get all active Slack integrations
        slack_integrations = db.query(SlackIntegration).filter(
            SlackIntegration.is_active == True
        ).all()

        if not slack_integrations:
            return {"message": "No active Slack integrations found", "status": "success"}

        results = []
        total_integrations = len(slack_integrations)

        for i, integration in enumerate(slack_integrations):
            progress = 10 + int((i / total_integrations) * 80)
            current_task.update_state(
                state="PROGRESS",
                meta={
                    "step": f"syncing_slack_{integration.id}",
                    "progress": progress,
                    "current_integration": integration.workspace_name
                }
            )

            try:
                # Initialize Slack sync service
                slack_sync = SlackSyncService(integration)

                # Sync tickets from the last sync time or last 24 hours
                last_sync = integration.last_sync_at or (datetime.utcnow() - timedelta(hours=24))
                sync_result = slack_sync.sync_tickets_since(last_sync)

                # Update last sync time
                integration.last_sync_at = datetime.utcnow()
                db.commit()

                # Trigger ML classification for new tickets
                for ticket_id in sync_result.get("new_ticket_ids", []):
                    classify_ticket_task.delay(ticket_id, integration.organization_id)

                results.append({
                    "integration_id": integration.id,
                    "workspace_name": integration.workspace_name,
                    "organization_id": integration.organization_id,
                    "new_tickets": len(sync_result.get("new_ticket_ids", [])),
                    "updated_tickets": len(sync_result.get("updated_ticket_ids", [])),
                    "status": "success"
                })

            except Exception as e:
                logger.error(f"Error syncing Slack integration {integration.id}: {str(e)}")
                results.append({
                    "integration_id": integration.id,
                    "workspace_name": integration.workspace_name,
                    "organization_id": integration.organization_id,
                    "status": "error",
                    "error": str(e)
                })

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        return {
            "total_integrations": total_integrations,
            "results": results,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error in sync_slack_tickets: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise


@celery_app.task(bind=True, name="app.tasks.sync_tasks.process_email_tickets")
def process_email_tickets(self) -> Dict[str, Any]:
    """
    Process emails from all active email integrations and create tickets.

    Returns:
        Dict containing processing results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "fetching_integrations", "progress": 10}
        )

        db: Session = next(get_db())

        # Get all active email integrations
        email_integrations = db.query(EmailIntegration).filter(
            EmailIntegration.is_active == True
        ).all()

        if not email_integrations:
            return {"message": "No active email integrations found", "status": "success"}

        results = []
        total_integrations = len(email_integrations)

        for i, integration in enumerate(email_integrations):
            progress = 10 + int((i / total_integrations) * 80)
            current_task.update_state(
                state="PROGRESS",
                meta={
                    "step": f"processing_email_{integration.id}",
                    "progress": progress,
                    "current_integration": integration.email_address
                }
            )

            try:
                # Initialize email processor
                email_processor = EmailProcessor(integration)

                # Process emails from the last sync time or last 24 hours
                last_sync = integration.last_sync_at or (datetime.utcnow() - timedelta(hours=24))
                processing_result = email_processor.process_emails_since(last_sync)

                # Update last sync time
                integration.last_sync_at = datetime.utcnow()
                db.commit()

                # Trigger ML classification for new tickets
                for ticket_id in processing_result.get("new_ticket_ids", []):
                    classify_ticket_task.delay(ticket_id, integration.organization_id)

                results.append({
                    "integration_id": integration.id,
                    "email_address": integration.email_address,
                    "organization_id": integration.organization_id,
                    "new_tickets": len(processing_result.get("new_ticket_ids", [])),
                    "processed_emails": processing_result.get("processed_count", 0),
                    "status": "success"
                })

            except Exception as e:
                logger.error(f"Error processing email integration {integration.id}: {str(e)}")
                results.append({
                    "integration_id": integration.id,
                    "email_address": integration.email_address,
                    "organization_id": integration.organization_id,
                    "status": "error",
                    "error": str(e)
                })

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        return {
            "total_integrations": total_integrations,
            "results": results,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error in process_email_tickets: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise


@celery_app.task(bind=True, name="app.tasks.sync_tasks.sync_organization_data")
def sync_organization_data(self, organization_id: int) -> Dict[str, Any]:
    """
    Sync all data for a specific organization.

    Args:
        organization_id: ID of the organization to sync

    Returns:
        Dict containing sync results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "initializing", "progress": 10}
        )

        db: Session = next(get_db())

        # Verify organization exists
        organization = db.query(Organization).filter(
            Organization.id == organization_id
        ).first()

        if not organization:
            raise ValueError(f"Organization with ID {organization_id} not found")

        results = {
            "organization_id": organization_id,
            "organization_name": organization.name,
            "slack_sync": None,
            "email_sync": None,
            "status": "success"
        }

        # Sync Slack integrations
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "syncing_slack", "progress": 30}
        )

        slack_integrations = db.query(SlackIntegration).filter(
            SlackIntegration.organization_id == organization_id,
            SlackIntegration.is_active == True
        ).all()

        if slack_integrations:
            slack_results = []
            for integration in slack_integrations:
                try:
                    slack_sync = SlackSyncService(integration)
                    last_sync = integration.last_sync_at or (datetime.utcnow() - timedelta(hours=24))
                    sync_result = slack_sync.sync_tickets_since(last_sync)

                    integration.last_sync_at = datetime.utcnow()
                    db.commit()

                    # Trigger ML classification for new tickets
                    for ticket_id in sync_result.get("new_ticket_ids", []):
                        classify_ticket_task.delay(ticket_id, organization_id)

                    slack_results.append({
                        "integration_id": integration.id,
                        "workspace_name": integration.workspace_name,
                        "new_tickets": len(sync_result.get("new_ticket_ids", [])),
                        "status": "success"
                    })

                except Exception as e:
                    slack_results.append({
                        "integration_id": integration.id,
                        "workspace_name": integration.workspace_name,
                        "status": "error",
                        "error": str(e)
                    })

            results["slack_sync"] = slack_results

        # Sync Email integrations
        current_task.update_state(
            state="PROGRESS",
            meta={"step": "syncing_email", "progress": 60}
        )

        email_integrations = db.query(EmailIntegration).filter(
            EmailIntegration.organization_id == organization_id,
            EmailIntegration.is_active == True
        ).all()

        if email_integrations:
            email_results = []
            for integration in email_integrations:
                try:
                    email_processor = EmailProcessor(integration)
                    last_sync = integration.last_sync_at or (datetime.utcnow() - timedelta(hours=24))
                    processing_result = email_processor.process_emails_since(last_sync)

                    integration.last_sync_at = datetime.utcnow()
                    db.commit()

                    # Trigger ML classification for new tickets
                    for ticket_id in processing_result.get("new_ticket_ids", []):
                        classify_ticket_task.delay(ticket_id, organization_id)

                    email_results.append({
                        "integration_id": integration.id,
                        "email_address": integration.email_address,
                        "new_tickets": len(processing_result.get("new_ticket_ids", [])),
                        "status": "success"
                    })

                except Exception as e:
                    email_results.append({
                        "integration_id": integration.id,
                        "email_address": integration.email_address,
                        "status": "error",
                        "error": str(e)
                    })

            results["email_sync"] = email_results

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        return results

    except Exception as e:
        logger.error(f"Error syncing organization {organization_id}: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise


@celery_app.task(bind=True, name="app.tasks.sync_tasks.manual_sync_trigger")
def manual_sync_trigger(
    self,
    organization_id: int,
    sync_types: List[str] = None
) -> Dict[str, Any]:
    """
    Manually trigger sync for specific organization and sync types.

    Args:
        organization_id: ID of the organization to sync
        sync_types: List of sync types to perform ['slack', 'email', 'all']

    Returns:
        Dict containing sync results
    """
    try:
        if sync_types is None:
            sync_types = ["all"]

        current_task.update_state(
            state="PROGRESS",
            meta={"step": "validating_request", "progress": 10}
        )

        if "all" in sync_types:
            # Trigger full organization sync
            sync_task = sync_organization_data.delay(organization_id)
            return {
                "organization_id": organization_id,
                "sync_task_id": sync_task.id,
                "sync_types": sync_types,
                "status": "scheduled"
            }

        # Trigger specific sync types
        task_results = []

        if "slack" in sync_types:
            current_task.update_state(
                state="PROGRESS",
                meta={"step": "triggering_slack_sync", "progress": 40}
            )
            slack_task = sync_slack_tickets.delay()
            task_results.append({
                "type": "slack",
                "task_id": slack_task.id
            })

        if "email" in sync_types:
            current_task.update_state(
                state="PROGRESS",
                meta={"step": "triggering_email_sync", "progress": 70}
            )
            email_task = process_email_tickets.delay()
            task_results.append({
                "type": "email",
                "task_id": email_task.id
            })

        current_task.update_state(
            state="SUCCESS",
            meta={"step": "completed", "progress": 100}
        )

        return {
            "organization_id": organization_id,
            "sync_types": sync_types,
            "scheduled_tasks": task_results,
            "status": "scheduled"
        }

    except Exception as e:
        logger.error(f"Error in manual_sync_trigger: {str(e)}")
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise