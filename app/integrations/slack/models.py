"""
Slack integration data models and response schemas
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SlackBotInfo:
    """Information about the Slack bot"""
    user_id: str
    bot_id: Optional[str]
    team_id: str
    team_name: str
    user_name: str


@dataclass
class SlackUser:
    """Slack user information"""
    id: str
    name: Optional[str]
    real_name: Optional[str]
    display_name: Optional[str]
    email: Optional[str]
    is_bot: bool = False
    is_admin: bool = False
    is_owner: bool = False
    team_id: Optional[str] = None
    tz: Optional[str] = None


@dataclass
class SlackChannel:
    """Slack channel information"""
    id: str
    name: Optional[str]
    is_channel: bool = False
    is_group: bool = False
    is_private: bool = False
    is_member: bool = False
    num_members: int = 0
    topic: Optional[str] = None
    purpose: Optional[str] = None


@dataclass
class SlackMessage:
    """Slack message data"""
    ts: str  # Timestamp (unique message identifier)
    user: Optional[str]  # User ID who sent the message
    text: str
    channel: str  # Channel ID
    thread_ts: Optional[str] = None  # If this is a reply, the parent message ts
    reply_count: int = 0
    reply_users_count: int = 0
    latest_reply: Optional[str] = None
    subtype: Optional[str] = None  # Message subtype (bot_message, file_share, etc.)
    files: List[Dict[str, Any]] = None
    reactions: List[Dict[str, Any]] = None
    permalink: Optional[str] = None

    def __post_init__(self):
        if self.files is None:
            self.files = []
        if self.reactions is None:
            self.reactions = []

    @property
    def is_thread_parent(self) -> bool:
        """Check if this message is the parent of a thread"""
        return self.reply_count > 0

    @property
    def is_thread_reply(self) -> bool:
        """Check if this message is a reply in a thread"""
        return self.thread_ts is not None and self.thread_ts != self.ts

    @property
    def timestamp_datetime(self) -> datetime:
        """Convert Slack timestamp to datetime"""
        return datetime.fromtimestamp(float(self.ts))


@dataclass
class SlackThread:
    """Slack thread conversation"""
    parent_message: SlackMessage
    replies: List[SlackMessage]
    channel_id: str
    thread_ts: str

    @property
    def total_messages(self) -> int:
        """Total messages in thread including parent"""
        return len(self.replies) + 1

    @property
    def participants(self) -> List[str]:
        """Unique user IDs who participated in thread"""
        users = set()
        if self.parent_message.user:
            users.add(self.parent_message.user)
        for reply in self.replies:
            if reply.user:
                users.add(reply.user)
        return list(users)


@dataclass
class SlackReaction:
    """Slack reaction information"""
    name: str  # Emoji name (without colons)
    count: int
    users: List[str]  # User IDs who reacted


@dataclass
class SlackFile:
    """Slack file attachment"""
    id: str
    name: str
    title: Optional[str]
    mimetype: str
    filetype: str
    pretty_type: str
    user: str
    size: int
    url_private: str
    url_private_download: str
    permalink: str
    timestamp: str

    @property
    def is_image(self) -> bool:
        """Check if file is an image"""
        return self.mimetype.startswith('image/')

    @property
    def is_document(self) -> bool:
        """Check if file is a document"""
        document_types = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt']
        return self.filetype.lower() in document_types


@dataclass
class SlackWebhookEvent:
    """Slack webhook event data"""
    event_type: str  # message, reaction_added, etc.
    event_data: Dict[str, Any]
    team_id: str
    api_app_id: str
    event_id: str
    event_time: int
    authorizations: List[Dict[str, Any]]
    is_ext_shared_channel: bool = False
    context_team_id: Optional[str] = None
    context_enterprise_id: Optional[str] = None


@dataclass
class SlackMention:
    """User mention in Slack message"""
    user_id: str
    username: str
    start_pos: int
    end_pos: int


@dataclass
class SlackSyncResult:
    """Result of Slack message synchronization"""
    sync_type: str  # 'full' or 'incremental'
    channels_processed: int
    total_messages_fetched: int
    total_messages_processed: int
    total_tickets_created: int
    total_tickets_updated: int
    total_threads_processed: int
    total_errors: int
    errors: List[str]
    duration_seconds: float
    start_time: datetime
    end_time: datetime

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_messages_processed == 0:
            return 100.0
        return ((self.total_messages_processed - self.total_errors) / self.total_messages_processed) * 100


@dataclass
class SlackOAuthState:
    """OAuth state information"""
    state: str
    redirect_uri: str
    team_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class SlackInstallation:
    """Slack app installation info"""
    app_id: str
    team_id: str
    team_name: str
    bot_token: str
    bot_id: str
    bot_user_id: str
    user_token: Optional[str] = None
    user_id: Optional[str] = None
    enterprise_id: Optional[str] = None
    enterprise_name: Optional[str] = None
    is_enterprise_install: bool = False
    scopes: List[str] = None
    user_scopes: List[str] = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = []
        if self.user_scopes is None:
            self.user_scopes = []


# Webhook event type mappings
SLACK_EVENT_TYPES = {
    'message': 'Message posted',
    'message.channels': 'Message posted in channel',
    'message.groups': 'Message posted in private channel',
    'message.im': 'Direct message posted',
    'message.mpim': 'Message posted in group DM',
    'reaction_added': 'Reaction added to message',
    'reaction_removed': 'Reaction removed from message',
    'channel_created': 'Channel created',
    'channel_deleted': 'Channel deleted',
    'channel_rename': 'Channel renamed',
    'channel_archive': 'Channel archived',
    'channel_unarchive': 'Channel unarchived',
    'member_joined_channel': 'User joined channel',
    'member_left_channel': 'User left channel',
    'app_mention': 'App mentioned in message',
    'app_home_opened': 'App Home tab opened',
    'app_uninstalled': 'App uninstalled',
    'tokens_revoked': 'Tokens revoked'
}

# Message subtypes that should be processed as tickets
PROCESSABLE_MESSAGE_SUBTYPES = {
    None,  # Regular messages
    'file_share',  # File attachments
    'thread_broadcast',  # Thread messages broadcast to channel
    # We typically skip bot messages, but can be configured
}

# Message subtypes to ignore
IGNORED_MESSAGE_SUBTYPES = {
    'bot_message',  # Messages from bots (configurable)
    'channel_join',  # User joined channel
    'channel_leave',  # User left channel
    'channel_topic',  # Channel topic changed
    'channel_purpose',  # Channel purpose changed
    'channel_name',  # Channel renamed
    'channel_archive',  # Channel archived
    'channel_unarchive',  # Channel unarchived
    'pinned_item',  # Item pinned
    'unpinned_item',  # Item unpinned
    'ekm_access_denied',  # Enterprise key management
    'reminder_add',  # Reminder added
    'reminder_delete',  # Reminder deleted
}