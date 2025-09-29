"""
Slack message synchronization service
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.integrations.slack.client import SlackClient
from app.integrations.slack.models import SlackSyncResult, SlackMessage, SlackThread
from app.services.ticket_service import TicketService
from app.services.integration_service import IntegrationService
from app.schemas.ticket import TicketCreate
from app.models.ticket import TicketPriority, TicketStatus
from app.database.connection import get_db

logger = logging.getLogger(__name__)


class SlackSyncService:
    """
    Service for synchronizing Slack messages as tickets
    """

    def __init__(self, slack_client: SlackClient, db: Optional[Session] = None):
        self.slack_client = slack_client
        self.db = db or next(get_db())
        self.ticket_service = TicketService(self.db)
        self.integration_service = IntegrationService(self.db)

    def sync_messages(self, full_sync: bool = False, organization_id: Optional[int] = None) -> SlackSyncResult:
        """
        Synchronize messages from monitored Slack channels

        Args:
            full_sync: If True, sync all available messages. If False, sync recent messages.
            organization_id: Organization ID for ticket creation

        Returns:
            SlackSyncResult with sync statistics
        """
        start_time = datetime.utcnow()
        result = SlackSyncResult(
            sync_type='full' if full_sync else 'incremental',
            channels_processed=0,
            total_messages_fetched=0,
            total_messages_processed=0,
            total_tickets_created=0,
            total_tickets_updated=0,
            total_threads_processed=0,
            total_errors=0,
            errors=[],
            duration_seconds=0,
            start_time=start_time,
            end_time=start_time
        )

        try:
            logger.info(f"Starting Slack sync ({result.sync_type})")

            # Get organization ID if not provided
            if not organization_id:
                organization_id = self._get_organization_id()

            if not organization_id:
                raise ValueError("Organization ID required for ticket creation")

            # Get monitored channels
            monitored_channels = self._get_monitored_channels()
            if not monitored_channels:
                logger.warning("No monitored channels configured, will sync all accessible channels")
                monitored_channels = self._get_all_accessible_channels()

            logger.info(f"Syncing {len(monitored_channels)} channels")

            # Determine time range for sync
            oldest_timestamp = None
            if not full_sync:
                # Incremental sync: last 24 hours
                oldest_timestamp = self._get_incremental_sync_timestamp()

            # Process each channel
            for channel_id in monitored_channels:
                try:
                    channel_result = self._sync_channel(
                        channel_id,
                        oldest_timestamp,
                        organization_id
                    )

                    # Update totals
                    result.channels_processed += 1
                    result.total_messages_fetched += channel_result['messages_fetched']
                    result.total_messages_processed += channel_result['messages_processed']
                    result.total_tickets_created += channel_result['tickets_created']
                    result.total_tickets_updated += channel_result['tickets_updated']
                    result.total_threads_processed += channel_result['threads_processed']
                    result.total_errors += len(channel_result['errors'])
                    result.errors.extend(channel_result['errors'])

                except Exception as e:
                    error_msg = f"Error syncing channel {channel_id}: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    result.total_errors += 1

            # Calculate duration
            result.end_time = datetime.utcnow()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()

            logger.info(f"Slack sync completed: {result.total_tickets_created} tickets created, "
                       f"{result.total_tickets_updated} updated, {result.total_errors} errors")

            return result

        except Exception as e:
            result.end_time = datetime.utcnow()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            error_msg = f"Slack sync failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            result.total_errors += 1
            return result

    def _sync_channel(
        self,
        channel_id: str,
        oldest_timestamp: Optional[str],
        organization_id: int
    ) -> Dict[str, Any]:
        """Sync messages from a specific channel"""
        result = {
            'messages_fetched': 0,
            'messages_processed': 0,
            'tickets_created': 0,
            'tickets_updated': 0,
            'threads_processed': 0,
            'errors': []
        }

        try:
            logger.info(f"Syncing channel {channel_id}")

            # Get channel info
            channels = self.slack_client.get_channels()
            channel_info = next((c for c in channels if c.id == channel_id), None)
            channel_name = channel_info.name if channel_info else channel_id

            # Ensure bot is in channel
            if channel_info and not channel_info.is_member:
                join_success = self.slack_client.join_channel(channel_id)
                if not join_success:
                    logger.warning(f"Could not join channel {channel_id}")

            # Get message history
            messages = list(self.slack_client.get_channel_history(
                channel_id=channel_id,
                oldest=oldest_timestamp,
                limit=1000  # Process in batches
            ))

            result['messages_fetched'] = len(messages)
            logger.info(f"Fetched {len(messages)} messages from {channel_name}")

            # Group messages by threads
            threads = self._group_messages_by_threads(messages)

            # Process threads
            for thread_key, thread_messages in threads.items():
                try:
                    thread_result = self._process_thread(
                        thread_messages,
                        channel_id,
                        channel_name,
                        organization_id
                    )

                    result['messages_processed'] += thread_result['messages_processed']
                    result['tickets_created'] += thread_result['tickets_created']
                    result['tickets_updated'] += thread_result['tickets_updated']
                    result['threads_processed'] += 1

                except Exception as e:
                    error_msg = f"Error processing thread {thread_key}: {str(e)}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)

            return result

        except Exception as e:
            error_msg = f"Error syncing channel {channel_id}: {str(e)}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
            return result

    def _group_messages_by_threads(self, messages: List[SlackMessage]) -> Dict[str, List[SlackMessage]]:
        """Group messages by threads"""
        threads = {}

        for message in messages:
            # Skip bot messages and system messages unless configured
            if self._should_skip_message(message):
                continue

            # Determine thread key
            if message.thread_ts:
                # This is part of a thread
                thread_key = message.thread_ts
            else:
                # This is a standalone message or thread parent
                thread_key = message.ts

            if thread_key not in threads:
                threads[thread_key] = []

            threads[thread_key].append(message)

        # Sort messages within each thread by timestamp
        for thread_key in threads:
            threads[thread_key].sort(key=lambda m: float(m.ts))

        return threads

    def _process_thread(
        self,
        messages: List[SlackMessage],
        channel_id: str,
        channel_name: str,
        organization_id: int
    ) -> Dict[str, Any]:
        """Process a thread of messages"""
        result = {
            'messages_processed': 0,
            'tickets_created': 0,
            'tickets_updated': 0
        }

        if not messages:
            return result

        # First message is the thread parent
        parent_message = messages[0]
        replies = messages[1:] if len(messages) > 1 else []

        # Check if ticket already exists
        external_id = f"slack_{parent_message.ts}_{channel_id}"
        existing_ticket = self.ticket_service.get_ticket_by_external_id(
            external_id, organization_id
        )

        if existing_ticket:
            # Update existing ticket with new replies
            for reply in replies:
                # Check if this reply was already added
                reply_external_id = f"slack_{reply.ts}_{channel_id}"

                # Add as comment if not already present
                comment_text = self._format_message_for_ticket(reply, channel_name)
                self.ticket_service.add_comment_to_ticket(
                    existing_ticket.id,
                    comment_text,
                    organization_id,
                    source="slack_sync"
                )
                result['messages_processed'] += 1

            result['tickets_updated'] += 1
            logger.debug(f"Updated ticket {existing_ticket.id} with {len(replies)} new replies")

        else:
            # Create new ticket from parent message
            ticket = self._create_ticket_from_message(
                parent_message,
                channel_id,
                channel_name,
                organization_id
            )

            if ticket:
                result['tickets_created'] += 1
                result['messages_processed'] += 1

                # Add replies as comments
                for reply in replies:
                    comment_text = self._format_message_for_ticket(reply, channel_name)
                    self.ticket_service.add_comment_to_ticket(
                        ticket.id,
                        comment_text,
                        organization_id,
                        source="slack_sync"
                    )
                    result['messages_processed'] += 1

                logger.debug(f"Created ticket {ticket.id} with {len(replies)} replies")

        return result

    def _create_ticket_from_message(
        self,
        message: SlackMessage,
        channel_id: str,
        channel_name: str,
        organization_id: int
    ):
        """Create ticket from Slack message"""
        try:
            # Get user info
            user_info = None
            if message.user:
                user_info = self.slack_client.get_user_info(message.user)

            # Generate title and description
            title = self._generate_ticket_title(message, channel_name, user_info)
            description = self._format_message_for_ticket(message, channel_name)

            # Determine priority
            priority = self._determine_priority(message)

            # Create ticket
            ticket_data = TicketCreate(
                title=title,
                description=description,
                priority=priority,
                status=TicketStatus.OPEN,
                source="slack",
                external_id=f"slack_{message.ts}_{channel_id}",
                metadata={
                    "slack_channel": channel_id,
                    "slack_channel_name": channel_name,
                    "slack_message_ts": message.ts,
                    "slack_thread_ts": message.thread_ts,
                    "slack_user": message.user,
                    "slack_user_name": user_info.real_name if user_info else None,
                    "slack_user_email": user_info.email if user_info else None,
                    "has_files": len(message.files) > 0,
                    "reply_count": message.reply_count,
                    "created_from_sync": True
                }
            )

            ticket = self.ticket_service.create_ticket(ticket_data, organization_id)

            # Get permalink
            permalink = self.slack_client.get_permalink(channel_id, message.ts)
            if permalink:
                ticket.metadata["slack_permalink"] = permalink
                self.db.commit()

            return ticket

        except Exception as e:
            logger.error(f"Error creating ticket from message {message.ts}: {e}")
            return None

    def _should_skip_message(self, message: SlackMessage) -> bool:
        """Check if message should be skipped"""
        # Skip empty messages
        if not message.text.strip() and not message.files:
            return True

        # Skip bot messages (configurable)
        if message.subtype == 'bot_message':
            return True

        # Skip system messages
        system_subtypes = {
            'channel_join', 'channel_leave', 'channel_topic',
            'channel_purpose', 'channel_name', 'channel_archive'
        }
        if message.subtype in system_subtypes:
            return True

        return False

    def _format_message_for_ticket(self, message: SlackMessage, channel_name: str) -> str:
        """Format message for ticket description"""
        lines = []

        # Get user info
        user_info = None
        if message.user:
            user_info = self.slack_client.get_user_info(message.user)

        # User info
        if user_info:
            user_display = user_info.real_name or user_info.display_name or user_info.name
            if user_info.email:
                user_display += f" ({user_info.email})"
        else:
            user_display = message.user or "Unknown User"

        lines.append(f"**From:** {user_display}")
        lines.append(f"**Channel:** #{channel_name}")
        lines.append(f"**Time:** {message.timestamp_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("")

        # Message content
        if message.text:
            lines.append("**Message:**")
            lines.append(message.text)
            lines.append("")

        # Files
        if message.files:
            lines.append("**Attachments:**")
            for file_info in message.files:
                file_name = file_info.get('name', 'Unknown file')
                file_type = file_info.get('filetype', 'unknown')
                lines.append(f"- {file_name} ({file_type})")
            lines.append("")

        return "\n".join(lines)

    def _generate_ticket_title(self, message: SlackMessage, channel_name: str, user_info) -> str:
        """Generate ticket title from message"""
        if message.text:
            title = message.text.strip()[:100]
            if len(message.text) > 100:
                title += "..."
        else:
            title = "Message with attachments"

        user_display = user_info.real_name if user_info else (message.user or "Unknown")
        return f"[#{channel_name}] {title} - {user_display}"

    def _determine_priority(self, message: SlackMessage) -> TicketPriority:
        """Determine ticket priority based on message content"""
        text = message.text.lower()

        # High priority keywords
        high_priority_keywords = [
            'urgent', 'critical', 'emergency', 'down', 'broken',
            'error', 'bug', 'issue', 'problem', 'help'
        ]

        # Medium priority keywords
        medium_priority_keywords = [
            'question', 'support', 'request', 'feature'
        ]

        if any(keyword in text for keyword in high_priority_keywords):
            return TicketPriority.HIGH
        elif any(keyword in text for keyword in medium_priority_keywords):
            return TicketPriority.MEDIUM
        else:
            return TicketPriority.LOW

    def _get_monitored_channels(self) -> List[str]:
        """Get list of monitored channel IDs from configuration"""
        try:
            # This would come from the integration config
            return self.slack_client.monitored_channels
        except Exception:
            return []

    def _get_all_accessible_channels(self) -> List[str]:
        """Get all channels the bot has access to"""
        try:
            channels = self.slack_client.get_channels()
            return [c.id for c in channels if c.is_member]
        except Exception as e:
            logger.error(f"Error getting accessible channels: {e}")
            return []

    def _get_incremental_sync_timestamp(self) -> str:
        """Get timestamp for incremental sync (last 24 hours)"""
        yesterday = datetime.utcnow() - timedelta(hours=24)
        return str(yesterday.timestamp())

    def _get_organization_id(self) -> Optional[int]:
        """Get organization ID from current context"""
        # This would need to be passed from the calling context
        # For now, return None and require it to be passed in
        return None

    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status"""
        return {
            "last_sync": None,  # Would track in database
            "total_messages_synced": 0,  # Would track in database
            "monitored_channels": len(self._get_monitored_channels()),
            "accessible_channels": len(self._get_all_accessible_channels()),
            "sync_enabled": True
        }