"""
Slack API client with bot authentication and rate limiting
"""
import logging
from typing import Dict, List, Any, Optional, Generator
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError, SlackClientError
from slack_sdk.oauth import OAuthStateUtils
from slack_sdk.oauth.installation_store import Installation
from urllib.parse import urlencode

from app.integrations.base import BaseIntegration, RateLimiter, AuthenticationError, RateLimitError, IntegrationError
from app.integrations.slack.models import SlackBotInfo, SlackChannel, SlackMessage, SlackThread, SlackUser
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SlackClient(BaseIntegration):
    """
    Slack Bot API client with OAuth 2.0 and rate limiting
    Supports bot tokens and user tokens for different operations
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Slack client with bot/user tokens

        Args:
            config: Dictionary containing Slack configuration
                   - bot_token: Bot User OAuth token (xoxb-...)
                   - user_token: User OAuth token (xoxp-...) [optional]
                   - app_token: App-level token (xapp-...) [optional for Socket Mode]
                   - client_id: OAuth app client ID
                   - client_secret: OAuth app client secret
                   - scopes: List of OAuth scopes
                   - monitored_channels: List of channel IDs to monitor
        """
        if config is None:
            # Fallback to environment variables for development
            config = {
                "bot_token": getattr(settings, 'slack_bot_token', None),
                "user_token": getattr(settings, 'slack_user_token', None),
                "client_id": getattr(settings, 'slack_client_id', None),
                "client_secret": getattr(settings, 'slack_client_secret', None),
                "app_token": getattr(settings, 'slack_app_token', None),
                "scopes": getattr(settings, 'slack_scopes', [
                    "channels:read", "channels:history", "chat:write",
                    "users:read", "reactions:read", "files:read"
                ]),
                "monitored_channels": []
            }
            logger.warning("SlackClient initialized with environment config - this should only happen in development")

        super().__init__(config)

        # Slack API rate limits vary by method but generally ~1 request per second for most endpoints
        # Tier 1: 1+ per minute, Tier 2: 20+ per minute, Tier 3: 50+ per minute, Tier 4: 100+ per minute
        # We'll use conservative rate limiting to avoid issues
        self.rate_limiter = RateLimiter(max_requests=50, time_window=60)

        # Initialize Slack clients
        if self.is_enabled:
            self.bot_client = WebClient(token=self.config.get('bot_token'))

            # User client is optional for elevated permissions
            user_token = self.config.get('user_token')
            self.user_client = WebClient(token=user_token) if user_token else None

            # App token for Socket Mode (optional)
            app_token = self.config.get('app_token')
            self.app_client = WebClient(token=app_token) if app_token else None

            # OAuth configuration
            self.client_id = self.config.get('client_id')
            self.client_secret = self.config.get('client_secret')
            self.scopes = self.config.get('scopes', [])

            # Channel monitoring configuration
            self.monitored_channels = self.config.get('monitored_channels', [])

        else:
            self.bot_client = None
            self.user_client = None
            self.app_client = None
            self.client_id = None
            self.client_secret = None
            self.scopes = []
            self.monitored_channels = []

    def _validate_config(self) -> bool:
        """Validate Slack configuration"""
        # At minimum, we need a bot token
        if not self.config.get('bot_token'):
            logger.warning("Missing Slack bot token")
            return False

        # For OAuth, we need client credentials
        if self.config.get('client_id') and not self.config.get('client_secret'):
            logger.warning("Slack client_id provided but missing client_secret")
            return False

        return True

    def _make_api_call(self, client: WebClient, method: str, **kwargs) -> Dict[str, Any]:
        """
        Make rate-limited API call to Slack with retry logic
        """
        if not self.is_enabled or not client:
            raise AuthenticationError("Slack client not properly configured")

        # Check rate limit
        if not self.rate_limiter.can_make_request():
            wait_time = self.rate_limiter.get_wait_time()
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                import time
                time.sleep(wait_time)

        # Record the request for rate limiting
        self.rate_limiter.record_request()

        try:
            # Get the API method from client
            api_method = getattr(client, method)
            response = api_method(**kwargs)

            # Slack API returns ok: true/false
            if not response.get('ok', False):
                error = response.get('error', 'Unknown error')

                # Handle specific errors
                if error == 'ratelimited':
                    raise RateLimitError(f"Slack API rate limited: {response}")
                elif error in ['invalid_auth', 'account_inactive', 'token_revoked']:
                    raise AuthenticationError(f"Slack authentication error: {error}")
                else:
                    raise IntegrationError(f"Slack API error: {error}")

            return response.data

        except SlackApiError as e:
            # Handle Slack-specific API errors
            if e.response['error'] == 'ratelimited':
                raise RateLimitError(f"Slack API rate limited: {e}")
            elif e.response['error'] in ['invalid_auth', 'account_inactive', 'token_revoked']:
                raise AuthenticationError(f"Slack authentication error: {e.response['error']}")
            else:
                raise IntegrationError(f"Slack API error: {e.response['error']}")

        except SlackClientError as e:
            raise IntegrationError(f"Slack client error: {str(e)}")

    def test_connection(self) -> bool:
        """Test connection to Slack API"""
        if not self.is_enabled or not self.bot_client:
            return False

        try:
            # Test bot token with auth.test
            response = self._make_api_call(self.bot_client, 'auth_test')
            return response.get('ok', False)
        except Exception as e:
            logger.error(f"Slack connection test failed: {e}")
            return False

    def get_bot_info(self) -> Optional[SlackBotInfo]:
        """Get information about the bot"""
        try:
            response = self._make_api_call(self.bot_client, 'auth_test')
            return SlackBotInfo(
                user_id=response.get('user_id'),
                bot_id=response.get('bot_id'),
                team_id=response.get('team_id'),
                team_name=response.get('team'),
                user_name=response.get('user')
            )
        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            return None

    def get_channels(self, types: str = "public_channel,private_channel") -> List[SlackChannel]:
        """
        Get list of channels the bot has access to

        Args:
            types: Comma-separated list of channel types to include
                  (public_channel, private_channel, mpim, im)
        """
        try:
            channels = []
            cursor = None

            while True:
                kwargs = {
                    "types": types,
                    "exclude_archived": True,
                    "limit": 200
                }
                if cursor:
                    kwargs["cursor"] = cursor

                response = self._make_api_call(self.bot_client, 'conversations_list', **kwargs)

                for channel_data in response.get('channels', []):
                    channel = SlackChannel(
                        id=channel_data['id'],
                        name=channel_data.get('name'),
                        is_channel=channel_data.get('is_channel', False),
                        is_group=channel_data.get('is_group', False),
                        is_private=channel_data.get('is_private', False),
                        is_member=channel_data.get('is_member', False),
                        num_members=channel_data.get('num_members', 0),
                        topic=channel_data.get('topic', {}).get('value'),
                        purpose=channel_data.get('purpose', {}).get('value')
                    )
                    channels.append(channel)

                # Check for pagination
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break

            return channels

        except Exception as e:
            logger.error(f"Error fetching channels: {e}")
            return []

    def join_channel(self, channel_id: str) -> bool:
        """Join a channel"""
        try:
            self._make_api_call(self.bot_client, 'conversations_join', channel=channel_id)
            return True
        except Exception as e:
            logger.error(f"Error joining channel {channel_id}: {e}")
            return False

    def get_channel_history(
        self,
        channel_id: str,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
        limit: int = 100
    ) -> Generator[SlackMessage, None, None]:
        """
        Get message history from a channel

        Args:
            channel_id: Channel to fetch messages from
            oldest: Only messages after this timestamp
            latest: Only messages before this timestamp
            limit: Maximum messages per request (max 1000)
        """
        try:
            cursor = None
            limit = min(limit, 1000)  # Slack max is 1000

            while True:
                kwargs = {
                    "channel": channel_id,
                    "limit": limit
                }

                if oldest:
                    kwargs["oldest"] = oldest
                if latest:
                    kwargs["latest"] = latest
                if cursor:
                    kwargs["cursor"] = cursor

                response = self._make_api_call(self.bot_client, 'conversations_history', **kwargs)

                messages = response.get('messages', [])
                if not messages:
                    break

                for message_data in messages:
                    # Skip messages without text or from bots (unless we want bot messages)
                    if not message_data.get('text') and not message_data.get('files'):
                        continue

                    message = SlackMessage(
                        ts=message_data['ts'],
                        user=message_data.get('user'),
                        text=message_data.get('text', ''),
                        channel=channel_id,
                        thread_ts=message_data.get('thread_ts'),
                        reply_count=message_data.get('reply_count', 0),
                        reply_users_count=message_data.get('reply_users_count', 0),
                        latest_reply=message_data.get('latest_reply'),
                        subtype=message_data.get('subtype'),
                        files=message_data.get('files', []),
                        reactions=message_data.get('reactions', []),
                        permalink=None  # Will be set separately if needed
                    )
                    yield message

                # Check for pagination
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break

        except Exception as e:
            logger.error(f"Error fetching channel history for {channel_id}: {e}")

    def get_thread_replies(self, channel_id: str, thread_ts: str) -> List[SlackMessage]:
        """Get replies to a thread"""
        try:
            response = self._make_api_call(
                self.bot_client,
                'conversations_replies',
                channel=channel_id,
                ts=thread_ts
            )

            messages = []
            for message_data in response.get('messages', []):
                message = SlackMessage(
                    ts=message_data['ts'],
                    user=message_data.get('user'),
                    text=message_data.get('text', ''),
                    channel=channel_id,
                    thread_ts=message_data.get('thread_ts'),
                    reply_count=message_data.get('reply_count', 0),
                    reply_users_count=message_data.get('reply_users_count', 0),
                    latest_reply=message_data.get('latest_reply'),
                    subtype=message_data.get('subtype'),
                    files=message_data.get('files', []),
                    reactions=message_data.get('reactions', []),
                    permalink=None
                )
                messages.append(message)

            return messages

        except Exception as e:
            logger.error(f"Error fetching thread replies for {thread_ts}: {e}")
            return []

    def get_user_info(self, user_id: str) -> Optional[SlackUser]:
        """Get user information"""
        try:
            response = self._make_api_call(self.bot_client, 'users_info', user=user_id)
            user_data = response.get('user', {})

            return SlackUser(
                id=user_data['id'],
                name=user_data.get('name'),
                real_name=user_data.get('real_name'),
                display_name=user_data.get('profile', {}).get('display_name'),
                email=user_data.get('profile', {}).get('email'),
                is_bot=user_data.get('is_bot', False),
                is_admin=user_data.get('is_admin', False),
                is_owner=user_data.get('is_owner', False),
                team_id=user_data.get('team_id'),
                tz=user_data.get('tz')
            )

        except Exception as e:
            logger.error(f"Error getting user info for {user_id}: {e}")
            return None

    def post_message(self, channel: str, text: str, thread_ts: Optional[str] = None) -> Optional[str]:
        """
        Post a message to a channel

        Returns:
            Message timestamp if successful, None otherwise
        """
        try:
            kwargs = {
                "channel": channel,
                "text": text
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts

            response = self._make_api_call(self.bot_client, 'chat_postMessage', **kwargs)
            return response.get('ts')

        except Exception as e:
            logger.error(f"Error posting message to {channel}: {e}")
            return None

    def add_reaction(self, channel: str, timestamp: str, name: str) -> bool:
        """Add reaction to a message"""
        try:
            self._make_api_call(
                self.bot_client,
                'reactions_add',
                channel=channel,
                timestamp=timestamp,
                name=name
            )
            return True
        except Exception as e:
            logger.error(f"Error adding reaction {name} to message {timestamp}: {e}")
            return False

    def get_permalink(self, channel: str, message_ts: str) -> Optional[str]:
        """Get permalink for a message"""
        try:
            response = self._make_api_call(
                self.bot_client,
                'chat_getPermalink',
                channel=channel,
                message_ts=message_ts
            )
            return response.get('permalink')
        except Exception as e:
            logger.error(f"Error getting permalink for message {message_ts}: {e}")
            return None

    def generate_oauth_url(self, state: str, redirect_uri: str) -> str:
        """Generate OAuth authorization URL"""
        if not self.client_id:
            raise ValueError("client_id required for OAuth")

        params = {
            'client_id': self.client_id,
            'scope': ','.join(self.scopes),
            'state': state,
            'redirect_uri': redirect_uri
        }

        return f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"

    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange OAuth code for access tokens"""
        if not self.client_id or not self.client_secret:
            raise ValueError("client_id and client_secret required for OAuth")

        # Use a temporary client without token for OAuth
        oauth_client = WebClient()

        try:
            response = oauth_client.oauth_v2_access(
                client_id=self.client_id,
                client_secret=self.client_secret,
                code=code,
                redirect_uri=redirect_uri
            )

            return response.data

        except SlackApiError as e:
            raise IntegrationError(f"OAuth token exchange failed: {e.response['error']}")

    def sync_tickets(self, full_sync: bool = False) -> Dict[str, Any]:
        """
        Synchronize messages from monitored channels as tickets
        Implementation will be in the sync.py module
        """
        from app.integrations.slack.sync import SlackSyncService
        sync_service = SlackSyncService(self)
        return sync_service.sync_messages(full_sync=full_sync)

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        return {
            "max_requests": self.rate_limiter.max_requests,
            "time_window": self.rate_limiter.time_window,
            "current_requests": len(self.rate_limiter.requests),
            "requests_remaining": self.rate_limiter.max_requests - len(self.rate_limiter.requests),
            "wait_time": self.rate_limiter.get_wait_time(),
            "can_make_request": self.rate_limiter.can_make_request()
        }