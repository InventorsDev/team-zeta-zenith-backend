"""
Slack webhook event handler for real-time message processing
"""
import json
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.integrations.slack.models import (
    SlackWebhookEvent, SlackMessage, SlackMention, SlackReaction,
    SLACK_EVENT_TYPES, PROCESSABLE_MESSAGE_SUBTYPES, IGNORED_MESSAGE_SUBTYPES
)
from app.integrations.slack.client import SlackClient
from app.services.ticket_service import TicketService
from app.services.integration_service import IntegrationService
from app.schemas.ticket import TicketCreate
from app.models.ticket import TicketPriority, TicketStatus
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SlackWebhookHandler:
    """
    Handles incoming Slack webhook events and processes them into tickets
    """

    def __init__(self, db: Session):
        self.db = db
        self.ticket_service = TicketService(db)
        self.integration_service = IntegrationService(db)

    def handle_webhook(
        self,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
        body: bytes = None
    ) -> Dict[str, Any]:
        """
        Process incoming Slack webhook event

        Args:
            payload: Webhook payload data
            signature: Slack signature for verification
            body: Raw request body for signature verification

        Returns:
            Processing result
        """
        try:
            # Handle URL verification challenge
            if payload.get('type') == 'url_verification':
                return {'challenge': payload.get('challenge')}

            # Verify webhook signature if provided
            if signature and body:
                if not self._verify_signature(signature, body):
                    logger.warning("Invalid Slack webhook signature")
                    return {'error': 'Invalid signature', 'status': 'rejected'}

            # Process event
            if payload.get('type') == 'event_callback':
                return self._process_event(payload)
            else:
                logger.info(f"Ignoring webhook type: {payload.get('type')}")
                return {'status': 'ignored', 'reason': f"Unsupported webhook type: {payload.get('type')}"}

        except Exception as e:
            logger.error(f"Error processing Slack webhook: {e}")
            return {'error': str(e), 'status': 'error'}

    def _verify_signature(self, signature: str, body: bytes) -> bool:
        """
        Verify Slack webhook signature

        Slack signs webhook requests using your app's signing secret.
        The signature is in the X-Slack-Signature header.
        """
        try:
            # Get signing secret from settings
            signing_secret = getattr(settings, 'slack_signing_secret', None)
            if not signing_secret:
                logger.warning("No Slack signing secret configured")
                return True  # Skip verification if no secret configured

            # Extract timestamp from signature
            timestamp = signature.split(',')[0].split('=')[1]

            # Create base string
            base_string = f"v0:{timestamp}:{body.decode('utf-8')}"

            # Create signature
            expected_signature = 'v0=' + hmac.new(
                signing_secret.encode(),
                base_string.encode(),
                hashlib.sha256
            ).hexdigest()

            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Error verifying Slack signature: {e}")
            return False

    def _process_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process event callback from Slack"""
        event = payload.get('event', {})
        event_type = event.get('type')
        team_id = payload.get('team_id')

        logger.info(f"Processing Slack event: {event_type} from team {team_id}")

        # Find integration by team_id
        integration = self._find_integration_by_team_id(team_id)
        if not integration:
            logger.warning(f"No integration found for team {team_id}")
            return {'status': 'ignored', 'reason': 'No integration found for team'}

        # Get Slack client for this integration
        slack_client = self._get_slack_client(integration)
        if not slack_client:
            logger.error(f"Could not create Slack client for integration {integration.id}")
            return {'status': 'error', 'reason': 'Could not create Slack client'}

        # Route to specific event handler
        if event_type == 'message':
            return self._handle_message_event(event, slack_client, integration)
        elif event_type == 'reaction_added':
            return self._handle_reaction_event(event, slack_client, integration, 'added')
        elif event_type == 'reaction_removed':
            return self._handle_reaction_event(event, slack_client, integration, 'removed')
        elif event_type == 'app_mention':
            return self._handle_mention_event(event, slack_client, integration)
        elif event_type in ['member_joined_channel', 'member_left_channel']:
            return self._handle_channel_membership_event(event, slack_client, integration)
        else:
            logger.info(f"Ignoring event type: {event_type}")
            return {'status': 'ignored', 'reason': f'Event type {event_type} not processed'}

    def _find_integration_by_team_id(self, team_id: str):
        """Find Slack integration by team ID"""
        try:
            # Search integrations for one with matching team_id in config
            from app.models.integration import IntegrationType

            integrations = self.integration_service.integration_repo.find_by_type(
                IntegrationType.SLACK
            )

            for integration in integrations:
                config = self.integration_service.integration_repo.get_decrypted_config(integration)
                if config and config.get('team_id') == team_id:
                    return integration

            return None

        except Exception as e:
            logger.error(f"Error finding integration by team_id {team_id}: {e}")
            return None

    def _get_slack_client(self, integration) -> Optional[SlackClient]:
        """Get Slack client for integration"""
        try:
            config = self.integration_service.integration_repo.get_decrypted_config(integration)
            return SlackClient(config)
        except Exception as e:
            logger.error(f"Error creating Slack client: {e}")
            return None

    def _handle_message_event(
        self,
        event: Dict[str, Any],
        slack_client: SlackClient,
        integration
    ) -> Dict[str, Any]:
        """Handle message events"""
        try:
            # Extract message data
            channel = event.get('channel')
            user = event.get('user')
            text = event.get('text', '')
            ts = event.get('ts')
            thread_ts = event.get('thread_ts')
            subtype = event.get('subtype')
            files = event.get('files', [])

            # Skip messages from bots unless configured otherwise
            if event.get('bot_id') and not self._should_process_bot_messages(integration):
                return {'status': 'ignored', 'reason': 'Bot message'}

            # Skip ignored message subtypes
            if subtype in IGNORED_MESSAGE_SUBTYPES:
                return {'status': 'ignored', 'reason': f'Ignored subtype: {subtype}'}

            # Check if channel is monitored
            if not self._is_channel_monitored(channel, integration):
                return {'status': 'ignored', 'reason': 'Channel not monitored'}

            # Skip empty messages unless they have files
            if not text.strip() and not files:
                return {'status': 'ignored', 'reason': 'Empty message'}

            # Create SlackMessage object
            message = SlackMessage(
                ts=ts,
                user=user,
                text=text,
                channel=channel,
                thread_ts=thread_ts,
                subtype=subtype,
                files=files
            )

            # Get user info for better ticket attribution
            user_info = slack_client.get_user_info(user) if user else None

            # Create or update ticket
            if thread_ts and thread_ts != ts:
                # This is a reply in a thread
                return self._handle_thread_reply(message, slack_client, integration, user_info)
            else:
                # This is a new message or thread parent
                return self._create_ticket_from_message(message, slack_client, integration, user_info)

        except Exception as e:
            logger.error(f"Error handling message event: {e}")
            return {'status': 'error', 'error': str(e)}

    def _handle_thread_reply(
        self,
        message: SlackMessage,
        slack_client: SlackClient,
        integration,
        user_info
    ) -> Dict[str, Any]:
        """Handle thread reply by updating parent ticket"""
        try:
            # Find existing ticket by thread_ts
            ticket = self.ticket_service.get_ticket_by_external_id(
                f"slack_{message.thread_ts}_{message.channel}",
                integration.organization_id
            )

            if ticket:
                # Add reply as comment to existing ticket
                comment_text = self._format_message_for_ticket(message, user_info)

                # Update ticket with new comment
                self.ticket_service.add_comment_to_ticket(
                    ticket.id,
                    comment_text,
                    integration.organization_id,
                    source="slack_thread_reply"
                )

                logger.info(f"Added thread reply to ticket {ticket.id}")
                return {
                    'status': 'processed',
                    'action': 'thread_reply_added',
                    'ticket_id': ticket.id,
                    'message_ts': message.ts
                }
            else:
                # Parent ticket not found, create new ticket
                logger.warning(f"Parent ticket not found for thread {message.thread_ts}, creating new ticket")
                return self._create_ticket_from_message(message, slack_client, integration, user_info)

        except Exception as e:
            logger.error(f"Error handling thread reply: {e}")
            return {'status': 'error', 'error': str(e)}

    def _create_ticket_from_message(
        self,
        message: SlackMessage,
        slack_client: SlackClient,
        integration,
        user_info
    ) -> Dict[str, Any]:
        """Create new ticket from Slack message"""
        try:
            # Get channel info
            channels = slack_client.get_channels()
            channel_info = next((c for c in channels if c.id == message.channel), None)
            channel_name = channel_info.name if channel_info else message.channel

            # Format ticket data
            title = self._generate_ticket_title(message, channel_name, user_info)
            description = self._format_message_for_ticket(message, user_info)

            # Detect mentions
            mentions = self._extract_mentions(message.text)

            # Determine priority based on content
            priority = self._determine_priority(message, mentions)

            # Create ticket
            ticket_data = TicketCreate(
                title=title,
                description=description,
                priority=priority,
                status=TicketStatus.OPEN,
                source="slack",
                external_id=f"slack_{message.ts}_{message.channel}",
                metadata={
                    "slack_channel": message.channel,
                    "slack_channel_name": channel_name,
                    "slack_message_ts": message.ts,
                    "slack_thread_ts": message.thread_ts,
                    "slack_user": message.user,
                    "slack_user_name": user_info.real_name if user_info else None,
                    "slack_user_email": user_info.email if user_info else None,
                    "mentions": [m.__dict__ for m in mentions],
                    "reaction_count": len(message.reactions),
                    "has_files": len(message.files) > 0,
                    "integration_id": integration.id
                }
            )

            ticket = self.ticket_service.create_ticket(ticket_data, integration.organization_id)

            # Get permalink for better tracking
            permalink = slack_client.get_permalink(message.channel, message.ts)
            if permalink:
                ticket.metadata["slack_permalink"] = permalink
                self.db.commit()

            logger.info(f"Created ticket {ticket.id} from Slack message {message.ts}")
            return {
                'status': 'processed',
                'action': 'ticket_created',
                'ticket_id': ticket.id,
                'message_ts': message.ts
            }

        except Exception as e:
            logger.error(f"Error creating ticket from message: {e}")
            return {'status': 'error', 'error': str(e)}

    def _handle_reaction_event(
        self,
        event: Dict[str, Any],
        slack_client: SlackClient,
        integration,
        action: str
    ) -> Dict[str, Any]:
        """Handle reaction added/removed events"""
        try:
            item = event.get('item', {})
            if item.get('type') != 'message':
                return {'status': 'ignored', 'reason': 'Reaction not on message'}

            channel = item.get('channel')
            message_ts = item.get('ts')
            reaction = event.get('reaction')
            user = event.get('user')

            # Find ticket by message
            ticket = self.ticket_service.get_ticket_by_external_id(
                f"slack_{message_ts}_{channel}",
                integration.organization_id
            )

            if ticket:
                # Update ticket metadata with reaction info
                if 'reactions' not in ticket.metadata:
                    ticket.metadata['reactions'] = []

                # Update reaction data
                reactions = ticket.metadata['reactions']
                existing_reaction = next(
                    (r for r in reactions if r['name'] == reaction),
                    None
                )

                if action == 'added':
                    if existing_reaction:
                        if user not in existing_reaction['users']:
                            existing_reaction['users'].append(user)
                            existing_reaction['count'] = len(existing_reaction['users'])
                    else:
                        reactions.append({
                            'name': reaction,
                            'count': 1,
                            'users': [user]
                        })
                elif action == 'removed':
                    if existing_reaction and user in existing_reaction['users']:
                        existing_reaction['users'].remove(user)
                        existing_reaction['count'] = len(existing_reaction['users'])
                        if existing_reaction['count'] == 0:
                            reactions.remove(existing_reaction)

                # Save changes
                self.db.commit()

                logger.info(f"Updated reactions for ticket {ticket.id}")
                return {
                    'status': 'processed',
                    'action': f'reaction_{action}',
                    'ticket_id': ticket.id,
                    'reaction': reaction
                }
            else:
                return {'status': 'ignored', 'reason': 'Ticket not found for reaction'}

        except Exception as e:
            logger.error(f"Error handling reaction event: {e}")
            return {'status': 'error', 'error': str(e)}

    def _handle_mention_event(
        self,
        event: Dict[str, Any],
        slack_client: SlackClient,
        integration
    ) -> Dict[str, Any]:
        """Handle app mention events"""
        try:
            # App mentions are essentially messages, so process them as such
            return self._handle_message_event(event, slack_client, integration)

        except Exception as e:
            logger.error(f"Error handling mention event: {e}")
            return {'status': 'error', 'error': str(e)}

    def _handle_channel_membership_event(
        self,
        event: Dict[str, Any],
        slack_client: SlackClient,
        integration
    ) -> Dict[str, Any]:
        """Handle channel membership changes"""
        try:
            # For now, just log membership changes
            # Future: Could create tickets for user join/leave in monitored channels
            event_type = event.get('type')
            user = event.get('user')
            channel = event.get('channel')

            logger.info(f"Channel membership event: {event_type} - user {user} in channel {channel}")
            return {'status': 'processed', 'action': 'membership_logged'}

        except Exception as e:
            logger.error(f"Error handling membership event: {e}")
            return {'status': 'error', 'error': str(e)}

    def _is_channel_monitored(self, channel_id: str, integration) -> bool:
        """Check if channel is being monitored"""
        try:
            config = self.integration_service.integration_repo.get_decrypted_config(integration)
            monitored_channels = config.get('monitored_channels', [])

            # If no channels specified, monitor all channels the bot is in
            if not monitored_channels:
                return True

            return channel_id in monitored_channels

        except Exception as e:
            logger.error(f"Error checking monitored channels: {e}")
            return False

    def _should_process_bot_messages(self, integration) -> bool:
        """Check if bot messages should be processed"""
        try:
            config = self.integration_service.integration_repo.get_decrypted_config(integration)
            return config.get('process_bot_messages', False)
        except Exception:
            return False

    def _format_message_for_ticket(self, message: SlackMessage, user_info) -> str:
        """Format Slack message for ticket description"""
        lines = []

        # User info
        if user_info:
            user_display = user_info.real_name or user_info.display_name or user_info.name
            if user_info.email:
                user_display += f" ({user_info.email})"
        else:
            user_display = message.user or "Unknown User"

        lines.append(f"**From:** {user_display}")
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

        # Reactions
        if message.reactions:
            reaction_summary = ", ".join([
                f"{r.get('name', 'unknown')} ({r.get('count', 0)})"
                for r in message.reactions
            ])
            lines.append(f"**Reactions:** {reaction_summary}")
            lines.append("")

        return "\n".join(lines)

    def _generate_ticket_title(self, message: SlackMessage, channel_name: str, user_info) -> str:
        """Generate ticket title from message"""
        # Use first 100 chars of message as title
        if message.text:
            title = message.text.strip()[:100]
            if len(message.text) > 100:
                title += "..."
        else:
            title = "Message with attachments"

        # Add channel context
        user_display = user_info.real_name if user_info else (message.user or "Unknown")
        return f"[#{channel_name}] {title} - {user_display}"

    def _extract_mentions(self, text: str) -> List[SlackMention]:
        """Extract user mentions from message text"""
        mentions = []
        import re

        # Slack mentions are in format <@U1234567|username> or <@U1234567>
        mention_pattern = r'<@([A-Z0-9]+)(?:\|([^>]+))?>'

        for match in re.finditer(mention_pattern, text):
            user_id = match.group(1)
            username = match.group(2) or user_id
            start_pos = match.start()
            end_pos = match.end()

            mention = SlackMention(
                user_id=user_id,
                username=username,
                start_pos=start_pos,
                end_pos=end_pos
            )
            mentions.append(mention)

        return mentions

    def _determine_priority(self, message: SlackMessage, mentions: List[SlackMention]) -> TicketPriority:
        """Determine ticket priority based on message content"""
        text = message.text.lower()

        # High priority indicators
        high_priority_keywords = [
            'urgent', 'critical', 'emergency', 'down', 'broken', 'error',
            'bug', 'issue', 'problem', 'help', 'asap'
        ]

        # Medium priority indicators
        medium_priority_keywords = [
            'question', 'support', 'request', 'feature', 'enhancement'
        ]

        # Check for mentions (usually higher priority)
        if mentions:
            return TicketPriority.MEDIUM

        # Check text content
        if any(keyword in text for keyword in high_priority_keywords):
            return TicketPriority.HIGH
        elif any(keyword in text for keyword in medium_priority_keywords):
            return TicketPriority.MEDIUM
        else:
            return TicketPriority.LOW

    def validate_webhook_config(self) -> Dict[str, Any]:
        """Validate webhook configuration"""
        config_status = {
            "signing_secret": bool(getattr(settings, 'slack_signing_secret', None)),
            "webhook_url_format": "POST /api/v1/integrations/webhooks/{webhook_token}",
            "supported_events": list(SLACK_EVENT_TYPES.keys()),
            "validation": "URL verification supported"
        }

        return config_status

    def get_webhook_url(self, base_url: str, webhook_token: str) -> str:
        """Get webhook URL for Slack app configuration"""
        return f"{base_url.rstrip('/')}/api/v1/integrations/webhooks/{webhook_token}"